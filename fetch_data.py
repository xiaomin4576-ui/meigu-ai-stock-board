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
        fwd_pe = None
        pe_col = next((c for c in df.columns if "2026" in c and "市盈率" in c), None)
        if pe_col:
            pes = [float(x) for x in df[pe_col].tolist() if str(x).replace(".", "").replace("-", "").isdigit() and float(x) > 0]
            if pes:
                fwd_pe = round(statistics.median(pes), 1)
        return {"rating": rating, "n_recent_reports": n_recent, "total_reports": int(len(df)), "fwd_pe": fwd_pe}
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


def fetch_one_cn(s):
    """A 股抓取:全程 akshare 直连(行情/技术 + 机构共识 + 新闻),不依赖 Yahoo。
    行情拿不到则抛异常,由上层走逐支回退。"""
    tk = s["ticker"]
    code = tk.split(".")[0]
    rec = {"name": s["name"], "role": s["role"], "market": "CN"}
    import akshare as ak

    def _hist():
        return with_no_proxy(lambda: ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq"))

    df = _with_retry(_hist, tk)
    if df is None or "收盘" not in df.columns or len(df) < 30:
        raise RuntimeError("A股行情不足")
    c = df["收盘"].astype(float).dropna()
    n = len(c)
    last = float(c.iloc[-1])
    back = lambda d: float(c.iloc[-d - 1]) if n > d else None
    ma = lambda k: round(float(c.tail(k).mean()), 2) if n >= k else None
    win = c.tail(250)
    hi, lo = round(float(win.max()), 2), round(float(win.min()), 2)
    rec.update({
        "price": round(last, 2),
        "m1": pct(last, back(21)), "m3": pct(last, back(63)), "m6": pct(last, back(126)),
        "fromhi": pct(last, hi), "hi": hi, "lo": lo, "ma50": ma(50), "ma200": ma(200),
    })
    cn = cn_consensus(code)
    rec["analyst"] = {"target_mean": None, "target_low": None, "target_high": None,
                      "cn_rating": cn.get("rating"), "n_analysts": cn.get("n_recent_reports"),
                      "cn_reports_total": cn.get("total_reports"), "fwd_pe": cn.get("fwd_pe"),
                      "rating": None, "rating_mean": None}
    rec["earnings_date"] = None
    rec["news"] = cn_news(code, 3)
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
            "fromhi": pct(last, hi), "hi": hi, "lo": lo, "ma50": ma(50), "ma200": ma(200),
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
        try:
            rec = fetch_one_cn(s) if s.get("market") == "CN" else fetch_one(s, sess)  # A股走akshare,美股走yfinance
        except Exception as e:
            rec = {"name": s["name"], "role": s["role"], "market": s.get("market", "US"),
                   "error": f"抓取失败: {str(e)[:80]}"}
        stocks[tk] = rec
        an = rec.get("analyst", {}) or {}
        print(f"  {tk}: 价 {rec.get('price','?')} · 共识 {an.get('target_mean') or an.get('cn_rating') or '?'} · 新闻 {len(rec.get('news', []))}条")
        time.sleep(random.uniform(*GAP))

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
