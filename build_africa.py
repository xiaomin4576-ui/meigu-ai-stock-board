#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""非洲科技脉搏——把 fetch_africa.py 抓的真实非洲科技/AI 动态渲染成 LUMORA 主题自包含页 state/africa.html。
同光科技在莫桑比克,本板块跟踪整个非洲大陆的科技与 AI 一举一动。
布局(2026-07 参考 AI 早报侧栏改版):左侧【分类(全部/AI基建/AI前沿/科技全景)+ 国家/地区】双维筛选,右侧文章卡片。
诚实纪律:只渲染真实抓到的条目+来源链接;莫桑比克/南部非洲优先;AI 基建单列(光互联需求侧弱信号)。"""
import os, re, json, glob, datetime, html as _html
from collections import Counter

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
_BJ = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
TODAY = _BJ.date().isoformat()
BUILD_TS = _BJ.strftime("%Y-%m-%d %H:%M")

# 南部非洲/莫桑比克优先(同光所在地)——用于卡片排序
PRIOR = ["🇲🇿 莫桑比克", "🇿🇦 南非", "🇦🇴 安哥拉", "🇿🇲 赞比亚", "🇿🇼 津巴布韦"]

# 非洲大区归类(2026-07 用户要左侧按大区分类,比逐国更聚合清晰):国家(带国旗中文名)→ 大区
REGION = {
    "🇲🇿 莫桑比克": "南部非洲", "🇿🇦 南非": "南部非洲", "🇦🇴 安哥拉": "南部非洲",
    "🇿🇲 赞比亚": "南部非洲", "🇿🇼 津巴布韦": "南部非洲",
    "🇰🇪 肯尼亚": "东非", "🇪🇹 埃塞俄比亚": "东非", "🇹🇿 坦桑尼亚": "东非",
    "🇷🇼 卢旺达": "东非", "🇺🇬 乌干达": "东非",
    "🇪🇬 埃及": "北非", "🇲🇦 摩洛哥": "北非",
    "🇳🇬 尼日利亚": "西非", "🇬🇭 加纳": "西非", "🇸🇳 塞内加尔": "西非", "🇨🇮 科特迪瓦": "西非",
}
REGION_ORDER = ["南部非洲", "东非", "北非", "西非"]  # 用户列的顺序;南部非洲=同光所在,优先
REGION_ICON = {"南部非洲": "🧭", "东非": "🌅", "北非": "🏜️", "西非": "🌍"}


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
            f'</ul><div class="snote">🧭 南部非洲(莫桑比克/南非/安哥拉/赞比亚/津巴布韦)= 同光所在,优先关注</div>'
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
</style></head><body>
<div class="wrap">
<div class="nav"><a href="home.html">🏠 首页</a><span class="ts">🕐 {BUILD_TS} 北京</span></div>
<div class="header">
  <h1>🌍 非洲科技脉搏</h1>
  <div class="sub">同光科技立足莫桑比克 · 跟踪整个非洲大陆科技与 AI 的一举一动 · 当日非洲本地媒体 RSS + 2024/2025 历史回填(Google News 按年检索),真实可溯</div>
  <div class="kpis"><div class="kpi"><b>{n_total}</b><span>总条目 · 含24/25</span></div><div class="kpi"><b>{n_infra_meta}</b><span>🏗️ AI 基建</span></div><div class="kpi"><b>{n_ai_meta}</b><span>🤖 AI / 前沿</span></div><div class="kpi"><b>{n_ctry}</b><span>覆盖国家</span></div></div>
</div>
<div class="layout">
{side}
<div class="main-col">
{main_col}
</div>
</div>
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
</script>
</body></html>"""
    os.makedirs(STATE, exist_ok=True)
    out = os.path.join(STATE, "africa.html")
    open(out, "w", encoding="utf-8").write(html_out)
    print(f"✅ 非洲科技脉搏页 → {out}({len(items)} 条 · AI {n_ai_meta} · {n_ctry} 国 · 侧栏 分类+国家双维筛选)")


if __name__ == "__main__":
    main()
