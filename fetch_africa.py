#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""非洲科技脉搏采集:为「非洲科技早报」板块抓取整个非洲的科技 / AI 动态。
同光科技在莫桑比克,需跟踪非洲大陆科技与 AI 的一举一动。
信源=非洲本地科技媒体 RSS(逐路容错,一路挂不影响其余;均已实测可达):
  TechCabal / Moonshot(泛非·尼日利亚)、Disrupt Africa(创业)、Techpoint Africa(尼日利亚)、
  IT News Africa(泛非企业科技)、TechAfrica News、Condia(原 Benjamindada·金融科技)。
去重 + 按时间排序后写 state/africa_raw_<北京日期>.json。
诚实纪律:只存真实抓到的条目与来源链接,抓不到就少,绝不编造(数据真实性规则)。"""
import os, re, json, ssl, html, datetime, urllib.request

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()

# 实测可达的非洲科技媒体 RSS(2026-07 验证;死源自动跳过)
FEEDS = [
    ("TechCabal", "https://techcabal.com/feed/"),
    ("Moonshot·TechCabal", "https://techcabal.com/category/moonshot/feed/"),
    ("Disrupt Africa", "https://disrupt-africa.com/feed/"),
    ("Techpoint Africa", "https://techpoint.africa/feed/"),
    ("IT News Africa", "https://www.itnewsafrica.com/feed/"),
    ("TechAfrica News", "https://techafricanews.com/feed/"),
    ("Condia", "https://www.benjamindada.com/rss/"),
]

# 非洲国家/地区识别(标题+摘要命中→标国旗,莫桑比克与南部非洲优先展示)
COUNTRIES = [
    ("🇲🇿 莫桑比克", ["mozambiqu", "maputo", "moçambique"]),
    ("🇿🇦 南非", ["south africa", "johannesburg", "cape town", "pretoria"]),
    ("🇳🇬 尼日利亚", ["nigeria", "lagos", "abuja"]),
    ("🇰🇪 肯尼亚", ["kenya", "nairobi"]),
    ("🇪🇬 埃及", ["egypt", "cairo"]),
    ("🇬🇭 加纳", ["ghana", "accra"]),
    ("🇪🇹 埃塞俄比亚", ["ethiopia", "addis"]),
    ("🇷🇼 卢旺达", ["rwanda", "kigali"]),
    ("🇹🇿 坦桑尼亚", ["tanzania"]),
    ("🇺🇬 乌干达", ["uganda"]),
    ("🇸🇳 塞内加尔", ["senegal", "dakar"]),
    ("🇨🇮 科特迪瓦", ["ivory coast", "côte d", "abidjan"]),
    ("🇦🇴 安哥拉", ["angola", "luanda"]),
    ("🇲🇦 摩洛哥", ["morocco", "casablanca"]),
    ("🇿🇲 赞比亚", ["zambia"]),
    ("🇿🇼 津巴布韦", ["zimbabwe"]),
]
# AI / 前沿科技关键词(命中→标 AI 档,优先展示)
AI_KW = ["ai ", " ai", "artificial intelligence", "machine learning", "llm", "genai",
         "generative", "chatgpt", "openai", "anthropic", "data center", "gpu", "chatbot",
         "automation", "算法", "人工智能", "大模型", "deepseek", "nvidia"]


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) africa-fetcher"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        return r.read().decode("utf-8", "ignore")


def _clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")        # 去 HTML 标签
    return html.unescape(s).strip()


def _parse_date(s):
    """RSS pubDate → date 对象(排序用);解析不出返回 None。"""
    s = (s or "").strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def tag_of(text):
    t = text.lower()
    country = next((c for c, kws in COUNTRIES if any(k in t for k in kws)), None)
    is_ai = any(k in t for k in AI_KW)
    return country, is_ai


def src_rss(name, url):
    out = []
    try:
        xml = _get(url)
        for m in re.findall(r"<item>(.*?)</item>", xml, re.S)[:20]:
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", m, re.S)
            l = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", m, re.S)
            d = re.search(r"<pubDate>(.*?)</pubDate>", m, re.S)
            desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", m, re.S)
            title = _clean(t.group(1)) if t else ""
            if not title:
                continue
            brief = _clean(desc.group(1))[:220] if desc else ""
            country, is_ai = tag_of(title + " " + brief)
            out.append({"title": title, "brief": brief, "source": name,
                        "url": (l.group(1).strip() if l else ""),
                        "date": (d.group(1).strip() if d else ""),
                        "country": country, "is_ai": is_ai})
    except Exception as e:
        print(f"  {name} 失败:{e}")
    return out


def _norm(t):
    return re.sub(r"[^0-9a-zA-Z]", "", t.lower())[:56]


def main():
    os.makedirs(STATE, exist_ok=True)
    cands, counts = [], {}
    for name, url in FEEDS:
        items = src_rss(name, url)
        counts[name] = len(items)
        cands += items
        print(f"  {name}: {len(items)} 条")
    # 标题归一化去重
    seen, dedup = set(), []
    for it in cands:
        k = _norm(it["title"])
        if not k or k in seen:
            continue
        seen.add(k)
        dedup.append(it)
    # 按发布时间倒序(解析不出日期的排最后)
    dedup.sort(key=lambda x: (_parse_date(x["date"]) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)), reverse=True)
    dedup = dedup[:45]
    n_ai = sum(1 for x in dedup if x["is_ai"])
    n_ctry = len({x["country"] for x in dedup if x["country"]})
    out = {"asof": TODAY,
           "fetched_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="minutes"),
           "meta": {"counts": counts, "total": len(dedup), "ai_flagged": n_ai, "countries": n_ctry},
           "items": dedup}
    path = os.path.join(STATE, f"africa_raw_{TODAY}.json")
    # 诚实防护:本次 0 条不覆盖已有真值
    if not dedup and os.path.exists(path):
        print(f"⚠️ 本次 0 条,保留已有 {path}")
        return
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 非洲科技候选 {len(dedup)} 条(AI {n_ai} · {n_ctry} 国)→ {path}")


if __name__ == "__main__":
    main()
