#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全球头条采集:为「全球市场头条」板块抓取影响美股/科技板块的候选新闻。
三路信源(逐路容错,一路挂不影响其余):
  ① Finnhub 市场新闻(env FINNHUB_KEY,云端 secret 已配;无 key 优雅跳过)
  ② akshare 东财环球财经快讯(A股视角的全球快讯;禁代理直连,同 fetch_data)
  ③ 财经 RSS 兜底(CNBC 国际/科技、Yahoo Finance;框架版 Python 需 certifi)
去重后写 state/news_raw_<北京日期>.json,供 research_news_ds.py(云端)或 Claude(本地)双档研判。
诚实纪律:只存真实抓到的条目与来源链接,抓不到就少,绝不编造。"""
import os, re, json, ssl, html, datetime, threading, urllib.request

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()


def with_no_proxy(fn):
    """临时禁用代理执行 fn(东财需直连;云端无代理时为无害空操作)。与 fetch_data.py 同款。"""
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


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) news-fetcher"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        return r.read().decode("utf-8", "ignore")


def src_finnhub():
    """Finnhub 市场新闻(general 档):headline/summary/source/url/datetime。"""
    key = (os.environ.get("FINNHUB_KEY") or "").strip()
    if not key:
        return []
    out = []
    try:
        data = json.loads(_get(f"https://finnhub.io/api/v1/news?category=general&token={key}"))
        for it in data[:40]:
            if not it.get("headline"):
                continue
            ts = datetime.datetime.fromtimestamp(it.get("datetime", 0), datetime.timezone.utc).isoformat()
            out.append({"title": html.unescape(it["headline"].strip()), "summary": html.unescape((it.get("summary") or "").strip())[:300],
                        "source": it.get("source") or "Finnhub", "url": it.get("url") or "", "ts": ts, "origin": "finnhub"})
    except Exception as e:
        print(f"  finnhub 失败:{e}")
    return out


def _run_with_timeout(fn, seconds):
    """守护线程跑 fn 并限时——akshare 内部 requests 无超时,连接挂起时靠这层止损
    (daemon 线程不阻塞进程退出;审查发现的唯一能击穿 job 预算的敞口)。"""
    box = {}
    def _run():
        try:
            box["v"] = fn()
        except Exception as e:
            box["e"] = e
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(seconds)
    if "v" in box:
        return box["v"]
    raise TimeoutError(box.get("e") or f"超过 {seconds}s 未返回")


def src_akshare_em():
    """东财环球财经快讯(中文,A股视角看全球)。"""
    out = []
    try:
        import akshare as ak
        df = _run_with_timeout(lambda: with_no_proxy(lambda: ak.stock_info_global_em()), 60)
        for _, row in df.head(40).iterrows():
            title = html.unescape(str(row.get("标题") or "").strip())
            if not title:
                continue
            out.append({"title": title, "summary": html.unescape(str(row.get("摘要") or "").strip())[:300],
                        "source": "东方财富·环球", "url": str(row.get("链接") or ""),
                        "ts": str(row.get("发布时间") or ""), "origin": "em"})
    except Exception as e:
        print(f"  akshare 环球快讯失败:{e}")
    return out


RSS_FEEDS = [
    ("CNBC World", "https://www.cnbc.com/id/100727362/device/rss/rss.html"),
    ("CNBC Tech", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    # 石油/能源档专用信源(莫桑比克联合能源Union视角;失败照常单路容错)
    ("OilPrice", "https://oilprice.com/rss/main"),
    ("CNBC Energy", "https://www.cnbc.com/id/19836768/device/rss/rss.html"),
    # 2026-07 扩:原油气源(OilPrice/CNBC)偏全球通用,抓不到莫桑比克/东非天然气专项。补:
    ("Offshore Energy", "https://www.offshore-energy.biz/feed/"),          # LNG/FLNG/上游项目(Golar/TotalEnergies等)
    ("Energy Capital & Power", "https://energycapitalpower.com/feed/"),    # 非洲能源专业媒体
    # Google News 定向聚合:莫桑比克/东非天然气(Rovuma/Cabo Delgado/坦桑LNG)——联合能源 Union 核心关切,全网匹配
    ("莫桑东非能源·聚合", "https://news.google.com/rss/search?q=(Mozambique+OR+%22East+Africa%22+OR+Rovuma+OR+%22Cabo+Delgado%22+OR+Tanzania)+(gas+OR+LNG+OR+oil+OR+energy)+when:14d&hl=en-US&gl=US&ceid=US:en"),
]


def src_rss():
    """财经 RSS 兜底:轻量正则解析 <item>(不引第三方解析库)。"""
    out = []
    for name, url in RSS_FEEDS:
        try:
            xml = _get(url)
            for m in re.findall(r"<item>(.*?)</item>", xml, re.S)[:15]:
                t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", m, re.S)
                l = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", m, re.S)
                d = re.search(r"<pubDate>(.*?)</pubDate>", m, re.S)
                title = html.unescape(t.group(1).strip()) if t else ""
                if not title:
                    continue
                out.append({"title": title, "summary": "", "source": name,
                            "url": (l.group(1).strip() if l else ""), "ts": (d.group(1).strip() if d else ""), "origin": "rss"})
        except Exception as e:
            print(f"  RSS {name} 失败:{e}")
    return out


def _norm(t):
    return re.sub(r"[^0-9a-zA-Z一-鿿]", "", t.lower())[:48]


def main():
    os.makedirs(STATE, exist_ok=True)
    cands, counts = [], {}
    for label, fn in [("finnhub", src_finnhub), ("em", src_akshare_em), ("rss", src_rss)]:
        items = fn()
        counts[label] = len(items)
        cands += items
        print(f"  {label}: {len(items)} 条")
    # 标题归一化去重(保留先到的:finnhub → 东财 → rss)
    seen, dedup = set(), []
    for it in cands:
        k = _norm(it["title"])
        if not k or k in seen:
            continue
        seen.add(k)
        dedup.append(it)
    out = {"asof": TODAY,
           "fetched_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="minutes"),
           "meta": {"counts": counts, "total": len(dedup)},
           "candidates": dedup}
    path = os.path.join(STATE, f"news_raw_{TODAY}.json")
    # 诚实防护:本次一条都没抓到时不覆盖已有真值(保留上次成功抓取)
    if not dedup and os.path.exists(path):
        print(f"⚠️ 本次 0 条,保留已有 {path}")
        return
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 候选 {len(dedup)} 条 → {path}")


if __name__ == "__main__":
    main()
