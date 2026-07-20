#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""非洲科技脉搏——把 fetch_africa.py 抓的真实非洲科技/AI 动态渲染成 LUMORA 主题自包含页 state/africa.html。
本板块【主要给同光科技(莫桑比克)做战略决策支持】:实时了解整个非洲科技,服务同光三大产品线
Smart Mine(矿业智慧化·首选灯塔)/ Smart Energy(能源数字化)/ Smart Gov(数字政府)。

2026-07-20 参考同光 AI 世界地图(map.html)大改版,按同光战略裁剪移植三视图 + 三层科技栈分类:
  🌐 全景——【同光三大赛道雷达】+【三层科技栈:基础设施/模型平台/应用行业(子主题节点)】+【竞争雷达:华为/中资 vs 国际】
  🔥 近期焦点——近期条目按【同光战略权重】(矿业+4/能源+3/政府+3/基建+2/AI+2/莫桑+2/华为+2)排序
  🏢 落地案例——动作词识别(投产/签约/落地/launch/deploy/partner)= 谁在非洲真建设 = 竞争&合作情报
  📰 动态 / 📈 趋势——保留原有筛选流与趋势图
数据实体稀疏(非公司提及计数),故用主题/赛道分层(诚实);build 时烘焙,每次 CI 刷新不冻结。
诚实纪律:只渲染真实抓到的条目+来源链接;赛道无料如实留白(如矿业媒体覆盖稀少=情报缺口,本身是决策信号)。"""
import os, re, json, glob, datetime, html as _html
from collections import Counter, OrderedDict

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
_BJ = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
TODAY = _BJ.date().isoformat()
BUILD_TS = _BJ.strftime("%Y-%m-%d %H:%M")

PRIOR = ["🇲🇿 莫桑比克", "🇰🇪 肯尼亚", "🇹🇿 坦桑尼亚", "🇪🇹 埃塞俄比亚"]

REGION = {
    "🇲🇿 莫桑比克": "东非", "🇰🇪 肯尼亚": "东非", "🇪🇹 埃塞俄比亚": "东非",
    "🇹🇿 坦桑尼亚": "东非", "🇷🇼 卢旺达": "东非", "🇺🇬 乌干达": "东非",
    "🇿🇲 赞比亚": "东非", "🇿🇼 津巴布韦": "东非", "🇲🇬 马达加斯加": "东非", "🇲🇼 马拉维": "东非",
    "🇿🇦 南非": "南部非洲", "🇧🇼 博茨瓦纳": "南部非洲", "🇳🇦 纳米比亚": "南部非洲",
    "🇪🇬 埃及": "北非", "🇲🇦 摩洛哥": "北非", "🇹🇳 突尼斯": "北非", "🇩🇿 阿尔及利亚": "北非",
    "🇳🇬 尼日利亚": "西非", "🇬🇭 加纳": "西非", "🇸🇳 塞内加尔": "西非", "🇨🇮 科特迪瓦": "西非",
    "🇧🇯 贝宁": "西非", "🇲🇱 马里": "西非", "🇧🇫 布基纳法索": "西非", "🇹🇬 多哥": "西非",
}
REGION_ORDER = ["东非", "南部非洲", "西非", "北非"]
REGION_ICON = {"东非": "🧭", "南部非洲": "🌍", "西非": "🌐", "北非": "🏜️"}

# ══ 同光战略分层配置(2026-07-20 依据公司汇报书:三大产品线 + 对标华为 + 三层科技栈)══
# 三层科技栈(用户要求「基础设施/模型层/应用层」)——每层拆若干子主题节点,节点按真实条数计。
# 优先级 infra > model > app:一条「AI 数据中心」归基础设施(同光做 IT 基建/数据中心,基建视角优先)。
THEMES = [
    # ① 基础设施层
    ("dc",       "infra", "🖥️ 数据中心",   ["data cent", "data centre", "数据中心", "hyperscale", "colocation", "cloud region", "megawatt", " mw "]),
    ("cable",    "infra", "🌊 海缆·光缆",   ["subsea", "undersea cable", "submarine cable", "海缆", "2africa", "equiano", "cable landing", "landing station", "落地站"]),
    ("mobile",   "infra", "📶 移动网络·5G", ["5g", "4g", "spectrum", "base station", "mobile network", "telecom tower", "lte"]),
    ("backbone", "infra", "🔌 骨干·连接",   ["backbone", "骨干网", "fibre", "fiber", "broadband", "ixp", "internet exchange", "connectivity", "last mile"]),
    ("power",    "infra", "⚡ 电力·能源基建", ["power grid", "electricity", "solar", "renewable energy", "megawatt", "mini-grid", "off-grid", "green hydrogen", "电力"]),
    ("sat",      "infra", "🛰️ 卫星·星链",   ["satellite", "starlink", " leo ", "low earth orbit"]),
    # ② 模型与平台层
    ("llm",      "model", "🧠 大模型·生成式", ["llm", "large language model", "generative ai", "genai", "foundation model", "大模型", "chatgpt", "gpt-", "openai", "anthropic", "gemini"]),
    ("airesearch","model","🔬 AI研究·应用",  ["artificial intelligence", "machine learning", "ai model", "ai research", "ai lab", "instadeep", "lelapa", "人工智能", "算法"]),
    ("compute",  "model", "🎮 算力·GPU",     ["gpu", "nvidia", "supercomput", "算力", "compute cluster", "ai chip", "accelerator"]),
    ("aicloud",  "model", "☁️ AI云·平台",    ["cloud region", "aws", "azure", "google cloud", "ai platform", "cloud service", "microsoft cloud"]),
    # ③ 应用与行业层
    ("fintech",  "app",   "💳 金融科技",     ["fintech", "payment", "mobile money", "m-pesa", "wallet", "lending", "remittance", "neobank", "digital bank"]),
    ("egov",     "app",   "🏛️ 电子政务·数字身份", ["e-gov", "e-government", "govtech", "digital id", "digital identity", "public sector", "electronic government", "电子政务", "数字身份"]),
    ("ecom",     "app",   "🛒 电商·物流",    ["e-commerce", "ecommerce", "marketplace", "logistics", "last-mile delivery", "ride-hail", "mobility"]),
    ("cyber",    "app",   "🔐 网络安全",     ["cybersecurity", "cyber security", "cyberattack", "ransomware", "data breach", "fraud", "网络安全"]),
    ("agri",     "app",   "🌾 农业科技",     ["agritech", "agtech", "agri-tech", "farming tech", "precision agri"]),
    ("crypto",   "app",   "⛓️ 加密·区块链", ["crypto", "blockchain", "web3", "bitcoin", "stablecoin"]),
]
LAYER_META = OrderedDict([
    ("infra", ("① 基础设施层", "数据中心 · 海缆 · 骨干网 · 5G · 电力基建 — 非洲数字化的地基,也是同光 IT 基建/数据中心业务的战场", "#7ab8ff")),
    ("model", ("② 模型与平台层", "大模型 · AI 研究 · 算力 · AI 云 — 非洲仍薄弱,机会在本地化与算力配套", "#b794f6")),
    ("app",   ("③ 应用与行业层", "金融科技 · 电子政务 · 电商 · 安全 · 农业 — 技术落到行业,同光 Smart Gov/垂直应用的竞技场", "#4ade80")),
])

# 同光三大产品线(汇报书优先级:Smart Mine 首选灯塔 > Smart Energy > Smart Gov)
VERTICALS = [
    ("mine",   "⛏️", "Smart Mine · 矿业智慧化", "首选灯塔赛道 · $20亿+ · CAGR 15% · 莫桑石墨全球前五/钽矿世界第一",
     ["mining", "mine ", " mines", "mineral", "cobalt", "lithium", "graphite", "石墨", "tantalum", "钽", "copper mine", "gold min", "extractive", "smart mine", "矿"]),
    ("energy", "⚡", "Smart Energy · 能源数字化", "$9-17亿 · LNG 投资超 $500亿驱动 · 智能电网/数字油气田/智慧能源管理",
     ["energy", "power grid", "electricity", "solar", "renewable", "hydrogen", "lng", "natural gas", "utility", "mini-grid", "off-grid", "oil field", "smart grid", "能源", "电力"]),
    ("gov",    "🏛️", "Smart Gov · 数字政府", "$1.5亿+ · 世行专项赠款 · 数字身份/电子政务/数据中心/网络安全",
     ["government", "e-gov", "e-government", "digital id", "digital identity", "public sector", "govtech", "ministry", "regulator", "national digital", "e-services", "政府", "电子政务"]),
]

# 竞争雷达:同光明确对标华为("华为环伺""在华为反应过来之前")——追踪中资厂商在非动向=直接战略情报
CN_VENDORS = [("华为 Huawei", ["huawei", "华为"]), ("中兴 ZTE", ["zte", "中兴"]),
              ("四达时代 StarTimes", ["startimes", "四达"]), ("传音 Transsion", ["transsion", "传音", "tecno", "itel"]),
              ("中国电信/移动", ["china mobile", "china telecom", "china unicom"])]
INTL_VENDORS = [("Google", ["google "]), ("Microsoft", ["microsoft"]), ("Amazon/AWS", ["amazon", " aws "]),
                ("Meta", ["meta "]), ("Nvidia", ["nvidia"]), ("Equinix", ["equinix"]),
                ("Starlink/SpaceX", ["starlink", "spacex"]), ("Airtel", ["airtel"])]

# 落地案例:动作/交易词(= 谁在非洲真建设/签约/融资 = 竞争与合作情报)
CASE_KW = ["launch", "unveil", "deploy", "go live", "goes live", "rolls out", "roll out", "opens ", " opened",
           "to build", "builds ", "building ", "signs ", "signed ", "partner", "partnership", "acquire", "acquisition",
           "raises ", "raised ", "invest", "funding", "completes", "completed", "expand", "unveils", "inaugurat",
           "投产", "签约", "落地", "上线", "启用", "建成", "揭牌", "开工", "融资", "收购"]


def _region_of(country):
    if not country:
        return "__none"
    return REGION.get(country, "__none")


def _year_of(it):
    if it.get("year"):
        try:
            return int(it["year"])
        except Exception:
            pass
    m = re.search(r"(20\d{2})", str(it.get("date") or ""))
    return int(m.group(1)) if m else None


def _norm2(t):
    return re.sub(r"[^a-z0-9一-鿿]", "", str(t or "").lower())[:64]


def _sortable(it):
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
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.datetime.strptime((s or "").strip(), fmt).strftime("%m-%d")
        except Exception:
            continue
    return (s or "")[:10]


def _strip_tags(s):
    t = _html.unescape(str(s or ""))
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"<[^>]*>?", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) >= 12 else ""


def _txt(it):
    return (str(it.get("title") or "") + " " + str(it.get("brief") or "")).lower()


def _has(it, kws):
    """关键词命中——ASCII 词加【起始词边界】防子串误匹配(经典坑:"mine " 误中 "examine "、
    "ai" 误中 "airtel";词边界只加在起始,允许后缀 mining/mines 仍命中)。CJK 与空格开头词走纯子串。"""
    t = _txt(it)
    for k in kws:
        if not k:
            continue
        if k[0].isascii() and k[0].isalnum():
            if re.search(r"\b" + re.escape(k), t):
                return True
        elif k in t:
            return True
    return False


def _cat_of(it):
    """原三分类(动态视图筛选沿用):AI 基建 > AI 前沿 > 科技全景。"""
    if it.get("is_aiinfra"):
        return "infra"
    if it.get("is_ai"):
        return "ai"
    return "rest"


def _themes_of(it):
    """条目命中的子主题 id 列表(可多)。"""
    return [tid for tid, layer, label, kws in THEMES if _has(it, kws)]


def _layer_of(it):
    """主层归属:infra > model > app > other(基建视角优先,契合同光做数据中心/基建)。"""
    hit = set()
    for tid, layer, label, kws in THEMES:
        if _has(it, kws):
            hit.add(layer)
    if "infra" in hit:
        return "infra"
    if "model" in hit:
        return "model"
    return "app"        # 应用/行业层为兜底:非基建非模型的一般科技/创业/行业新闻都归应用,三层合计恒 100%


def _verticals_of(it):
    return [vid for vid, icon, name, sub, kws in VERTICALS if _has(it, kws)]


def _vendor_has(it, kws):
    """竞争雷达厂商命中——先剔"Google News"聚合源名污染(否则聚合条目的源名把 Google 计数灌高失真)。"""
    t = _txt(it).replace("google news", " ")
    for k in kws:
        if not k:
            continue
        if k[0].isascii() and k[0].isalnum():
            if re.search(r"\b" + re.escape(k), t):
                return True
        elif k in t:
            return True
    return False


def _card(it):
    country = it.get("country") or ""
    reg = _region_of(country)
    yr = _year_of(it) or ""
    cat = _cat_of(it)
    tags = ""
    if country:
        tags += f'<span class="ct">{esc(country)}</span>'
    if it.get("is_aiinfra"):
        tags += '<span class="infra">🏗️ AI基建</span>'
    if it.get("is_ai"):
        tags += '<span class="ai">🤖 AI</span>'
    for vid, icon, name, sub, kws in VERTICALS:
        if _has(it, kws):
            tags += f'<span class="vert v-{vid}">{icon} {esc(name.split(" · ")[1])}</span>'
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


# ─────────────────── 🌐 全景视图 ───────────────────
def _panorama_html(items):
    n = len(items)
    layer_cnt = Counter(_layer_of(x) for x in items)
    n_infra = layer_cnt.get("infra", 0)
    n_model = layer_cnt.get("model", 0)
    n_app = layer_cnt.get("app", 0)
    pct = lambda v: (100 * v // n) if n else 0

    # 洞察框(同光战略视角,基于真实占比动态生成)
    vcounts = {vid: sum(1 for x in items if _has(x, kws)) for vid, icon, name, sub, kws in VERTICALS}
    mine_note = ("矿业赛道非洲科技媒体覆盖极少(仅少量)——这是<b>情报缺口/早期机会</b>信号:同光首选灯塔尚未被媒体照亮,一手渠道更关键。"
                 if vcounts.get("mine", 0) <= 3 else "矿业赛道已有真实动态,重点跟踪。")
    insight = (f'<div class="view-insight"><h3>💡 全景 · 同光战略视角</h3>'
               f'<p>本板块追踪 <strong>{n}</strong> 条非洲科技动态。三层科技栈占比(合计 100%):'
               f'<b style="color:#7ab8ff">基础设施 {pct(n_infra)}%</b> · '
               f'<b style="color:#b794f6">模型/AI {pct(n_model)}%</b> · '
               f'<b style="color:#4ade80">应用/行业 {pct(n_app)}%</b>。'
               f'(模型层为<b>狭义</b>大模型/算力/AI云;数据中心等 AI 基建按基建视角计入基础设施。)'
               f'非洲仍处 <b>基础设施建设期</b>——地基最厚、模型原生层尚薄,同光机会在<b>基建配套 + 行业落地</b>。</p>'
               f'<p class="quote">"在莫桑为莫桑,在非洲为非洲。" 下方【同光三大赛道】按公司战略优先级排列:矿业(首选灯塔)→ 能源 → 数字政府。</p>'
               f'<p style="color:#94a6c4;font-size:12px">🎯 {mine_note}</p></div>')

    # 同光三大赛道雷达
    vcards = ""
    for vid, icon, name, sub, kws in VERTICALS:
        hits = [x for x in items if _has(x, kws)]
        hits.sort(key=_sortable, reverse=True)
        cnt = len(hits)
        latest = ""
        if hits:
            top = hits[0]
            url = top.get("url", "")
            t = esc(top.get("title"))
            tl = f'<a href="{esc(url)}" target="_blank" rel="noopener">{t} ↗</a>' if url.startswith("http") else t
            ctry = f'<span class="vct">{esc(top.get("country"))}</span>' if top.get("country") else ""
            latest = f'<div class="vlatest">最新:{ctry}{tl}</div>'
        else:
            latest = '<div class="vlatest empty">暂无非洲媒体覆盖 —— 情报缺口,需一手渠道补</div>'
        vcards += (f'<div class="vcard v-{vid}" data-theme="vert:{vid}">'
                   f'<div class="vhd"><span class="vicon">{icon}</span><span class="vname">{esc(name)}</span>'
                   f'<span class="vcnt">{cnt}</span></div>'
                   f'<div class="vsub">{esc(sub)}</div>{latest}</div>')
    vband = (f'<div class="strat-band"><div class="sb-title">🎯 同光业务</div>'
             f'<div class="vgrid">{vcards}</div></div>')

    # 三层科技栈(子主题节点)
    stack = ""
    for L, (title, sub, color) in LAYER_META.items():
        nodes = ""
        for tid, layer, label, kws in THEMES:
            if layer != L:
                continue
            c = sum(1 for x in items if _has(x, kws))
            if c == 0:
                continue
            hot = " hot" if c >= 20 else ""
            nodes += f'<div class="node{hot}" data-theme="{tid}" style="border-color:{color}55">{esc(label)}<span class="nmeta">{c}</span></div>'
        if not nodes:
            nodes = '<div style="color:#7e90b0;font-size:12px">本期无数据</div>'
        stack += (f'<div class="layer" style="border-left:3px solid {color}">'
                  f'<div class="layer-t" style="color:{color}">{esc(title)}</div>'
                  f'<div class="layer-s">{esc(sub)}</div>'
                  f'<div class="nodes">{nodes}</div></div>')

    # 竞争雷达
    def _vendor_row(vendors):
        row = ""
        for name, kws in vendors:
            c = sum(1 for x in items if _vendor_has(x, kws))
            if c == 0:
                continue
            row += f'<div class="node" data-theme="vendor:{esc(name)}" style="border-color:#2f4166">{esc(name)}<span class="nmeta">{c}</span></div>'
        return row or '<div style="color:#7e90b0;font-size:12px">本期无数据</div>'
    radar = (f'<div class="layer" style="border-left:3px solid #ff8080;background:rgba(255,128,128,.04)">'
             f'<div class="layer-t" style="color:#ff8080">⚔️ 竞争雷达 · 中资厂商在非动向</div>'
             f'<div class="layer-s">同光战略对标华为——追踪中资科技厂商非洲布局是直接情报(点节点看相关报道)</div>'
             f'<div class="nodes">{_vendor_row(CN_VENDORS)}</div>'
             f'<div class="layer-t" style="color:#94a6c4;margin-top:12px;font-size:13px">🌐 国际云/科技厂商(对照)</div>'
             f'<div class="layer-s">注:国际厂商计数含全球媒体对其非洲业务的报道,量偏高供对照参考</div>'
             f'<div class="nodes">{_vendor_row(INTL_VENDORS)}</div></div>')

    return insight + vband + f'<div class="stack-hd">🗺️ 非洲科技栈 · 三层结构(点子主题看条目)</div>' + stack + radar


# ─────────────────── 🔥 近期焦点 ───────────────────
def _focus_html(items):
    """近期条目按同光战略权重排序。近期=最新年份(当日窗口);战略权重=赛道+层+地缘+竞争。"""
    yrs = [y for y in (_year_of(x) for x in items) if y]
    newest = max(yrs) if yrs else None
    pool = [x for x in items if _year_of(x) == newest] if newest else list(items)
    if len(pool) < 8:                        # 当日太薄则纳入全部,保证有料
        pool = list(items)

    def score(it):
        s = 0.0
        vs = _verticals_of(it)
        if "mine" in vs:
            s += 4                            # 首选灯塔,权重最高
        if "energy" in vs:
            s += 3
        if "gov" in vs:
            s += 3
        L = _layer_of(it)
        if L == "infra":
            s += 2
        if L == "model" or it.get("is_ai"):
            s += 2
        reg = _region_of(it.get("country") or "")
        if it.get("country") == "🇲🇿 莫桑比克":
            s += 2                            # 同光所在
        elif reg == "东非":
            s += 1
        if _has(it, [k for _, kws in CN_VENDORS for k in kws]):
            s += 2                            # 竞争情报
        return s

    ranked = sorted(pool, key=lambda x: (score(x), _sortable(x)), reverse=True)
    top = [x for x in ranked if score(x) > 0][:12]
    if not top:
        top = ranked[:12]

    insight = (f'<div class="view-insight"><h3>🔥 近期焦点 · 为同光战略排序</h3>'
               f'<p>从近期 <strong>{len(pool)}</strong> 条动态中,按<b>同光战略权重</b>'
               f'(⛏️矿业+4 · ⚡能源+3 · 🏛️数字政府+3 · 🏗️基建+2 · 🤖AI+2 · 🇲🇿莫桑+2 · ⚔️华为/中资+2)'
               f'排出最值得关注的 <strong>{len(top)}</strong> 条。「为何关注」标签说明战略相关性。</p></div>')
    cards = ""
    for it in top:
        why = []
        vs = _verticals_of(it)
        for vid, icon, name, sub, kws in VERTICALS:
            if vid in vs:
                why.append(f'<span class="why w-{vid}">{icon} {esc(name.split(" · ")[1])}</span>')
        L = _layer_of(it)
        lm = {"infra": ("🏗️ 基础设施", "#7ab8ff"), "model": ("🤖 模型/AI", "#b794f6"), "app": ("🧩 应用/行业", "#4ade80")}
        if L in lm:
            lb, lc = lm[L]
            why.append(f'<span class="why" style="color:{lc};background:{lc}22">{lb}</span>')
        if it.get("country") == "🇲🇿 莫桑比克":
            why.append('<span class="why w-mz">🇲🇿 同光所在</span>')
        if _has(it, [k for _, kws in CN_VENDORS for k in kws]):
            why.append('<span class="why w-cn">⚔️ 中资动向</span>')
        url = it.get("url", "")
        t = esc(it.get("title"))
        tl = f'<a href="{esc(url)}" target="_blank" rel="noopener">{t} ↗</a>' if url.startswith("http") else t
        ctry = f'<span class="ct">{esc(it.get("country"))}</span>' if it.get("country") else ""
        brief = _strip_tags(it.get("brief"))
        bf = f'<div class="bf">{esc(brief)}</div>' if brief else ""
        cards += (f'<div class="fcard"><div class="fmeta">{ctry}<span class="sc">{esc(it.get("source"))}</span>'
                  f'<span class="dt">{_fmt_date(it.get("date"))}</span></div>'
                  f'<div class="fti">{tl}</div>{bf}<div class="whys">{"".join(why)}</div></div>')
    return insight + (f'<div class="fgrid">{cards}</div>' if cards else '<div class="empty">近期暂无够格条目</div>')


# ─────────────────── 🏢 落地案例 ───────────────────
def _cases_html(items):
    cases = [x for x in items if _has(x, CASE_KW)]
    cases.sort(key=_sortable, reverse=True)
    cases = cases[:18]
    insight = (f'<div class="view-insight"><h3>🏢 落地案例 · 谁在非洲真建设</h3>'
               f'<p>按<b>动作/交易词</b>(投产·签约·落地·融资·launch·deploy·partner·invest…)从全部动态中筛出 '
               f'<strong>{len(cases)}</strong> 条<b>实际发生的项目/合作/交易</b>——这是同光的<b>竞争对手动向 + 潜在合作/入口</b>情报,'
               f'区别于观点评论。点标题看原文。</p></div>')
    cards = ""
    for it in cases:
        url = it.get("url", "")
        t = esc(it.get("title"))
        tl = f'<a href="{esc(url)}" target="_blank" rel="noopener">{t} ↗</a>' if url.startswith("http") else t
        ctry = f'<span class="ct">{esc(it.get("country"))}</span>' if it.get("country") else ""
        vtags = ""
        for vid, icon, name, sub, kws in VERTICALS:
            if _has(it, kws):
                vtags += f'<span class="vert v-{vid}">{icon}</span>'
        cnflag = '<span class="why w-cn">⚔️中资</span>' if _has(it, [k for _, kws in CN_VENDORS for k in kws]) else ""
        brief = _strip_tags(it.get("brief"))
        bf = f'<div class="uses">{esc(brief[:150])}{"…" if len(brief) > 150 else ""}</div>' if brief else ""
        cards += (f'<div class="ccard"><div class="cmeta">{ctry}{vtags}{cnflag}'
                  f'<span class="dt">{_fmt_date(it.get("date"))}</span></div>'
                  f'<div class="cti">{tl}</div>{bf}<div class="csrc">{esc(it.get("source"))}</div></div>')
    return insight + (f'<div class="cgrid">{cards}</div>' if cards else '<div class="empty">暂无动作类条目</div>')


# ─────────────────── 主题→条目(模态弹窗数据) ───────────────────
def _theme_articles(items):
    """构建 主题id/vert:id/vendor:名 → 命中条目列表(供节点点击弹窗)。"""
    out = {}
    def add(key, matcher):
        lst = [x for x in items if matcher(x)]
        lst.sort(key=_sortable, reverse=True)
        out[key] = [{"t": x.get("title"), "u": x.get("url", ""), "c": x.get("country") or "",
                     "d": _fmt_date(x.get("date"))} for x in lst[:15]]
    for tid, layer, label, kws in THEMES:
        add(tid, lambda x, kws=kws: _has(x, kws))
    for vid, icon, name, sub, kws in VERTICALS:
        add("vert:" + vid, lambda x, kws=kws: _has(x, kws))
    for name, kws in CN_VENDORS + INTL_VENDORS:
        add("vendor:" + name, lambda x, kws=kws: _vendor_has(x, kws))
    return out


def _trend_svg(months, monthly):
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
            h = val / tot * plotH
            y -= h
            bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{barw:.1f}" height="{h:.1f}" fill="{color}" rx="1"/>')
        if m.endswith("-01") or m.endswith("-07") or i == 0 or i == len(months) - 1:
            labels.append(f'<text x="{PADL + i * bw + bw / 2:.1f}" y="{H - PADB + 15:.0f}" text-anchor="middle" '
                          f'font-size="8.5" fill="#94a6c4">{m}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:{W}px;height:auto">'
            + "".join(grid) + "".join(bars) + "".join(labels) + '</svg>')


def _timeline_html(ordered):
    groups = OrderedDict()
    for it in ordered:
        ym = _sortable(it)[:7]
        if not ym or ym.startswith("0000"):
            ym = "未标注日期"
        groups.setdefault(ym, []).append(it)
    out = []
    for ym, its in groups.items():
        rows = ""
        for x in its[:30]:
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
    asof = data.get("asof", TODAY)
    fetched = data.get("fetched_at", "")

    hist = []
    hpath = os.path.join(STATE, "africa_history.json")
    if os.path.exists(hpath):
        try:
            hist = json.load(open(hpath, encoding="utf-8")).get("items", [])
        except Exception:
            hist = []
    seen, items = set(), []
    for it in cur + hist:
        k = _norm2(it.get("title"))
        if not k or k in seen:
            continue
        seen.add(k)
        items.append(it)

    infra_items = [x for x in items if x.get("is_aiinfra")]
    ai_items = [x for x in items if x.get("is_ai") and not x.get("is_aiinfra")]
    rest = [x for x in items if not x.get("is_ai") and not x.get("is_aiinfra")]
    ordered = sorted(items, key=_sortable, reverse=True)
    cards = "".join(_card(x) for x in ordered) if ordered else ""

    n_all = len(items)
    n_infra = len(infra_items)
    n_ai = len(ai_items)
    n_rest = len(rest)
    n_hist = len(hist)
    year_counts = Counter(_year_of(x) for x in items if _year_of(x))

    _catkey = {"infra": "infra", "ai": "ai", "rest": "gen"}
    monthly = {}
    for it in items:
        ym = _sortable(it)[:7]
        if not ym or ym.startswith("0000") or ym >= "2026":
            continue
        d = monthly.setdefault(ym, {"total": 0, "ai": 0, "infra": 0, "gen": 0})
        d["total"] += 1
        d[_catkey[_cat_of(it)]] += 1
    months_sorted = sorted(monthly.keys())
    newest_yr = max(year_counts) if year_counts else None
    ykpi = ""
    for y in sorted(year_counts.keys(), reverse=True):
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

    reg_counts = Counter(_region_of(x.get("country") or "") for x in items)
    n_none = reg_counts.get("__none", 0)
    reg_html = "".join(
        f'<li class="fi" data-region="{rg}">{REGION_ICON.get(rg, "🌍")} {rg}<span>{reg_counts.get(rg, 0)}</span></li>'
        for rg in REGION_ORDER)
    none_html = (f'<li class="fi" data-region="__none">🌐 泛非洲 / 未分国<span>{n_none}</span></li>') if n_none else ""

    years_sorted = sorted(year_counts.keys(), reverse=True)
    newest_year = years_sorted[0] if years_sorted else None
    year_html = "".join(
        f'<li class="fi" data-year="{y}">{"🕐 " + str(y) + " · 最近" if y == newest_year else "📅 " + str(y)}<span>{year_counts[y]}</span></li>'
        for y in years_sorted)

    side = (f'<aside class="side">'
            f'<h4>🔎 分类(科技栈层)</h4><ul class="filist" id="catlist">'
            f'<li class="fi active" data-cat="all">📡 全部<span>{n_all}</span></li>'
            f'<li class="fi" data-cat="infra">🏗️ 基础设施(AI基建)<span>{n_infra}</span></li>'
            f'<li class="fi" data-cat="ai">🤖 模型·AI 前沿<span>{n_ai}</span></li>'
            f'<li class="fi" data-cat="rest">🌍 应用·科技全景<span>{n_rest}</span></li>'
            f'</ul>'
            f'<div class="snote">🏗️ 基础设施(数据中心/海缆/骨干网)= 光互联/光模块需求侧,与看板 长飞·中天 存在需求侧关联</div>'
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

    n_total = n_all
    n_ai_meta = len([x for x in items if x.get("is_ai")])
    n_infra_meta = n_infra
    n_ctry = len({x.get("country") for x in items if x.get("country")})

    panorama = _panorama_html(items) if items else '<div class="empty">暂无数据</div>'
    focus = _focus_html(items) if items else '<div class="empty">暂无数据</div>'
    cases = _cases_html(items) if items else '<div class="empty">暂无数据</div>'
    theme_json = json.dumps(_theme_articles(items), ensure_ascii=False)
    # 主题 key → 弹窗标题(节点/赛道/厂商)
    theme_label = {}
    for tid, layer, label, kws in THEMES:
        theme_label[tid] = label
    for vid, icon, name, sub, kws in VERTICALS:
        theme_label["vert:" + vid] = icon + " " + name
    for name, kws in CN_VENDORS + INTL_VENDORS:
        theme_label["vendor:" + name] = "⚔️ " + name if (name, kws) in CN_VENDORS else "🌐 " + name
    theme_label_json = json.dumps(theme_label, ensure_ascii=False)

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
/* 视图切换(5 视图) */
.vtabs{{display:flex;gap:5px;background:#101b33;border:1px solid #2f4166;border-radius:10px;padding:5px;margin-bottom:18px;flex-wrap:wrap}}
.vt{{flex:1;min-width:96px;padding:9px 12px;background:transparent;border:none;border-radius:7px;font-family:inherit;font-size:13.5px;font-weight:600;color:#c9d5e8;cursor:pointer;transition:all .15s;white-space:nowrap}}
.vt:hover{{color:#f2f6fc;background:#1c2a4a}}.vt.active{{background:#e2c07e;color:#0a1020}}
.view{{display:none}}.view.active{{display:block}}
/* 洞察框 */
.view-insight{{background:linear-gradient(180deg,rgba(226,192,126,.07),transparent);border:1px solid rgba(226,192,126,.28);border-radius:12px;padding:15px 19px;margin-bottom:18px}}
.view-insight h3{{font-size:16px;font-weight:800;color:#e2c07e;margin-bottom:7px}}
.view-insight p{{font-size:13px;color:#c9d5e8;line-height:1.7;margin-bottom:5px}}
.view-insight .quote{{font-style:italic;color:#f2f6fc;border-left:3px solid #e2c07e;padding-left:11px;margin:8px 0}}
/* 同光赛道 band */
.strat-band{{margin-bottom:20px}}
.sb-title{{font-size:15px;font-weight:800;color:#e2c07e;margin-bottom:10px}}
.vgrid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}}
@media(max-width:820px){{.vgrid{{grid-template-columns:1fr}}}}
.vcard{{background:#1c2a4a;border:1px solid #2f4166;border-radius:13px;padding:15px 17px;cursor:pointer;transition:all .15s}}
.vcard:hover{{border-color:#e2c07e;transform:translateY(-2px)}}
.vcard.v-mine{{border-top:3px solid #e2c07e}}.vcard.v-energy{{border-top:3px solid #fbbf24}}.vcard.v-gov{{border-top:3px solid #7ab8ff}}
.vhd{{display:flex;align-items:center;gap:8px;margin-bottom:5px}}
.vicon{{font-size:20px}}.vname{{font-size:14.5px;font-weight:800;color:#f2f6fc;flex:1}}
.vcnt{{font-size:16px;font-weight:900;color:#e2c07e;font-variant-numeric:tabular-nums}}
.vsub{{font-size:11.5px;color:#94a6c4;line-height:1.5;margin-bottom:8px}}
.vlatest{{font-size:12.5px;color:#c9d5e8;line-height:1.5;border-top:1px solid #2f4166;padding-top:8px}}
.vlatest a{{color:#7ab8ff;text-decoration:none}}.vlatest.empty{{color:#7e90b0;font-style:italic}}
.vct{{color:#fbbf24;font-weight:700;margin-right:5px}}
/* 科技栈层 */
.stack-hd{{font-size:15px;font-weight:800;color:#33d6c5;margin:6px 2px 12px}}
.layer{{background:#101b33;border:1px solid #2f4166;border-radius:12px;padding:14px 16px;margin-bottom:12px}}
.layer-t{{font-size:14.5px;font-weight:800;margin-bottom:3px}}
.layer-s{{font-size:11.5px;color:#94a6c4;margin-bottom:10px;line-height:1.5}}
.nodes{{display:flex;flex-wrap:wrap;gap:8px}}
.node{{display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:600;color:#c9d5e8;background:#1c2a4a;border:1px solid #2f4166;border-radius:9px;padding:7px 11px;cursor:pointer;transition:all .15s}}
.node:hover{{background:#22345a;color:#f2f6fc;transform:translateY(-1px)}}
.node.hot{{box-shadow:0 0 0 1px rgba(226,192,126,.4)}}
.nmeta{{font-size:12px;font-weight:800;color:#e2c07e;font-variant-numeric:tabular-nums}}
/* 焦点/案例卡片 */
.fgrid,.cgrid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:820px){{.fgrid,.cgrid{{grid-template-columns:1fr}}}}
.fcard,.ccard{{background:#1c2a4a;border:1px solid #2f4166;border-radius:12px;padding:14px 16px}}
.fmeta,.cmeta{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:11.5px;margin-bottom:7px}}
.fti,.cti{{font-size:14.5px;font-weight:700;color:#f2f6fc;line-height:1.5}}
.fti a,.cti a{{color:#f2f6fc;text-decoration:none}}.fti a:hover,.cti a:hover{{color:#7ab8ff}}
.bf,.uses{{font-size:12.5px;color:#94a6c4;margin-top:6px;line-height:1.6}}
.csrc{{font-size:11.5px;color:#7ab8ff;margin-top:7px;font-weight:600}}
.whys{{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px}}
.why{{font-size:11px;font-weight:700;border-radius:20px;padding:2px 9px;color:#c9d5e8;background:rgba(148,163,184,.15)}}
.why.w-mine{{color:#e2c07e;background:rgba(226,192,126,.15)}}.why.w-energy{{color:#fbbf24;background:rgba(251,191,36,.14)}}
.why.w-gov{{color:#7ab8ff;background:rgba(122,184,255,.14)}}.why.w-mz{{color:#fbbf24;background:rgba(251,191,36,.14)}}
.why.w-cn{{color:#ff8080;background:rgba(255,128,128,.14)}}
.vert{{font-size:11px;font-weight:700;border-radius:20px;padding:2px 8px}}
.vert.v-mine{{color:#e2c07e;background:rgba(226,192,126,.15)}}.vert.v-energy{{color:#fbbf24;background:rgba(251,191,36,.14)}}.vert.v-gov{{color:#7ab8ff;background:rgba(122,184,255,.14)}}
/* 通用 */
.layout{{display:grid;grid-template-columns:220px 1fr;gap:20px;align-items:start}}
.side{{position:sticky;top:16px;background:#101b33;border:1px solid #2f4166;border-radius:13px;padding:14px}}
.side h4{{font-size:12px;color:#94a6c4;letter-spacing:.06em;margin-bottom:9px;font-weight:700}}
.filist{{list-style:none;display:flex;flex-direction:column;gap:5px}}
.fi{{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:13px;font-weight:600;color:#c9d5e8;background:#1c2a4a;border:1px solid #2f4166;border-radius:9px;padding:7px 11px;cursor:pointer;transition:all .15s}}
.fi:hover{{background:#22345a;color:#f2f6fc}}
.fi.active{{background:#e2c07e;color:#0a1020;border-color:#e2c07e}}
.fi span{{font-size:11px;font-weight:700;opacity:.75}}
.snote{{font-size:11px;color:#94a6c4;margin-top:9px;line-height:1.55}}
.resbar{{font-size:12.5px;color:#94a6c4;margin-bottom:12px}}.resbar b{{color:#e2c07e}}
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
/* 模态弹窗 */
.mask{{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:center;justify-content:center;z-index:100;padding:20px}}
.mask.show{{display:flex}}
.modal{{background:#101b33;border:1px solid #2f4166;border-radius:14px;padding:22px 24px;max-width:560px;width:100%;max-height:82vh;overflow-y:auto;position:relative}}
.modal h3{{font-size:17px;color:#e2c07e;margin-bottom:4px;padding-right:30px}}
.modal .msub{{font-size:12px;color:#94a6c4;margin-bottom:14px}}
.modal .mrow{{font-size:13px;color:#c9d5e8;border-left:2px solid #2f4166;padding:6px 0 6px 11px;margin-bottom:8px;line-height:1.5}}
.modal .mrow a{{color:#7ab8ff;text-decoration:none}}
.modal .mdt{{font-family:monospace;font-size:11px;color:#7e90b0;margin-right:6px}}
.modal .mclose{{position:absolute;top:14px;right:16px;background:none;border:none;font-size:24px;color:#94a6c4;cursor:pointer;line-height:1}}
.modal .mclose:hover{{color:#f2f6fc}}
</style></head><body>
<div class="wrap">
<div class="nav"><a href="home.html">🏠 门户</a><span class="ts">🕐 {BUILD_TS} 北京</span></div>
<div class="header">
  <h1>🌍 非洲科技脉搏</h1>
  <div class="sub">同光科技(莫桑比克)战略决策仪表盘 · 服务 Smart Mine / Smart Energy / Smart Gov 三大产品线 · 实时了解整个非洲科技 · 真实本地媒体 RSS + 2024/2025 历史回填,可溯源</div>
  <div class="kpis"><div class="kpi"><b>{n_total}</b><span>总条目 · 含24/25</span></div><div class="kpi"><b>{n_infra_meta}</b><span>🏗️ 基础设施</span></div><div class="kpi"><b>{n_ai_meta}</b><span>🤖 AI / 前沿</span></div><div class="kpi"><b>{n_ctry}</b><span>覆盖国家</span></div></div>
</div>
<nav class="vtabs">
  <button class="vt active" data-v="pano">🌐 全景</button>
  <button class="vt" data-v="focus">🔥 近期焦点</button>
  <button class="vt" data-v="cases">🏢 落地案例</button>
  <button class="vt" data-v="feed">📰 动态流</button>
  <button class="vt" data-v="trend">📈 趋势</button>
</nav>
<div class="view active" id="view-pano">{panorama}</div>
<div class="view" id="view-focus">{focus}</div>
<div class="view" id="view-cases">{cases}</div>
<div class="view" id="view-feed">
<div class="layout">
{side}
<div class="main-col">
{main_col}
</div>
</div>
</div>
<div class="view" id="view-trend">{trend_html}</div>
<div class="foot">
  数据源:<b>TechCabal · Techpoint · IT News Africa · TechAfrica News · Condia · ITWeb Africa</b> 等非洲本地科技媒体 + <b>Club of Mozambique · Zimbabwe Situation · African Business</b>(区域综合·只取科技)+ <b>Google News 定向聚合</b>,每次构建实时抓取,链接直达原文可溯<br>
  分层/赛道/竞争标签由关键词自动识别(供决策参考,非精确统计) · 采集时间 {esc(fetched)} 北京 · 仅供研究与学习,非投资建议 · LUMORA · 同光科技
</div>
</div>
<div class="mask" id="mask"><div class="modal"><button class="mclose" onclick="closeM()">×</button><div id="mbody"></div></div></div>
<script>
var TA={theme_json};
var curCat='all', curReg='all', curYear='all';
function _setActive(listId,li){{
  var ul=document.getElementById(listId); if(!ul)return;
  ul.querySelectorAll('.fi').forEach(function(x){{x.classList.remove('active');}});
  li.classList.add('active');
}}
function _applyFilter(){{
  var n=0;
  document.querySelectorAll('#view-feed .item').forEach(function(it){{
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
// 视图切换(5 视图)
document.addEventListener('click',function(e){{
  var vt=e.target.closest?e.target.closest('.vt'):null; if(!vt)return;
  document.querySelectorAll('.vt').forEach(function(x){{x.classList.remove('active');}});
  vt.classList.add('active');
  document.querySelectorAll('.view').forEach(function(x){{x.classList.remove('active');}});
  var t=document.getElementById('view-'+vt.getAttribute('data-v')); if(t)t.classList.add('active');
  window.scrollTo(0,0);
}});
// 节点/赛道卡点击 → 弹窗列出该主题条目
var THEME_LABEL={theme_label_json};
function openM(key){{
  var arts=TA[key]||[];
  var label=THEME_LABEL[key]||key;
  var html='<h3>'+label+'</h3><div class="msub">'+arts.length+' 条相关报道(最新在前)</div>';
  if(!arts.length){{ html+='<div class="mrow" style="border:none;color:#7e90b0">暂无非洲媒体覆盖 —— 情报缺口,建议一手渠道补充</div>'; }}
  arts.forEach(function(a){{
    var ct=a.c?'<span class="ct" style="margin-right:5px">'+esc(a.c)+'</span>':'';
    var link=a.u?('<a href="'+esc(a.u)+'" target="_blank" rel="noopener">'+esc(a.t)+' ↗</a>'):esc(a.t);
    html+='<div class="mrow"><span class="mdt">'+esc(a.d)+'</span>'+ct+link+'</div>';
  }});
  document.getElementById('mbody').innerHTML=html;
  document.getElementById('mask').classList.add('show');
}}
function closeM(){{ document.getElementById('mask').classList.remove('show'); }}
function esc(s){{ return String(s==null?'':s).replace(/[&<>"']/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c];}}); }}
document.addEventListener('click',function(e){{
  var nd=e.target.closest?e.target.closest('[data-theme]'):null;
  if(nd&&!e.target.closest('a')){{ openM(nd.getAttribute('data-theme')); }}
}});
document.addEventListener('click',function(e){{ if(e.target.id==='mask')closeM(); }});
document.addEventListener('keydown',function(e){{ if(e.key==='Escape')closeM(); }});
</script>
</body></html>"""
    os.makedirs(STATE, exist_ok=True)
    out = os.path.join(STATE, "africa.html")
    open(out, "w", encoding="utf-8").write(html_out)
    print(f"✅ 非洲科技脉搏页 → {out}({len(items)} 条 · 全景/焦点/案例/动态/趋势 5 视图 · 三层栈+三赛道+竞争雷达)")


if __name__ == "__main__":
    main()
