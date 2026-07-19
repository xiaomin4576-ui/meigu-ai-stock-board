#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""非洲科技脉搏采集:为「非洲科技早报」板块抓取整个非洲的科技 / AI 动态。
同光科技在莫桑比克,需跟踪非洲大陆科技与 AI 的一举一动。
信源(逐路容错,一路挂不影响其余;均已实测可达):
  ① 专业科技媒体(全收):TechCabal/Moonshot、Disrupt Africa、Techpoint Africa、IT News Africa、
     TechAfrica News、Condia、ITWeb Africa
  ② 区域综合源(只留科技条目):Club of Mozambique(同光所在地)、Zimbabwe Situation、African Business
  ③ Google News 定向聚合(全网匹配,补中非基建/数据中心/南部非洲跨源新闻):非洲科技、中非科技两路
  (2026-07 扩:原 7 源覆盖不到中非基建/南部非洲,漏了"中国援建津巴布韦数据中心"央视级新闻,故补②③)
去重 + 按时间排序后写 state/africa_raw_<北京日期>.json。
诚实纪律:只存真实抓到的条目与来源链接,抓不到就少,绝不编造(数据真实性规则)。"""
import os, re, json, ssl, html, datetime, urllib.request

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()

# 专业科技媒体 RSS(全部条目收;2026-07 实测可达,死源自动跳过)
TECH_FEEDS = [
    ("TechCabal", "https://techcabal.com/feed/"),
    ("Moonshot·TechCabal", "https://techcabal.com/category/moonshot/feed/"),
    ("Disrupt Africa", "https://disrupt-africa.com/feed/"),
    ("Techpoint Africa", "https://techpoint.africa/feed/"),
    ("IT News Africa", "https://www.itnewsafrica.com/feed/"),
    ("TechAfrica News", "https://techafricanews.com/feed/"),
    ("Condia", "https://www.benjamindada.com/rss/"),
    ("ITWeb Africa", "https://itweb.africa/rss"),
]
# 区域/综合源:补莫桑比克(同光所在地)/津巴布韦/中非基建覆盖,但【只留科技相关条目】,免非科技新闻污染。
# (缘起:2026-07 用户指出"中国援建津巴布韦数据中心"央视级新闻被漏——纯英语科技创业媒体覆盖不到中非基建与南部非洲)
GENERAL_FEEDS = [
    ("Club of Mozambique", "https://clubofmozambique.com/feed/"),
    ("Zimbabwe Situation", "https://www.zimbabwesituation.com/feed/"),
    ("African Business", "https://african.business/feed"),
    # Google News 定向聚合(全网匹配,不受单一媒体最近条目限制;补中非基建/数据中心/南部非洲这类跨源新闻)
    ("非洲科技·聚合", "https://news.google.com/rss/search?q=Africa+(technology+OR+AI+OR+%22data+center%22+OR+startup+OR+fintech+OR+telecom)+when:7d&hl=en-US&gl=US&ceid=US:en"),
    ("中非科技·聚合", "https://news.google.com/rss/search?q=(China+Africa+OR+Huawei+OR+Mozambique+OR+Zimbabwe)+(technology+OR+digital+OR+%22data+center%22+OR+telecom+OR+internet)+when:14d&hl=en-US&gl=US&ceid=US:en"),
]
# 科技强相关词(综合源【只在标题】匹配才收,确保"非洲科技脉搏"不掺非科技新闻——弱词如 payment/platform/app
# 会误收蜂蜜出口/世界杯/讣告,已剔除;保留高置信科技信号)
TECH_KW = ["data cent", "data centre", "数据中心", "technology", "digital", "artificial intel", "telecom",
           "fintech", "5g", "4g", "fibre", "fiber", "broadband", "cloud comput", "huawei", "zte",
           "startup", "software", "mobile money", "e-commerce", "semiconductor", "satellite", "starlink",
           "cyber", "crypto", "blockchain", "科技", "数字经济", "artificial intelligence", "gpu", "smartphone",
           "undersea cable", "connectivity", "electric vehicle", " 5g", "internet ", "chatgpt", "openai"]

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
    ("🇲🇬 马达加斯加", ["madagascar", "antananarivo"]),
    ("🇧🇼 博茨瓦纳", ["botswana", "gaborone"]),
    ("🇳🇦 纳米比亚", ["namibia", "windhoek"]),
    ("🇲🇼 马拉维", ["malawi"]),
    ("🇹🇳 突尼斯", ["tunisia", "tunis"]),
    ("🇩🇿 阿尔及利亚", ["algeria", "algiers"]),
    ("🇧🇯 贝宁", ["benin", "cotonou"]),
    ("🇲🇱 马里", ["mali", "bamako"]),
    ("🇧🇫 布基纳法索", ["burkina faso", "ouagadougou"]),
    ("🇹🇬 多哥", ["togo", "lome"]),
]
# AI / 前沿科技关键词(命中→标 AI 档,优先展示)
AI_KW = ["ai ", " ai", "artificial intelligence", "machine learning", "llm", "genai",
         "generative", "chatgpt", "openai", "anthropic", "data center", "gpu", "chatbot",
         "automation", "算法", "人工智能", "大模型", "deepseek", "nvidia"]
# AI 基础设施建设关键词(物理基建信号:数据中心/海缆/骨干网/超算/落地站/电力配套)——2026-07 用户要求单列。
# 意义:非洲 AI 数据中心/海缆 buildout = 光互联/光模块需求侧,与看板 A/港股 长飞·中天(光纤光缆)存在需求侧关联,
# 是"非洲板块→股票研判"的一条弱信号链(数据中心扩建→上游光缆/光模块订单)。
AIINFRA_KW = ["data center", "data centre", "数据中心", "undersea cable", "subsea cable", "海缆", "submarine cable",
              "hyperscale", "gpu cluster", "supercomput", "超算", "colocation", "landing station", "落地站",
              "internet exchange", "ixp", "backbone", "骨干网", "cloud region", "megawatt", " mw ", "green hydrogen"]


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
    """RSS pubDate → tz-aware datetime(排序用);统一 aware 免 naive/aware 混排崩溃(Google News 用 GMT)。"""
    s = (s or "").strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            continue
    return None


def tag_of(text):
    t = text.lower()
    country = next((c for c, kws in COUNTRIES if any(k in t for k in kws)), None)
    is_ai = any(k in t for k in AI_KW)
    is_aiinfra = any(k in t for k in AIINFRA_KW)   # AI 基建(数据中心/海缆/骨干网…)——单列因子
    return country, is_ai, is_aiinfra


def src_rss(name, url, tech_only=False):
    out = []
    try:
        xml = _get(url)
        for m in re.findall(r"<item>(.*?)</item>", xml, re.S)[:25]:
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", m, re.S)
            l = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", m, re.S)
            d = re.search(r"<pubDate>(.*?)</pubDate>", m, re.S)
            desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", m, re.S)
            title = _clean(t.group(1)) if t else ""
            if not title:
                continue
            brief = _clean(desc.group(1))[:220] if desc else ""
            if tech_only and not any(k in (title + " " + brief).lower() for k in TECH_KW):
                continue   # 综合源:标题+摘要命中【强】科技词才留(强词表已剔弱词,不误收讣告/蜂蜜/世界杯)
            # Google News 聚合:标题是"标题 - 真实媒体",<source>标签有真实源名——提取,显示真实出处
            disp_src = name
            sm = re.search(r"<source[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</source>", m, re.S)
            if sm and "聚合" in name:
                real = _clean(sm.group(1))
                if real:
                    disp_src = f"{real}·聚合"
                    if title.endswith(" - " + real):
                        title = title[: -(len(real) + 3)].strip()
            country, is_ai, is_aiinfra = tag_of(title + " " + brief)
            out.append({"title": title, "brief": brief, "source": disp_src,
                        "url": (l.group(1).strip() if l else ""),
                        "date": (d.group(1).strip() if d else ""),
                        "country": country, "is_ai": is_ai, "is_aiinfra": is_aiinfra})
    except Exception as e:
        print(f"  {name} 失败:{e}")
    return out


def _norm(t):
    return re.sub(r"[^0-9a-zA-Z]", "", t.lower())[:56]


def main():
    os.makedirs(STATE, exist_ok=True)
    cands, counts = [], {}
    for name, url in TECH_FEEDS:
        items = src_rss(name, url, tech_only=False)
        counts[name] = len(items)
        cands += items
        print(f"  {name}: {len(items)} 条")
    for name, url in GENERAL_FEEDS:
        items = src_rss(name, url, tech_only=True)   # 综合源过滤只留科技
        counts[name] = len(items)
        cands += items
        print(f"  {name}(科技过滤): {len(items)} 条")
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
    dedup = dedup[:60]
    n_ai = sum(1 for x in dedup if x["is_ai"])
    n_infra = sum(1 for x in dedup if x.get("is_aiinfra"))
    n_ctry = len({x["country"] for x in dedup if x["country"]})
    out = {"asof": TODAY,
           "fetched_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="minutes"),
           "meta": {"counts": counts, "total": len(dedup), "ai_flagged": n_ai, "aiinfra_flagged": n_infra, "countries": n_ctry},
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
