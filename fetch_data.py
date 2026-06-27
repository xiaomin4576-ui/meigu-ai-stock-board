#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① 数据层:按 config.json 股票池,用 yfinance 拉【真实】:
   (a) 行情/技术(价格/动量/MA/52周)
   (b) 券商分析师一致数据(目标价/评级/覆盖家数/前瞻PE)—— 机构共识锚
   (c) 下次财报日期
   (d) 近期新闻催化剂(标题+来源+链接+日期)
写入 state/data_<date>.json。全部真实抓取,缺失标 null,绝不编造。

CI 加固:每支重试+指数退避+浏览器 UA/session;单支失败不影响整体;
整体严重失败(成功 < 一半)时【绝不】用空数据覆盖,回退复用最近一份真实 data,
并在输出 meta.banner 标注「数据为 X 日(云端取数受限)」。脚本永远 exit 0。"""
import json, os, glob, time, random, datetime
import requests
import yfinance as yf

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()  # 北京时间

# === CI 抗限流参数(集中可调)===
RETRIES = 3                 # 单支最多重试次数
BACKOFF_BASE = 2.0          # 指数退避基数秒:2s/4s/8s(+抖动)
GAP = (1.0, 2.0)            # 股票之间随机间隔秒,降低被判爬虫概率
DEGRADE_RATIO = 0.5         # 成功率低于此值 → 判定云端取数受限,触发回退
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
# Twelve Data 行情 API:云端稳定取数(不像 Yahoo 限流数据中心 IP),需 secret TD_API_KEY(免费档)
TD_KEY = (os.environ.get("TD_API_KEY") or "").strip()
TD_BASE = "https://api.twelvedata.com"
FINNHUB_KEY = (os.environ.get("FINNHUB_KEY") or "").strip()   # 美股共识/评级/财报日/财务指标(云端IP可达,非Yahoo黑名单);留空则美股维持"技术分"现状,不影响
FH_BASE = "https://finnhub.io/api/v1"


def _session():
    """带浏览器 UA / 连接复用的 session,挡掉数据中心 IP 的大部分 429/401。"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/json,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


def _with_retry(fn, label):
    """指数退避重试。fn 抛异常或返回 None 视为失败,可重试。"""
    last = None
    for i in range(RETRIES):
        try:
            r = fn()
            if r is not None:
                return r
            last = "返回空"
        except Exception as e:
            last = str(e)[:120]
        if i < RETRIES - 1:
            wait = BACKOFF_BASE * (2 ** i) + random.uniform(0, 1)
            print(f"    {label} 第{i+1}次失败({last}),{wait:.1f}s 后重试")
            time.sleep(wait)
    raise RuntimeError(f"重试{RETRIES}次仍失败: {last}")


def pct(cur, ref):
    try:
        return round((cur / ref - 1) * 100, 1)
    except Exception:
        return None


def ann_vol(closes, win=20):
    """近 win 日收盘的日收益年化波动率(%)。长期视角下低波动更优(次新/抛物线票波动高)。"""
    try:
        import statistics
        cl = [float(x) for x in list(closes)][-(win + 1):]
        if len(cl) < 10:
            return None
        rets = [cl[i] / cl[i - 1] - 1 for i in range(1, len(cl)) if cl[i - 1]]
        return round(statistics.pstdev(rets) * (252 ** 0.5) * 100, 1) if len(rets) >= 8 else None
    except Exception:
        return None


def get_news(t, k=3):
    out = []
    try:
        for n in (t.news or [])[:6]:
            c = n.get("content", n)
            title = c.get("title") or n.get("title")
            prov = c.get("provider") or {}
            pub = prov.get("displayName") if isinstance(prov, dict) else n.get("publisher")
            cu = c.get("canonicalUrl") or {}
            url = cu.get("url") if isinstance(cu, dict) else n.get("link")
            date = c.get("pubDate") or n.get("providerPublishTime")
            if title and url:
                out.append({"title": str(title)[:90], "pub": str(pub or ""), "url": url, "date": str(date)[:10]})
            if len(out) >= k:
                break
    except Exception:
        pass
    return out


def get_earnings_date(t):
    try:
        cal = t.calendar
        ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if isinstance(ed, list) and ed:
            return str(ed[0])
        return str(ed) if ed else None
    except Exception:
        return None


_CN_RATE_FROM_RATIO = lambda br: ("买入" if br >= 0.7 else "增持" if br >= 0.5 else "持有" if br >= 0.3 else "中性")


def us_finnhub(symbol, sess=None):
    """美股用 Finnhub 免费档补强(env 设 FINNHUB_KEY 才启用;云端 IP 可达、非 Yahoo 黑名单)。
    免费档可取:① 分析师评级趋势(recommendation)→ rating_mean(1-5,与yf同口径)+买入占比作"共识上行"代理(免费档无目标价)
    ② 财报日历(calendar/earnings)→ 下次财报日 ③ 财务指标(metric:roeTTM/grossMarginTTM/peTTM/epsGrowthTTMYoy)→ 质量+估值PEG。
    返回扁平 dict(字段缺则不含);任何子调用失败都跳过、不致命。60 次/分。"""
    if not FINNHUB_KEY:
        return {}
    s = sess or _session()
    out = {}

    def fh(path, **params):
        params["token"] = FINNHUB_KEY
        r = s.get(f"{FH_BASE}{path}", params=params, timeout=15)
        return r.json() if r.status_code == 200 else None

    # ① 分析师评级趋势
    try:
        rec = fh("/stock/recommendation", symbol=symbol)
        if isinstance(rec, list) and rec:
            r0 = rec[0]   # 最新一期在前
            sb, b, h, sl, ss = (r0.get("strongBuy", 0) or 0, r0.get("buy", 0) or 0,
                                r0.get("hold", 0) or 0, r0.get("sell", 0) or 0, r0.get("strongSell", 0) or 0)
            tot = sb + b + h + sl + ss
            if tot:
                out["rating_mean"] = round((sb * 1 + b * 2 + h * 3 + sl * 4 + ss * 5) / tot, 2)  # 1=强买…5=强卖
                out["n_analysts"] = tot
                out["cn_rating"] = _CN_RATE_FROM_RATIO((sb + b) / tot)   # 买入占比→评级词,喂"共识上行"因子
                out["rec_buy_ratio"] = round((sb + b) / tot, 2)
    except Exception:
        pass
    # ② 财报日历(取今天起最近一个未来财报日)
    try:
        d0 = datetime.date.fromisoformat(TODAY)
        cal = fh("/calendar/earnings", symbol=symbol,
                 **{"from": d0.isoformat(), "to": (d0 + datetime.timedelta(days=150)).isoformat()})
        ec = (cal or {}).get("earningsCalendar") or []
        fut = sorted(e["date"] for e in ec if e.get("date") and e["date"] >= TODAY)
        if fut:
            out["earnings_date"] = fut[0]
    except Exception:
        pass
    # ③ 财务指标 → 质量 + 估值PEG
    try:
        m = fh("/stock/metric", symbol=symbol, metric="all")
        met = (m or {}).get("metric") or {}
        roe = met.get("roeTTM")
        gm = met.get("grossMarginTTM")
        pe = met.get("peTTM") or met.get("peExclExtraTTM") or met.get("peBasicExclExtraTTM")
        epsg = met.get("epsGrowthTTMYoy")
        if roe is not None or gm is not None:
            out["roe"] = round(float(roe), 1) if roe is not None else None
            out["gross_margin"] = round(float(gm), 1) if gm is not None else None
        if pe and epsg is not None:
            out["fwd_pe"] = round(float(pe), 1)        # 免费档无 forward,用 TTM PE 代理
            out["eps_growth"] = round(float(epsg), 1)
    except Exception:
        pass
    return out


def with_no_proxy(fn):
    """临时禁用 HTTP(S) 代理执行 fn —— A 股数据源(东方财富)需直连,本机代理是给 Claude 访问用的。
    云端(GitHub Actions 无代理)下为无害空操作。执行后恢复原代理环境(不影响 yfinance/Yahoo)。"""
    keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
    saved = {k: os.environ.pop(k) for k in keys if k in os.environ}
    old_no = os.environ.get("NO_PROXY")
    os.environ["NO_PROXY"] = "*"
    try:
        return fn()
    finally:
        os.environ.pop("NO_PROXY", None)
        if old_no is not None:
            os.environ["NO_PROXY"] = old_no
        os.environ.update(saved)


def cn_consensus(code):
    """A 股机构共识(akshare 东财研报):东财评级(近批众数)+ 近一月研报数(覆盖广度)+ 2026 前瞻PE(中位)。
    yfinance 无 A 股一致目标价/评级,用东财研报补。best-effort,失败返回空。"""
    try:
        import akshare as ak
        from collections import Counter
        import statistics
        df = with_no_proxy(lambda: ak.stock_research_report_em(symbol=code))
        if df is None or len(df) == 0:
            return {}
        ratings = [r for r in (df["东财评级"].dropna().tolist() if "东财评级" in df.columns else []) if r]
        rating = Counter(ratings).most_common(1)[0][0] if ratings else None
        n_recent = None
        if "近一月个股研报数" in df.columns and len(df):
            try:
                n_recent = int(df["近一月个股研报数"].iloc[0])
            except Exception:
                n_recent = None
        cols = list(df.columns)

        def med_col(y):
            col = next((c for c in cols if y in c and "收益" in c), None)  # 2026/2027-盈利预测-收益 = EPS预测
            if not col:
                return None
            vals = []
            for x in df[col].tolist():
                try:
                    f = float(x)
                    if f > 0:
                        vals.append(f)
                except Exception:
                    pass
            return round(statistics.median(vals), 3) if vals else None

        eps_2026, eps_2027 = med_col("2026"), med_col("2027")
        sector = str(df.iloc[0]["行业"]) if "行业" in cols and len(df) else None
        # 注:研报里的"市盈率"列是各报告发布时按【当时股价】算的,股价大涨后严重失真,故不用;
        # 真·前瞻PE 由上层 fetch_one_cn 用【当日价 ÷ EPS预测】算。
        return {"rating": rating, "n_recent_reports": n_recent, "total_reports": int(len(df)),
                "eps_2026": eps_2026, "eps_2027": eps_2027, "sector": sector}
    except Exception as e:
        print(f"    {code} akshare 机构数据失败(不致命): {str(e)[:60]}")
        return {}


def cn_news(code, k=3):
    """A 股新闻催化剂(akshare 东财个股新闻),禁代理直连。失败返回空。"""
    try:
        import akshare as ak
        df = with_no_proxy(lambda: ak.stock_news_em(symbol=code))
        if df is None or len(df) == 0:
            return []
        out = []
        for _, r in df.head(k).iterrows():
            title = str(r.get("新闻标题", "") or "")[:90]
            url = r.get("新闻链接", "") or ""
            pub = r.get("文章来源", "") or "东方财富"
            date = str(r.get("发布时间", "") or "")[:10]
            if title and url:
                out.append({"title": title, "pub": str(pub), "url": url, "date": date})
        return out
    except Exception:
        return []


def _cn_next_period():
    """按今天选最可能"即将披露"的报告期末(YYYYMMDD)。披露滞后报告期末约1-2月。"""
    d = datetime.date.fromisoformat(TODAY)
    y, m = d.year, d.month
    if m <= 4:
        return f"{y}0331"     # 一季报(4月底前后披露)
    if m <= 8:
        return f"{y}0630"     # 中报(7-8月披露)
    if m <= 10:
        return f"{y}0930"     # 三季报(10月披露)
    return f"{y}1231"         # 年报(次年3-4月披露)


def cn_earnings_map():
    """A股业绩预约披露日历(akshare 东财 stock_yysj_em):返回 {6位代码: 'YYYY-MM-DD'}。
    优先实际披露时间,否则用首次预约时间。一次拉全表查多只,禁代理。best-effort。"""
    try:
        import akshare as ak
        period = _cn_next_period()
        df = with_no_proxy(lambda: ak.stock_yysj_em(symbol="沪深A股", date=period))
        if df is None or len(df) == 0:
            return {}
        cols = list(df.columns)
        cc = next((c for c in cols if "代码" in c), None)
        sc = "首次预约时间" if "首次预约时间" in cols else None
        ac = "实际披露时间" if "实际披露时间" in cols else None
        out = {}
        for _, r in df.iterrows():
            code = str(r[cc]).zfill(6)
            d = None
            if ac and str(r.get(ac))[:1].isdigit():
                d = str(r.get(ac))[:10]
            elif sc and str(r.get(sc))[:1].isdigit():
                d = str(r.get(sc))[:10]
            if d and len(d) == 10 and d[4] == "-":
                out[code] = d
        print(f"  A股业绩预约日历({period}):{len(out)} 只有披露日")
        return out
    except Exception as e:
        print(f"  A股业绩预约日历失败(不致命): {str(e)[:60]}")
        return {}


def cn_quality(code):
    """A股财务质量(akshare 东财 stock_financial_analysis_indicator):取最近一期 ROE/每股经营现金流/毛利率(毛利缺则回溯年报)。
    质量 = 盈利能力(ROE)+ 现金含量(经营现金流符号)+ 定价权(毛利)。次新股常 ROE 低/现金流为负 → 如实低分,不美化。best-effort、禁代理。"""
    try:
        import akshare as ak
        y0 = str(datetime.date.fromisoformat(TODAY).year - 1)
        df = with_no_proxy(lambda: ak.stock_financial_analysis_indicator(symbol=code, start_year=y0))
        if df is None or len(df) == 0 or "日期" not in df.columns:
            return {}
        df = df.sort_values("日期")

        def col(row, key):
            for c in df.columns:
                if key in c:
                    try:
                        v = float(row.get(c))
                        return v if v == v else None      # 过滤 nan
                    except Exception:
                        return None
            return None

        last = df.iloc[-1]
        roe = col(last, "净资产收益率")
        ocf = col(last, "每股经营性现金流")
        gm = None
        for _, r in df.iloc[::-1].iterrows():             # 毛利当季常空,回溯最近非空(年报)
            v = col(r, "销售毛利率")
            if v is not None:
                gm = v
                break
        if roe is None and ocf is None and gm is None:
            return {}
        return {"roe": roe, "ocf_ps": ocf, "gross_margin": gm, "period": str(last["日期"])}
    except Exception as e:
        print(f"  A股质量失败(不致命): {str(e)[:60]}")
        return {}


def cn_unlock_map(horizon_days=210):
    """A股限售解禁哨兵(akshare 东财 stock_restricted_release_detail_em):一次拉全市场未来~6个月解禁明细,
    返回 {6位代码: {"date":'YYYY-MM-DD',"pct_float":占流通市值比例%,"mktcap_yi":市值亿}}(每只取最近一次)。
    解禁=次新股最大的二元下行风险(限售盘到期抛压);老股/已过解禁的票则无,等于消除一个隐忧。best-effort、禁代理。"""
    try:
        import akshare as ak
        d0 = datetime.date.fromisoformat(TODAY)
        d1 = (d0 + datetime.timedelta(days=horizon_days))
        df = with_no_proxy(lambda: ak.stock_restricted_release_detail_em(
            start_date=d0.strftime("%Y%m%d"), end_date=d1.strftime("%Y%m%d")))
        if df is None or len(df) == 0:
            return {}
        cc = next((c for c in df.columns if "代码" in c), None)
        dc = next((c for c in df.columns if "解禁时间" in c), None)
        pc = next((c for c in df.columns if "占解禁前流通" in c or ("占" in c and "流通" in c)), None)
        mc = next((c for c in df.columns if "实际解禁市值" in c or ("市值" in c and "解禁" in c)), None)
        out = {}
        for _, r in df.iterrows():
            code = str(r[cc]).zfill(6)
            dt = str(r[dc])[:10]
            if not (len(dt) == 10 and dt[4] == "-"):
                continue
            if code in out and out[code]["date"] <= dt:   # 只留最近一次未来解禁
                continue
            pv = r.get(pc) if pc else None
            try:
                pv = round(float(pv) * 100, 1) if (pv is not None and float(pv) < 1) else (round(float(pv), 1) if pv is not None else None)
            except Exception:
                pv = None
            mv = None
            try:
                mv = round(float(r.get(mc)) / 1e8, 1) if mc and r.get(mc) is not None else None
            except Exception:
                pass
            out[code] = {"date": dt, "pct_float": pv, "mktcap_yi": mv}
        print(f"  A股解禁哨兵(未来{horizon_days}天):全市场 {len(out)} 只有解禁")
        return out
    except Exception as e:
        print(f"  A股解禁哨兵失败(不致命): {str(e)[:60]}")
        return {}


def _cn_close(code):
    """A股前复权日收盘 Series,多源回退:东财 stock_zh_a_hist → 新浪 stock_zh_a_daily → 腾讯 stock_zh_a_hist_tx。
    东财行情接口(push2his)本机/云端都常 RemoteDisconnected,单源易抓空;多源择一成功即拿到当日真值。"""
    import akshare as ak
    pref = ("sh" if code[0] == "6" else "sz") + code     # 新浪/腾讯需交易所前缀

    def s_em():
        df = with_no_proxy(lambda: ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq"))
        return df["收盘"].astype(float).dropna() if (df is not None and "收盘" in df.columns and len(df) >= 30) else None

    def s_sina():
        df = with_no_proxy(lambda: ak.stock_zh_a_daily(symbol=pref, adjust="qfq"))
        return df["close"].astype(float).dropna() if (df is not None and "close" in df.columns and len(df) >= 30) else None

    def s_tx():
        df = with_no_proxy(lambda: ak.stock_zh_a_hist_tx(symbol=pref, adjust="qfq"))
        return df["close"].astype(float).dropna() if (df is not None and "close" in df.columns and len(df) >= 30) else None

    for name, fn in (("东财", s_em), ("新浪", s_sina), ("腾讯", s_tx)):
        try:
            c = fn()
            if c is not None and len(c) >= 30:
                return c
        except Exception:
            continue
    return None


def fetch_one_cn(s):
    """A 股抓取:全程 akshare 直连(行情/技术 + 机构共识 + 新闻),不依赖 Yahoo。
    行情拿不到则抛异常,由上层走逐支回退。"""
    tk = s["ticker"]
    code = tk.split(".")[0]
    rec = {"name": s["name"], "role": s["role"], "market": "CN"}

    c = _with_retry(lambda: _cn_close(code), tk)         # 多源回退拿前复权收盘
    if c is None or len(c) < 30:
        raise RuntimeError("A股行情不足(三源均失败)")
    n = len(c)
    last = float(c.iloc[-1])
    back = lambda d: float(c.iloc[-d - 1]) if n > d else None
    ma = lambda k: round(float(c.tail(k).mean()), 2) if n >= k else None
    win = c.tail(250)
    hi, lo = round(float(win.max()), 2), round(float(win.min()), 2)
    rec.update({
        "price": round(last, 2),
        "m1": pct(last, back(21)), "m3": pct(last, back(63)), "m6": pct(last, back(126)),
        "fromhi": pct(last, hi), "hi": hi, "lo": lo, "ma50": ma(50), "ma200": ma(200), "vol": ann_vol(c),
    })
    cn = cn_consensus(code)
    eps26, eps27 = cn.get("eps_2026"), cn.get("eps_2027")
    fwd_pe = round(last / eps26, 1) if (eps26 and last) else None              # 真·当日前瞻PE(报告PE列失真,弃用)
    eps_growth = round((eps27 / eps26 - 1) * 100, 1) if (eps26 and eps27) else None  # 26→27 EPS 增速
    rec["analyst"] = {"target_mean": None, "target_low": None, "target_high": None,
                      "cn_rating": cn.get("rating"), "n_analysts": cn.get("n_recent_reports"),
                      "cn_reports_total": cn.get("total_reports"), "fwd_pe": fwd_pe,
                      "eps_2026": eps26, "eps_2027": eps27, "eps_growth": eps_growth, "sector": cn.get("sector"),
                      "rating": None, "rating_mean": None}
    rec["earnings_date"] = None
    rec["quality"] = cn_quality(code)     # 财务质量:ROE/经营现金流/毛利(进质量因子)
    rec["news"] = cn_news(code, 3)
    return rec


def _td_symbol(tk, market):
    """Twelve Data 符号:港股用 <code>:HKEX,美股原样。"""
    if market == "HK":
        return tk.replace(".HK", "").lstrip("0") + ":HKEX"
    return tk


def td_fetch_one(s, sess):
    """美股/港股优先用 Twelve Data 取价格+技术面(云端稳定不限流)+ yfinance 尽力补券商一致。
    行情拿不到则抛异常,由上层逐支回退。"""
    tk, market = s["ticker"], s.get("market", "US")
    rec = {"name": s["name"], "role": s["role"], "market": market}
    sym = _td_symbol(tk, market)

    def _hist():
        r = requests.get(f"{TD_BASE}/time_series",
                         params={"symbol": sym, "interval": "1day", "outputsize": 260, "apikey": TD_KEY},
                         timeout=30)
        d = r.json()
        if isinstance(d, dict) and d.get("status") == "error":
            raise RuntimeError(str(d.get("message", ""))[:100])
        vals = d.get("values") if isinstance(d, dict) else None
        return vals if (vals and len(vals) >= 30) else None

    vals = _with_retry(_hist, f"TD:{sym}")
    closes = [float(v["close"]) for v in reversed(vals)]   # 旧→新
    highs = [float(v["high"]) for v in reversed(vals)]
    lows = [float(v["low"]) for v in reversed(vals)]
    n, last = len(closes), float(closes[-1])
    back = lambda d: closes[-d - 1] if n > d else None
    ma = lambda k: round(sum(closes[-k:]) / k, 2) if n >= k else None
    hi, lo = round(max(highs[-250:]), 2), round(min(lows[-250:]), 2)
    rec.update({"price": round(last, 2),
                "m1": pct(last, back(21)), "m3": pct(last, back(63)), "m6": pct(last, back(126)),
                "fromhi": pct(last, hi), "hi": hi, "lo": lo, "ma50": ma(50), "ma200": ma(200), "vol": ann_vol(closes)})
    # 券商一致:yfinance 尽力补(云端常被限,拿不到留 None,不致命)
    an = {"target_mean": None, "target_low": None, "target_high": None, "rating": None,
          "rating_mean": None, "n_analysts": None, "fwd_pe": None, "ttm_pe": None}
    rec["earnings_date"] = None
    rec["news"] = []
    try:
        t = yf.Ticker(tk, session=sess)
        info = t.info or {}
        an.update({"target_mean": info.get("targetMeanPrice"), "target_low": info.get("targetLowPrice"),
                   "target_high": info.get("targetHighPrice"), "rating": info.get("recommendationKey"),
                   "rating_mean": info.get("recommendationMean"), "n_analysts": info.get("numberOfAnalystOpinions"),
                   "fwd_pe": round(info.get("forwardPE"), 1) if info.get("forwardPE") else None})
        rec["earnings_date"] = get_earnings_date(t)   # 尽力补美股财报日(yfinance,云端常被限)
        rec["news"] = get_news(t, 3)                  # 美股新闻催化剂(之前 TD 路径漏了,现补回)
    except Exception:
        pass
    # Finnhub 补强(美股,云端可达不限流):评级/财报日/质量/估值——把美股从"技术分"升到完整"评分"。
    # 优先级高于 yfinance(后者云端常限流返回 None);仅在配了 FINNHUB_KEY 时生效,否则维持现状。
    if FINNHUB_KEY and market == "US" and tk != "QQQ":
        fh = us_finnhub(tk, sess)
        if fh.get("rating_mean") is not None:
            an["rating_mean"] = fh["rating_mean"]
        if fh.get("n_analysts"):
            an["n_analysts"] = fh["n_analysts"]
        if fh.get("cn_rating") and not an.get("target_mean"):   # 无目标价时,用评级词作"共识上行"代理
            an["cn_rating"] = fh["cn_rating"]
        if fh.get("rec_buy_ratio") is not None:
            an["rec_buy_ratio"] = fh["rec_buy_ratio"]
        if fh.get("fwd_pe") is not None and not an.get("fwd_pe"):
            an["fwd_pe"] = fh["fwd_pe"]
        if fh.get("eps_growth") is not None:
            an["eps_growth"] = fh["eps_growth"]
        if fh.get("earnings_date") and not rec.get("earnings_date"):
            rec["earnings_date"] = fh["earnings_date"]
        if fh.get("roe") is not None or fh.get("gross_margin") is not None:
            rec["quality"] = {"roe": fh.get("roe"), "ocf_ps": None,
                              "gross_margin": fh.get("gross_margin"), "period": "TTM·Finnhub"}
        if any(k in fh for k in ("rating_mean", "cn_rating", "fwd_pe")):
            an["consensus_src"] = "Finnhub"
    rec["analyst"] = an
    return rec


def fetch_one(s, sess):
    """单支抓取(套重试)。返回完整 rec(含 price);行情拿不到则抛异常由 _with_retry 处理。"""
    tk = s["ticker"]
    rec = {"name": s["name"], "role": s["role"], "market": s.get("market", "US")}

    def _core():
        t = yf.Ticker(tk, session=sess)  # 直接给 Ticker 传 session
        df = t.history(period="1y", interval="1d", auto_adjust=True)
        c = df["Close"].dropna()
        if len(c) < 30:
            return None  # 空/不足 → 触发重试(常是限流返回空)
        last, n = float(c.iloc[-1]), len(c)
        back = lambda d: float(c.iloc[-d - 1]) if n > d else None
        ma = lambda k: round(float(c.tail(k).mean()), 2) if n >= k else None
        hi, lo = round(float(c.max()), 2), round(float(c.min()), 2)
        r = {
            "price": round(last, 2),
            "m1": pct(last, back(21)), "m3": pct(last, back(63)), "m6": pct(last, back(126)),
            "fromhi": pct(last, hi), "hi": hi, "lo": lo, "ma50": ma(50), "ma200": ma(200), "vol": ann_vol(c),
        }
        info = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}
        r["analyst"] = {
            "target_mean": info.get("targetMeanPrice"),
            "target_low": info.get("targetLowPrice"),
            "target_high": info.get("targetHighPrice"),
            "rating": info.get("recommendationKey"),
            "rating_mean": info.get("recommendationMean"),
            "n_analysts": info.get("numberOfAnalystOpinions"),
            "fwd_pe": round(info.get("forwardPE"), 1) if info.get("forwardPE") else None,
            "ttm_pe": round(info.get("trailingPE"), 1) if info.get("trailingPE") else None,
        }
        r["earnings_date"] = get_earnings_date(t)
        r["news"] = get_news(t, 3)
        return r

    core = _with_retry(_core, tk)  # 仅行情拿不到才算整支失败;info/news 缺失不致命
    rec.update(core)
    return rec


def _last_good_stock(tk):
    """逐支回退:从最近一份(【含】今天已提交的文件)含该支真实价的 data 里取该支记录 + 来源日期。
    关键:必须包含今天的文件——A 股在 GitHub Actions 抓不到(东财拒海外IP),靠复用我本地推的真实值自愈;
    fetch_data 在末尾才写盘,故回退时读到的今天文件是上一次提交的真实版本,不会读到半成品。"""
    files = sorted(glob.glob(os.path.join(STATE, "data_*.json")), reverse=True)
    for fp in files:
        try:
            st = json.load(open(fp, encoding="utf-8")).get("stocks", {})
            r = st.get(tk)
            if r and "price" in r:
                return dict(r), os.path.basename(fp)[5:15]
        except Exception:
            continue
    return None, None


def main():
    os.makedirs(STATE, exist_ok=True)
    cfg = json.load(open(os.path.join(DIR, "config.json"), encoding="utf-8"))
    sess = _session()
    stocks = {}
    for s in cfg["stocks"]:
        tk = s["ticker"]
        mk = s.get("market", "US")
        try:
            if mk == "CN":
                rec = fetch_one_cn(s)              # A股走 akshare 东财(yfinance无A股一致数据)
            elif mk == "US" and TD_KEY:
                rec = td_fetch_one(s, sess)        # 美股走 Twelve Data(免费档仅美股,云端稳定不限流)
            else:
                rec = fetch_one(s, sess)           # 港股/无TD key → yfinance(best-effort,可能被限)
        except Exception as e:
            rec = {"name": s["name"], "role": s["role"], "market": mk, "error": f"抓取失败: {str(e)[:80]}"}
        stocks[tk] = rec
        an = rec.get("analyst", {}) or {}
        print(f"  {tk}: 价 {rec.get('price','?')} · 共识 {an.get('target_mean') or an.get('cn_rating') or '?'} · 新闻 {len(rec.get('news', []))}条")
        # TD 免费档 8 次/分,美股/港股放慢间隔避免超限;A股(akshare)用原间隔
        time.sleep(random.uniform(8, 10) if (TD_KEY and mk != "CN") else random.uniform(*GAP))

    # 逐支回退:本次没抓到价的,各自复用最近一份真实值(含今天已提交的文件)。
    # 来源是更早日期 → 标 stale;来源就是今天(我本地推的真值,如 A 股)→ 视为当日真值不标 stale。
    for tk, rec in list(stocks.items()):
        if "price" not in rec:
            lg, src = _last_good_stock(tk)
            if lg:
                if src and src < TODAY:
                    lg["stale"] = True
                    lg["stale_date"] = src
                stocks[tk] = lg

    # A股财报日:从业绩预约披露日历批量补(一次拉表查所有A股,akshare东财)。云端连不上则保留既有值。
    cn_tks = [s["ticker"] for s in cfg["stocks"] if s.get("market") == "CN"]
    if cn_tks:
        emap = cn_earnings_map()
        umap = cn_unlock_map()                      # A股解禁哨兵(全市场未来6个月)
        for tk in cn_tks:
            code = tk.split(".")[0]
            if emap.get(code) and tk in stocks:
                stocks[tk]["earnings_date"] = emap[code]
            if tk in stocks:
                stocks[tk]["unlock"] = umap.get(code)   # 无未来解禁则 None(=消除隐忧)

    total = len(stocks)
    have = sum(1 for v in stocks.values() if "price" in v)
    stale_tk = [tk for tk, v in stocks.items() if v.get("stale")]
    fresh = sum(1 for v in stocks.values() if "price" in v and not v.get("stale"))
    degraded = len(stale_tk) > 0
    meta = {"degraded": degraded, "fresh": fresh, "have": have, "total": total, "stale_tickers": stale_tk}
    if degraded:
        meta["banner"] = (f"{len(stale_tk)}/{total} 支复用历史真实收盘(取数受限:{'、'.join(stale_tk)}),"
                          f"其余 {fresh}/{total} 为最近真值;价格全真实、非编造,但部分非当日")
    out = {"asof": TODAY, "stocks": stocks, "meta": meta}
    path = os.path.join(STATE, f"data_{TODAY}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{'⚠️ 部分降级' if degraded else '✅'} 有价 {have}/{total}(当日真值 {fresh},复用历史 {len(stale_tk)}) → {path}")


if __name__ == "__main__":
    main()
