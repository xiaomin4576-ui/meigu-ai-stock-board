#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""非洲科技脉搏——把 fetch_africa.py 抓的真实非洲科技/AI 动态渲染成 LUMORA 主题自包含页 state/africa.html。
同光科技在莫桑比克,本板块跟踪整个非洲大陆的科技与 AI 一举一动。
布局(2026-07 参考 AI 早报侧栏改版):左侧【分类(全部/AI基建/AI前沿/科技全景)+ 国家/地区】双维筛选,右侧文章卡片。
诚实纪律:只渲染真实抓到的条目+来源链接;莫桑比克/东非优先(同光所在,UN 地理分区);AI 基建单列(光互联需求侧弱信号)。"""
import os, re, json, glob, datetime, html as _html
from collections import Counter, OrderedDict

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
_BJ = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
TODAY = _BJ.date().isoformat()
BUILD_TS = _BJ.strftime("%Y-%m-%d %H:%M")

# 同光所在(莫桑比克=东非)优先——用于卡片排序
PRIOR = ["🇲🇿 莫桑比克", "🇰🇪 肯尼亚", "🇹🇿 坦桑尼亚", "🇪🇹 埃塞俄比亚"]

# 非洲大区归类(按 UN M49 标准地理分区)。2026-07-17 修正:原把莫桑比克/赞比亚/津巴布韦归"南部非洲"是
# SADC 政经联盟视角、非地理分区;UN 分区里它们属【东非】——与头条"莫桑比克/东非经营"统一。国家(带国旗中文名)→ 大区
REGION = {
    # 东非(Eastern Africa)——莫桑比克(同光所在)、赞比亚、津巴布韦(UN 均属东非)+ 东非高原诸国
    "🇲🇿 莫桑比克": "东非", "🇰🇪 肯尼亚": "东非", "🇪🇹 埃塞俄比亚": "东非",
    "🇹🇿 坦桑尼亚": "东非", "🇷🇼 卢旺达": "东非", "🇺🇬 乌干达": "东非",
    "🇿🇲 赞比亚": "东非", "🇿🇼 津巴布韦": "东非", "🇲🇬 马达加斯加": "东非", "🇲🇼 马拉维": "东非",
    # 南部非洲(Southern Africa, UN)——南非 + 纳米比亚/博茨瓦纳
    "🇿🇦 南非": "南部非洲", "🇧🇼 博茨瓦纳": "南部非洲", "🇳🇦 纳米比亚": "南部非洲",
    # 北非
    "🇪🇬 埃及": "北非", "🇲🇦 摩洛哥": "北非", "🇹🇳 突尼斯": "北非", "🇩🇿 阿尔及利亚": "北非",
    # 西非
    "🇳🇬 尼日利亚": "西非", "🇬🇭 加纳": "西非", "🇸🇳 塞内加尔": "西非", "🇨🇮 科特迪瓦": "西非",
    "🇧🇯 贝宁": "西非", "🇲🇱 马里": "西非", "🇧🇫 布基纳法索": "西非", "🇹🇬 多哥": "西非",
    # 注:安哥拉(🇦🇴)UN 属中非(Middle Africa),数据罕见,不单列中非 → 落"泛非洲/未分国"
}
REGION_ORDER = ["东非", "南部非洲", "西非", "北非"]  # 东非=同光所在(莫桑比克),优先置顶
REGION_ICON = {"东非": "🧭", "南部非洲": "🌍", "西非": "🌐", "北非": "🏜️"}


def _region_of(country):
    """国家 → 大区;无国家或未归类 → __none(泛非洲/未分国)。"""
    if not country:
        return "__none"
    return REGION.get(country, "__none")


def _year_of(it):
    """条目年份(时段筛选用):历史归档带 year 字段;当日抓取从 date 里提 20xx。"""
    if it.get("year"):
        try:
            return int(it["year"])
        except Exception:
            pass
    m = re.search(r"(20\d{2})", str(it.get("date") or ""))
    return int(m.group(1)) if m else None


def _norm2(t):
    """去重归一化(合并历史+当日时按标题去重)。"""
    return re.sub(r"[^a-z0-9一-鿿]", "", str(t or "").lower())[:64]


def _sortable(it):
    """统一成 YYYY-MM-DD 供排序:历史归档是 ISO;当日抓取是 RSS pubDate;都解析不出用年份兜底。"""
    d = str(it.get("date") or "")
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", d)
    if m:
        return m.group(0)
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.datetime.strptime(d.strip(), fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    y = _year_of(it)
    return f"{y}-00-00" if y else "0000-00-00"


def esc(s):
    return _html.escape(str(s or ""), quote=True)


def _fmt_date(s):
    """RSS pubDate → 'MM-DD';解析不出原样截断。"""
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.datetime.strptime((s or "").strip(), fmt).strftime("%m-%d")
        except Exception:
            continue
    return (s or "")[:10]


def _strip_tags(s):
    """RSS description 常混入原始 <a> HTML 或截断的裸链接(尤谷歌聚合项 brief=纯链接)。
    先反转义→去裸URL→去标签(闭合或截断均可)→压空白;只剩碎片(<12字)则返回空,不显示 brief。"""
    t = _html.unescape(str(s or ""))
    t = re.sub(r"https?://\S+", " ", t)   # 去裸/截断 URL
    t = re.sub(r"<[^>]*>?", " ", t)        # 去 HTML 标签(>? 兼容被截断的未闭合标签)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) >= 12 else ""


def _cat_of(it):
    """三分类:AI 基建 > AI 前沿 > 科技全景(与侧栏 data-cat 一致)。"""
    if it.get("is_aiinfra"):
        return "infra"
    if it.get("is_ai"):
        return "ai"
    return "rest"


def _card(it):
    country = it.get("country") or ""
    reg = _region_of(country)                     # 大区筛选维度(南部非洲/东非/北非/西非/__none)
    yr = _year_of(it) or ""                        # 时段筛选维度(2026最近/2025/2024)
    cat = _cat_of(it)
    tags = ""
    if country:
        tags += f'<span class="ct">{esc(country)}</span>'
    if it.get("is_aiinfra"):
        tags += '<span class="infra">🏗️ AI基建</span>'
    if it.get("is_ai"):
        tags += '<span class="ai">🤖 AI</span>'
    src = esc(it.get("source"))
    date = _fmt_date(it.get("date"))
    url = it.get("url", "")
    title = esc(it.get("title"))
    title_html = f'<a href="{esc(url)}" target="_blank" rel="noopener">{title} ↗</a>' if url.startswith("http") else title
    brief_text = _strip_tags(it.get("brief"))
    brief = f'<div class="bf">{esc(brief_text)}</div>' if brief_text else ""
    return (f'<div class="item" data-cat="{cat}" data-region="{esc(reg)}" data-year="{yr}">'
            f'<div class="meta">{tags}<span class="sc">{src}</span><span class="dt">{date}</span></div>'
            f'<div class="ti">{title_html}</div>{brief}</div>')


def _trend_svg(months, monthly):
    """月度【样本构成】·内联 SVG 100%堆叠(零依赖):每月一柱恒满高,按当月三类(AI基建/AI/一般)占比分段。
    (为何是占比不是绝对量:历史按月均匀采样每月≤7,绝对量恒定无意义;占比才能看出每月结构演变——审计建议。)"""
    if not months:
        return '<div class="empty">暂无足够历史数据画趋势(需至少一整年回填)</div>'
    W, H, PADL, PADB, PADT = 840, 220, 34, 44, 12
    plotW, plotH = W - PADL - 10, H - PADB - PADT
    bw = plotW / len(months)
    barw = min(bw * 0.7, 24)
    grid = []
    for g in range(5):
        y = PADT + plotH - (g / 4) * plotH
        grid.append(f'<line x1="{PADL}" y1="{y:.1f}" x2="{W - 10}" y2="{y:.1f}" stroke="#2f4166" stroke-width="0.5"/>'
                    f'<text x="{PADL - 5}" y="{y + 3:.1f}" text-anchor="end" font-size="9" fill="#94a6c4">{g * 25}%</text>')
    bars, labels = [], []
    for i, m in enumerate(months):
        d = monthly[m]
        tot = d["total"] or 1
        x = PADL + i * bw + (bw - barw) / 2
        y = PADT + plotH
        for val, color in ((d["infra"], "#e2c07e"), (d["ai"], "#4ade80"), (d["gen"], "#7ab8ff")):
            if val <= 0:
                continue
            h = val / tot * plotH                     # 占比:当月该类 / 当月总数,恒满高100%
            y -= h
            bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{barw:.1f}" height="{h:.1f}" fill="{color}" rx="1"/>')
        if m.endswith("-01") or m.endswith("-07") or i == 0 or i == len(months) - 1:
            labels.append(f'<text x="{PADL + i * bw + bw / 2:.1f}" y="{H - PADB + 15:.0f}" text-anchor="middle" '
                          f'font-size="8.5" fill="#94a6c4">{m}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:{W}px;height:auto">'
            + "".join(grid) + "".join(bars) + "".join(labels) + '</svg>')


def _timeline_html(ordered):
    """时间线:按月分组(新→旧),每月列具体事件(标题+日期+国家+链接)。借鉴同光趋势页'下半具体时间'。"""
    groups = OrderedDict()
    for it in ordered:                      # ordered 已按日期新→旧
        ym = _sortable(it)[:7]
        if not ym or ym.startswith("0000"):
            ym = "未标注日期"
        groups.setdefault(ym, []).append(it)
    out = []
    for ym, its in groups.items():
        rows = ""
        for x in its[:30]:                  # 每月最多列 30 条,防超长
            ct = f'<span class="ct">{esc(x.get("country"))}</span>' if x.get("country") else ""
            tag = '<span class="infra">🏗️</span>' if x.get("is_aiinfra") else ('<span class="ai">🤖</span>' if x.get("is_ai") else "")
            url = x.get("url", "")
            ti = esc(x.get("title"))
            link = f'<a href="{esc(url)}" target="_blank" rel="noopener" class="tl-ti">{ti} ↗</a>' if url.startswith("http") else f'<span class="tl-ti">{ti}</span>'
            rows += f'<div class="tl-item"><span class="tl-dt">{_fmt_date(x.get("date"))}</span>{ct}{tag}{link}</div>'
        out.append(f'<div class="tl-month"><div class="tl-mh">🗓️ {esc(ym)}<span class="tl-cnt">{len(its)} 条</span></div>{rows}</div>')
    return "".join(out)


def main():
    files = sorted(glob.glob(os.path.join(STATE, "africa_raw_*.json")))
    data = json.load(open(files[-1], encoding="utf-8")) if files else {"items": [], "meta": {}}
    cur = data.get("items", [])
    meta = data.get("meta", {})
    asof = data.get("asof", TODAY)
    fetched = data.get("fetched_at", "")

    # 合并【2024/2025 历史回填 + 当日抓取】,按标题去重(当日优先),解决非洲数据太薄(fetch_africa_history.py 生成归档)
    hist = []
    hpath = os.path.join(STATE, "africa_history.json")
    if os.path.exists(hpath):
        try:
            hist = json.load(open(hpath, encoding="utf-8")).get("items", [])
        except Exception:
            hist = []
    seen, items = set(), []
    for it in cur + hist:                 # 当日在前 → 去重优先保留当日版本
        k = _norm2(it.get("title"))
        if not k or k in seen:
            continue
        seen.add(k)
        items.append(it)

    # 分类计数(全量)
    infra_items = [x for x in items if x.get("is_aiinfra")]
    ai_items = [x for x in items if x.get("is_ai") and not x.get("is_aiinfra")]
    rest = [x for x in items if not x.get("is_ai") and not x.get("is_aiinfra")]
    # 展示排序:按日期新→旧(当日/近期在前,历史在后)
    ordered = sorted(items, key=_sortable, reverse=True)
    cards = "".join(_card(x) for x in ordered) if ordered else ""

    n_all = len(items)
    n_infra = len(infra_items)
    n_ai = len(ai_items)
    n_rest = len(rest)
    n_hist = len(hist)
    # 时段(年份)分布,供时段侧栏(含当日 2026 与历史 2025/2024)
    year_counts = Counter(_year_of(x) for x in items if _year_of(x))

    # ===== 趋势视图数据:月度聚合(堆叠类型)+ 年度 KPI + 时间线 =====
    _catkey = {"infra": "infra", "ai": "ai", "rest": "gen"}
    monthly = {}
    for it in items:
        ym = _sortable(it)[:7]
        # 2026 为当日 RSS 快照(集中本月数十条),口径与历史(每月均匀采样)不一致,不进月度趋势图避免尖峰失真;
        # 当日快照见"动态"视图与下方时间线。趋势图专注 2024-2025 完整两年的均匀月度序列。
        if not ym or ym.startswith("0000") or ym >= "2026":
            continue
        d = monthly.setdefault(ym, {"total": 0, "ai": 0, "infra": 0, "gen": 0})
        d["total"] += 1
        d[_catkey[_cat_of(it)]] += 1
    months_sorted = sorted(monthly.keys())
    newest_yr = max(year_counts) if year_counts else None
    ykpi = ""
    for y in sorted(year_counts.keys(), reverse=True):
        # 年度构成(不给"AI占比%"跨年比:历史是定向回填、当日是全量RSS,口径不同,占比不可比)
        yitems = [x for x in items if _year_of(x) == y]
        ytot = len(yitems)
        yi = sum(1 for x in yitems if x.get("is_aiinfra"))
        ya = sum(1 for x in yitems if x.get("is_ai") and not x.get("is_aiinfra"))
        yg = ytot - yi - ya
        lbl = f"{y} · 当日全量" if y == newest_yr else f"{y} · 定向回填"
        ykpi += f'<div class="ycard"><div class="yy">{lbl}</div><div class="yn">{ytot}</div><div class="ys">🏗️{yi} · 🤖{ya} · 🌐{yg}</div></div>'
    trend_html = (f'<div class="trend-hd">📈 非洲 AI / 科技投入趋势(样本)</div>'
                  f'<div class="trend-sub">共 {n_all} 条 · 上图看月度结构演变、下时间线看具体事件。'
                  f'<b style="color:#fbbf24">口径提示</b>:2024/2025 为按主题定向回填(每月均匀采样),2026 为当日全量 RSS——'
                  f'条数与占比【不宜跨年直接比】,故上图用「占比构成」而非绝对量。</div>'
                  f'<div class="ygrid">{ykpi}</div>'
                  f'<div class="chart-card"><div class="chart-t">📊 2024-2025 月度样本构成(每月三类占比 · 已排除当日快照年)</div>'
                  f'{_trend_svg(months_sorted, monthly)}'
                  f'<div class="clegend"><span><i style="background:#e2c07e"></i>🏗️ AI基建</span>'
                  f'<span><i style="background:#4ade80"></i>🤖 AI</span>'
                  f'<span><i style="background:#7ab8ff"></i>🌐 一般科技</span></div></div>'
                  f'<div class="chart-t" style="margin-top:20px">🗓️ 时间线 · 具体发生的事(按月 · 新→旧)</div>'
                  f'<div class="timeline">{_timeline_html(ordered)}</div>')

    # 大区侧栏(按非洲大区聚合,比逐国更清晰):统计各大区条目数;无国家归"泛非洲/未分国"
    reg_counts = Counter(_region_of(x.get("country") or "") for x in items)
    n_none = reg_counts.get("__none", 0)
    reg_html = "".join(
        f'<li class="fi" data-region="{rg}">{REGION_ICON.get(rg, "🌍")} {rg}<span>{reg_counts.get(rg, 0)}</span></li>'
        for rg in REGION_ORDER)
    none_html = (f'<li class="fi" data-region="__none">🌐 泛非洲 / 未分国<span>{n_none}</span></li>') if n_none else ""

    # 时段侧栏:年份新→旧(最新年=当日"最近");无年份条目不进筛选桶但"全部时段"含之
    years_sorted = sorted(year_counts.keys(), reverse=True)
    newest_year = years_sorted[0] if years_sorted else None
    year_html = "".join(
        f'<li class="fi" data-year="{y}">{"🕐 " + str(y) + " · 最近" if y == newest_year else "📅 " + str(y)}<span>{year_counts[y]}</span></li>'
        for y in years_sorted)

    side = (f'<aside class="side">'
            f'<h4>🔎 分类</h4><ul class="filist" id="catlist">'
            f'<li class="fi active" data-cat="all">📡 全部<span>{n_all}</span></li>'
            f'<li class="fi" data-cat="infra">🏗️ AI 基建<span>{n_infra}</span></li>'
            f'<li class="fi" data-cat="ai">🤖 AI 前沿<span>{n_ai}</span></li>'
            f'<li class="fi" data-cat="rest">🌍 科技全景<span>{n_rest}</span></li>'
            f'</ul>'
            f'<div class="snote">🏗️ AI 基建(数据中心/海缆/骨干网)= 光互联/光模块需求侧,与看板 长飞·中天 存在需求侧关联</div>'
            f'<h4 style="margin-top:16px">🌍 地区(大区)</h4><ul class="filist" id="reglist">'
            f'<li class="fi active" data-region="all">🌍 全部地区<span>{n_all}</span></li>'
            f'{reg_html}{none_html}'
            f'</ul><div class="snote">🧭 东非(莫桑比克=同光所在;含肯尼亚/坦桑/埃塞/卢旺达等,UN 地理分区)= 优先关注</div>'
            f'<h4 style="margin-top:16px">🕐 时段</h4><ul class="filist" id="yearlist">'
            f'<li class="fi active" data-year="all">🌐 全部时段<span>{n_all}</span></li>'
            f'{year_html}'
            f'</ul><div class="snote">2024 / 2025 为历史回填(Google News 按年检索,{n_hist} 条)——补非洲当日数据太薄</div>'
            f'</aside>')

    if not items:
        main_col = ('<div class="empty" style="grid-column:1/-1;padding:40px">暂无非洲科技数据(采集失败或首次运行)。'
                    '数据源=非洲本地科技媒体 RSS,下次构建自动补齐。</div>')
    else:
        main_col = (f'<div class="resbar">显示 <b id="viscount">{n_all}</b> 条 · 点左侧【分类】【地区】【时段】任意组合聚焦</div>'
                    f'<div class="grid" id="cards">{cards}</div>'
                    f'<div class="empty" id="emptymsg" style="display:none">该筛选组合下无匹配条目,换个分类/地区/时段试试</div>')

    # KPI 用合并后(含历史回填)全量口径
    n_total = n_all
    n_ai_meta = len([x for x in items if x.get("is_ai")])
    n_infra_meta = n_infra
    n_ctry = len({x.get("country") for x in items if x.get("country")})

    html_out = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"><meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0">
<title>非洲科技脉搏 · {asof}</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#0a1020;color:#f2f6fc;line-height:1.6;padding:20px}}
body::before{{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;background:radial-gradient(1100px 520px at 50% -8%,rgba(226,192,126,.10),transparent 62%),radial-gradient(800px 400px at 85% 110%,rgba(122,184,255,.06),transparent 60%)}}
@media(max-width:640px){{body{{padding:14px}}body::before{{background:radial-gradient(550px 260px at 50% -8%,rgba(226,192,126,.10),transparent 62%)}}}}
.wrap{{max-width:1180px;margin:0 auto}}
.nav{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:14px;font-size:13px}}
.nav a{{color:#33d6c5;text-decoration:none;font-weight:700;background:rgba(51,214,197,.1);border:1px solid rgba(51,214,197,.3);border-radius:10px;padding:6px 12px}}
.nav .ts{{color:#94a6c4;margin-left:auto}}
.header{{background:linear-gradient(135deg,#1c2a4a,#101b33);border:1px solid #2f4166;border-top-color:rgba(226,192,126,.35);border-radius:16px;padding:22px 24px;margin-bottom:16px}}
.header h1{{font-size:24px;font-weight:900;color:#e2c07e;text-shadow:0 0 20px rgba(226,192,126,.25)}}
.header .sub{{font-size:14px;color:#c9d5e8;margin-top:8px}}
.kpis{{display:flex;flex-wrap:wrap;gap:18px;margin-top:14px;font-variant-numeric:tabular-nums}}
.kpi b{{font-size:22px;color:#f2f6fc;font-weight:800}}.kpi span{{font-size:12px;color:#94a6c4;display:block}}
.layout{{display:grid;grid-template-columns:220px 1fr;gap:20px;align-items:start}}
.side{{position:sticky;top:16px;background:#101b33;border:1px solid #2f4166;border-radius:13px;padding:14px}}
.side h4{{font-size:12px;color:#94a6c4;letter-spacing:.06em;margin-bottom:9px;font-weight:700}}
.filist{{list-style:none;display:flex;flex-direction:column;gap:5px}}
.fi{{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:13px;font-weight:600;color:#c9d5e8;background:#1c2a4a;border:1px solid #2f4166;border-radius:9px;padding:7px 11px;cursor:pointer;transition:all .15s}}
.fi:hover{{background:#22345a;color:#f2f6fc}}
.fi.active{{background:#e2c07e;color:#0a1020;border-color:#e2c07e}}
.fi span{{font-size:11px;font-weight:700;opacity:.75}}
.snote{{font-size:11px;color:#94a6c4;margin-top:9px;line-height:1.55}}
.resbar{{font-size:12.5px;color:#94a6c4;margin-bottom:12px}}
.resbar b{{color:#e2c07e}}
.sec{{font-size:15px;font-weight:800;color:#33d6c5;margin:18px 2px 10px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
.item{{background:#1c2a4a;border:1px solid #2f4166;border-radius:12px;padding:14px 16px}}
.item .meta{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:11.5px;margin-bottom:7px}}
.ct{{color:#fbbf24;background:rgba(251,191,36,.12);border-radius:20px;padding:2px 9px;font-weight:700}}
.ai{{color:#4ade80;background:rgba(74,222,128,.14);border-radius:20px;padding:2px 9px;font-weight:700}}
.infra{{color:#e2c07e;background:rgba(226,192,126,.15);border-radius:20px;padding:2px 9px;font-weight:700}}
.sc{{color:#7ab8ff;font-weight:600}}
.dt{{color:#94a6c4;margin-left:auto}}
.item .ti{{font-size:14.5px;font-weight:700;color:#f2f6fc;line-height:1.5}}
.item .ti a{{color:#f2f6fc;text-decoration:none}}.item .ti a:hover{{color:#7ab8ff}}
.item .bf{{font-size:12.5px;color:#94a6c4;margin-top:6px;line-height:1.6}}
.empty{{color:#94a6c4;font-size:13px;padding:14px;text-align:center;grid-column:1/-1}}
.foot{{margin-top:22px;padding:14px 4px;font-size:12px;color:#94a6c4;line-height:1.8;border-top:1px solid #2f4166}}
.foot b{{color:#c9d5e8}}
@media(max-width:820px){{.layout{{grid-template-columns:1fr}}.side{{position:static}}.filist{{flex-direction:row;flex-wrap:wrap}}.fi{{flex:1;min-width:120px}}}}
/* 视图切换(动态/趋势) */
.aviews{{display:flex;gap:6px;background:#101b33;border:1px solid #2f4166;border-radius:10px;padding:4px;margin-bottom:16px;max-width:320px}}
.av{{flex:1;padding:8px 14px;background:transparent;border:none;border-radius:7px;font-family:inherit;font-size:13.5px;font-weight:600;color:#c9d5e8;cursor:pointer;transition:all .15s}}
.av:hover{{color:#f2f6fc}}.av.active{{background:#e2c07e;color:#0a1020}}
.aview{{display:none}}.aview.active{{display:block}}
/* 趋势视图 */
.trend-hd{{font-size:19px;font-weight:900;color:#e2c07e;margin-bottom:4px}}
.trend-sub{{font-size:12.5px;color:#94a6c4;margin-bottom:16px}}
.ygrid{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px}}
.ycard{{flex:1;min-width:120px;background:#1c2a4a;border:1px solid #2f4166;border-radius:12px;padding:13px 16px}}
.ycard .yy{{font-size:12px;color:#94a6c4;font-weight:700}}
.ycard .yn{{font-size:26px;font-weight:800;color:#f2f6fc;margin:2px 0;font-variant-numeric:tabular-nums}}
.ycard .ys{{font-size:11.5px;color:#4ade80}}
.chart-card{{background:#101b33;border:1px solid #2f4166;border-radius:13px;padding:16px 18px}}
.chart-t{{font-size:14px;font-weight:800;color:#c9d5e8;margin-bottom:10px}}
.clegend{{display:flex;flex-wrap:wrap;gap:16px;margin-top:10px;font-size:12px;color:#94a6c4}}
.clegend span{{display:flex;align-items:center;gap:6px}}
.clegend i{{width:12px;height:12px;border-radius:3px;display:inline-block}}
.timeline{{margin-top:8px}}
.tl-month{{margin-bottom:14px}}
.tl-mh{{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:800;color:#e2c07e;padding:6px 0 8px;border-bottom:1px solid #2f4166;margin-bottom:8px}}
.tl-cnt{{font-size:11px;font-weight:600;color:#94a6c4;background:rgba(148,163,184,.15);padding:1px 9px;border-radius:10px}}
.tl-item{{display:flex;align-items:baseline;flex-wrap:wrap;gap:7px;font-size:13px;padding:4px 0 4px 10px;border-left:2px solid #24344c;margin-bottom:2px}}
.tl-dt{{font-family:monospace;font-size:11px;color:#94a6c4;flex-shrink:0}}
.tl-ti{{color:#c9d5e8;text-decoration:none}}.tl-ti:hover{{color:#7ab8ff}}
</style></head><body>
<div class="wrap">
<div class="nav"><a href="home.html">🏠 首页</a><span class="ts">🕐 {BUILD_TS} 北京</span></div>
<div class="header">
  <h1>🌍 非洲科技脉搏</h1>
  <div class="sub">同光科技立足莫桑比克 · 跟踪整个非洲大陆科技与 AI 的一举一动 · 当日非洲本地媒体 RSS + 2024/2025 历史回填(Google News 按年检索),真实可溯</div>
  <div class="kpis"><div class="kpi"><b>{n_total}</b><span>总条目 · 含24/25</span></div><div class="kpi"><b>{n_infra_meta}</b><span>🏗️ AI 基建</span></div><div class="kpi"><b>{n_ai_meta}</b><span>🤖 AI / 前沿</span></div><div class="kpi"><b>{n_ctry}</b><span>覆盖国家</span></div></div>
</div>
<nav class="aviews"><button class="av active" data-v="feed">📰 动态</button><button class="av" data-v="trend">📈 趋势</button></nav>
<div class="aview active" id="view-feed">
<div class="layout">
{side}
<div class="main-col">
{main_col}
</div>
</div>
</div>
<div class="aview" id="view-trend">{trend_html}</div>
<div class="foot">
  数据源:<b>TechCabal · Techpoint · IT News Africa · TechAfrica News · Condia · ITWeb Africa</b> 等非洲本地科技媒体 + <b>Club of Mozambique · Zimbabwe Situation · African Business</b>(区域综合·只取科技)+ <b>Google News 定向聚合</b>(中非基建/数据中心跨源),每次构建实时抓取,链接直达原文可溯<br>
  采集时间 {esc(fetched)} 北京 · 仅供研究与学习,非投资建议 · LUMORA · 同光科技
</div>
</div>
<script>
var curCat='all', curReg='all', curYear='all';
function _setActive(listId,li){{
  var ul=document.getElementById(listId); if(!ul)return;
  ul.querySelectorAll('.fi').forEach(function(x){{x.classList.remove('active');}});
  li.classList.add('active');
}}
function _applyFilter(){{
  var n=0;
  document.querySelectorAll('.item').forEach(function(it){{
    var okc=(curCat==='all'||it.getAttribute('data-cat')===curCat);
    var okt=(curReg==='all'||it.getAttribute('data-region')===curReg);
    var oky=(curYear==='all'||it.getAttribute('data-year')===curYear);
    var show=okc&&okt&&oky; it.style.display=show?'':'none'; if(show)n++;
  }});
  var vc=document.getElementById('viscount'); if(vc)vc.textContent=n;
  var em=document.getElementById('emptymsg'); if(em)em.style.display=n?'none':'';
}}
document.addEventListener('click',function(e){{
  var li=e.target.closest?e.target.closest('.fi'):null; if(!li)return;
  if(li.hasAttribute('data-cat')){{ curCat=li.getAttribute('data-cat'); _setActive('catlist',li); }}
  else if(li.hasAttribute('data-region')){{ curReg=li.getAttribute('data-region'); _setActive('reglist',li); }}
  else if(li.hasAttribute('data-year')){{ curYear=li.getAttribute('data-year'); _setActive('yearlist',li); }}
  _applyFilter();
}});
// 视图切换:动态(卡片列表) / 趋势(图+时间线)
document.addEventListener('click',function(e){{
  var av=e.target.closest?e.target.closest('.av'):null; if(!av)return;
  document.querySelectorAll('.av').forEach(function(x){{x.classList.remove('active');}});
  av.classList.add('active');
  document.querySelectorAll('.aview').forEach(function(x){{x.classList.remove('active');}});
  var t=document.getElementById('view-'+av.getAttribute('data-v')); if(t)t.classList.add('active');
  window.scrollTo(0,0);
}});
</script>
</body></html>"""
    os.makedirs(STATE, exist_ok=True)
    out = os.path.join(STATE, "africa.html")
    open(out, "w", encoding="utf-8").write(html_out)
    print(f"✅ 非洲科技脉搏页 → {out}({len(items)} 条 · AI {n_ai_meta} · {n_ctry} 国 · 侧栏 分类+国家双维筛选)")


if __name__ == "__main__":
    main()
