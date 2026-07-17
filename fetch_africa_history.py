#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""非洲科技/AI 历史回填(2024+2025)——解决"非洲板块数据太薄"(用户 2026-07 要求,类比股票看板抓历史)。
RSS 本身只有最近条目、无历史存档;改用 Google News RSS search 的 after:/before: 日期操作符按时间区间拉历史。
产出 state/africa_history.json(静态归档,一次性/偶尔重跑即可),build_africa.py 合并【历史+当日】渲染。
诚实纪律:只存真实抓到的条目+可点链接;分类复用 fetch_africa.tag_of(国家/AI/AI基建)。"""
import os, re, json, datetime, html as _html
from urllib.parse import quote
from fetch_africa import _get, tag_of, _norm  # 复用 HTTP + 国家/AI识别 + 去重归一化

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
_BJ = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

# 主题查询(覆盖 AI/数据中心/金融科技/创业/基建等非洲科技面);每条会叠加日期区间
QUERIES = [
    'Africa (AI OR "artificial intelligence" OR "data center" OR datacentre OR "machine learning")',
    'Africa (fintech OR startup OR "digital economy" OR "mobile money") technology',
    '(Mozambique OR "East Africa" OR Nigeria OR Kenya OR "South Africa" OR Egypt OR Ghana) (AI OR tech OR startup OR digital)',
    'Africa ("undersea cable" OR "subsea cable" OR "cloud region" OR 5G OR broadband OR "internet exchange")',
]
# 半年一段拉 2024+2025(Google News search 每次约返回 100 条)
RANGES = [
    ("2024-01-01", "2024-06-30"), ("2024-07-01", "2024-12-31"),
    ("2025-01-01", "2025-06-30"), ("2025-07-01", "2025-12-31"),
]
CAP = 160  # 归档上限(去重后按 AI基建>AI>有国家>其余 优先保留,防页面过载)


def _parse_dt(s):
    """Google News pubDate(RFC822)→ (iso_date, year);解析不出返回 ('', None)。"""
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            d = datetime.datetime.strptime((s or "").strip(), fmt)
            return d.strftime("%Y-%m-%d"), d.year
        except Exception:
            continue
    m = re.search(r"(20\d{2})", s or "")
    return "", (int(m.group(1)) if m else None)


def parse_gnews(xml):
    out = []
    for block in re.findall(r"<item>(.*?)</item>", xml, re.S):
        t = re.search(r"<title>(.*?)</title>", block, re.S)
        l = re.search(r"<link>(.*?)</link>", block, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)
        s = re.search(r"<source[^>]*>(.*?)</source>", block, re.S)
        title = _html.unescape((t.group(1) if t else "").strip())
        url = (l.group(1) if l else "").strip()
        date_iso, year = _parse_dt(d.group(1) if d else "")
        source = _html.unescape((s.group(1) if s else "").strip())
        if title and url.startswith("http"):
            out.append({"title": title, "url": url, "date": date_iso, "year": year, "source": source or "Google News"})
    return out


def main():
    seen, cand = set(), []
    for q in QUERIES:
        for a, b in RANGES:
            url = (f"https://news.google.com/rss/search?q={quote(q)}+after:{a}+before:{b}"
                   f"&hl=en-US&gl=US&ceid=US:en")
            try:
                xml = _get(url, timeout=25)
            except Exception as e:
                print(f"  ⚠️ 抓取失败 [{a}..{b}] {q[:30]}: {e}")
                continue
            got = 0
            for it in parse_gnews(xml):
                key = _norm(it["title"])
                if not key or key in seen:
                    continue
                seen.add(key)
                country, is_ai, is_aiinfra = tag_of(it["title"])
                it.update({"country": country, "is_ai": is_ai, "is_aiinfra": is_aiinfra})
                cand.append(it)
                got += 1
            print(f"  [{a[:7]}..{b[:7]}] {q[:34]}… +{got}")

    # 平衡配额:纯优先级排序会让 is_aiinfra(海缆/数据中心)刷满,失去 AI/金融科技/一般科技的多样性。
    # 改为 AI / AI基建 / 有国家(非AI非基建) 三类各取【新→旧】配额,再合并,保证历史归档跨类均衡。
    def newest(lst, k):
        return sorted(lst, key=lambda x: x.get("date") or "", reverse=True)[:k]
    def by_year(lst, y):
        return [x for x in lst if x.get("year") == y]
    infra = [x for x in cand if x["is_aiinfra"]]
    ai_only = [x for x in cand if x["is_ai"] and not x["is_aiinfra"]]
    ctry_only = [x for x in cand if x["country"] and not x["is_ai"] and not x["is_aiinfra"]]
    # 每类按【年份】再各取配额,保证 2024 与 2025 都覆盖(否则 newest 会被 2025 占满);三类互斥无需去重
    kept = []
    for lst, per_year in ((ai_only, 30), (infra, 25), (ctry_only, 25)):
        for y in (2024, 2025):
            kept += newest(by_year(lst, y), per_year)
    kept.sort(key=lambda x: x.get("date") or "", reverse=True)  # 最终按日期新→旧

    n_ai = sum(1 for x in kept if x["is_ai"])
    n_infra = sum(1 for x in kept if x["is_aiinfra"])
    years = {}
    for x in kept:
        y = x.get("year")
        if y:
            years[str(y)] = years.get(str(y), 0) + 1
    out = {"items": kept, "asof": _BJ.date().isoformat(), "source": "google-news-history",
           "meta": {"total": len(kept), "ai_flagged": n_ai, "aiinfra_flagged": n_infra,
                    "years": years, "candidates_seen": len(cand)}}
    os.makedirs(STATE, exist_ok=True)
    path = os.path.join(STATE, "africa_history.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 非洲历史归档 {len(kept)} 条(候选 {len(cand)} · AI {n_ai} · 基建 {n_infra} · 年份 {years})→ {path}")


if __name__ == "__main__":
    main()
