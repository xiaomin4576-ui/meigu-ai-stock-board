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


def fetch_one(s, sess):
    """单支抓取(套重试)。返回完整 rec(含 price);行情拿不到则抛异常由 _with_retry 处理。"""
    tk = s["ticker"]
    rec = {"name": s["name"], "role": s["role"]}

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


def _load_last_good():
    """扫 state 找最近一份真实健康的 data(排除今天的文件)。文件名带北京日期,字典序=时间序。"""
    today_path = os.path.join(STATE, f"data_{TODAY}.json")
    files = sorted(glob.glob(os.path.join(STATE, "data_*.json")), reverse=True)
    for fp in files:
        if os.path.abspath(fp) == os.path.abspath(today_path):
            continue
        try:
            d = json.load(open(fp, encoding="utf-8"))
            st = d.get("stocks", {})
            ok = sum(1 for v in st.values() if "price" in v)
            if st and ok >= max(1, int(len(st) * DEGRADE_RATIO)):
                return d, d.get("asof") or os.path.basename(fp)[5:15]
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
            rec = fetch_one(s, sess)
        except Exception as e:
            rec = {"name": s["name"], "role": s["role"], "error": f"抓取失败: {str(e)[:80]}"}
        stocks[tk] = rec
        print(f"  {tk}: 价 {rec.get('price','?')} · 一致目标 {rec.get('analyst',{}).get('target_mean','?')} · {rec.get('analyst',{}).get('rating','?')} · 新闻 {len(rec.get('news',[]))}条")
        time.sleep(random.uniform(*GAP))

    total = len(stocks)
    ok = sum(1 for v in stocks.values() if "price" in v)
    path = os.path.join(STATE, f"data_{TODAY}.json")

    # 整体严重失败 → 回退复用最近一份真实 data,绝不用空数据覆盖
    if ok < max(1, int(total * DEGRADE_RATIO)):
        # 优先:磁盘上已有的【今日】文件若本身是真实的(如 Routine/上一跑已抓到),限流时一律保留不覆盖
        if os.path.exists(path):
            try:
                cur = json.load(open(path, encoding="utf-8"))
                cur_ok = sum(1 for v in cur.get("stocks", {}).values() if "price" in v)
                if cur_ok >= max(1, int(total * DEGRADE_RATIO)):
                    print(f"⚠️ 本次抓取受限({ok}/{total}),但磁盘已有今日真实数据({cur_ok}/{total}),保留不覆盖 → {path}")
                    return
            except Exception:
                pass
        last, ddate = _load_last_good()
        if last:
            for v in last.get("stocks", {}).values():
                v["stale"] = True
            out = {
                "asof": TODAY,
                "stocks": last["stocks"],
                "meta": {
                    "degraded": True, "data_date": ddate, "ok": ok, "total": total,
                    "banner": f"数据为 {ddate} 日(云端取数受限,当日仅 {ok}/{total} 支抓取成功,已复用最近一期真实行情)",
                },
            }
            json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"⚠️ 云端取数受限({ok}/{total}),已回退复用 {ddate} 日真实数据 → {path}")
            return
        out = {"asof": TODAY, "stocks": stocks,
               "meta": {"degraded": True, "data_date": None, "ok": ok, "total": total,
                        "banner": f"云端取数受限({ok}/{total}),且无历史数据可回退"}}
        json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"⚠️ 云端取数受限且无可回退数据,写入残缺结果 → {path}")
        return

    # 正常路径:与原逻辑一致(顶层只多一个可选 meta,schema 不变)
    out = {"asof": TODAY, "stocks": stocks,
           "meta": {"degraded": False, "data_date": TODAY, "ok": ok, "total": total}}
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 已拉取 {ok}/{total} 支(行情+机构一致+财报日+新闻) → {path}")


if __name__ == "__main__":
    main()
