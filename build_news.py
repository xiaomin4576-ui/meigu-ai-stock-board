#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「全球市场头条」页渲染:读最新 state/news_<date>.json → state/news.html。
双档布局(🌍宏观/地缘 → 🤖科技/AI 产业),每条带「传导链」高亮(事件→美股→A股)。
新鲜度诚实标注:头条非今日则橙色横幅明示。CI 把 news.html 拷进 docs 顶层→自动进加密循环(锁 8888)。"""
import os, re, json, glob, datetime

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
_BJ = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
TODAY = _BJ.date().isoformat()
BUILD_TS = _BJ.strftime("%Y-%m-%d %H:%M")

CAT = {"macro": ("🌍 宏观 / 地缘", "影响美股整体:利率 · 关税 · 地缘 · 大宗 · 政策", "#60a5fa"),
       "oil": ("🛢️ 全球石油 / 能源", "OPEC+ · 油价 · LNG/天然气 · 能源巨头 · 传导视角:莫桑比克/东非能源经营(联合能源 Union)", "#f97316"),
       "tech": ("🤖 科技 / AI 产业", "影响科技板块:财报 · 芯片管制 · AI 监管 · 产业链", "#34d399")}


def latest_news():
    p = os.path.join(STATE, f"news_{TODAY}.json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8")), TODAY
    files = sorted(glob.glob(os.path.join(STATE, "news_*.json")))
    files = [f for f in files if re.search(r"news_\d{4}-\d{2}-\d{2}\.json$", f)]
    if not files:
        return None, None
    m = re.search(r"news_(\d{4}-\d{2}-\d{2})\.json", files[-1])
    return json.load(open(files[-1], encoding="utf-8")), m.group(1)


def esc(s):
    # 引号也要转:url 会进 href="…" 属性,第三方链接含引号时可注入属性(审查已实际复现)
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def item_html(rank, it):
    imp = it.get("impact") or "?"
    src = esc(it.get("source"))
    url = str(it.get("url") or "")
    ts = esc(str(it.get("ts") or "")[:16])
    link = f'<a href="{esc(url)}" target="_blank" rel="noopener">{src} ↗</a>' if url.startswith("http") else src
    return f"""<div class="item">
  <div class="ihd"><span class="irk">{rank}</span><span class="ittl">{esc(it.get('title'))}</span><span class="imp">影响力 {imp}/10</span></div>
  <div class="ibrief">{esc(it.get('brief'))}</div>
  <div class="ichain">🔗 <b>传导链:</b>{esc(it.get('chain'))}</div>
  <div class="isrc">{link} · {ts}</div>
</div>"""


def main():
    news, news_date = latest_news()
    if not news:
        raise SystemExit("缺 state/news_*.json(先跑 fetch_news + research_news)")
    # 新鲜度以内容 asof 为准而非文件名日期——回退研判写今日文件但内容是旧候选时,不许谎标"今日"
    # (与 build_board 的 QA 语料同口径;审查发现的口径不一致)
    news_date = news.get("asof") or news_date
    items = news.get("items", [])
    if news_date == TODAY:
        fresh = f'<div class="fresh ok">🟢 头条为今日(<b>{TODAY}</b>)· 引擎 {esc(news.get("generated_by","?"))} · 生成于 {esc(news.get("generated_at",""))}</div>'
    else:
        days = "?"
        try:
            days = (datetime.date.fromisoformat(TODAY) - datetime.date.fromisoformat(news_date)).days
        except Exception:
            pass
        fresh = f'<div class="fresh stale">🟠 <b>头条仍是 {news_date}({days} 天前)</b>——今日采集/研判未跑通,内容仅供参考</div>'
    secs = ""
    for cat in ("macro", "oil", "tech"):
        grp = [it for it in items if it.get("cat") == cat]
        title, sub, color = CAT[cat]
        secs += f'<div class="section" style="border-left-color:{color}">{title}<span class="ssub">{sub}</span><span class="scnt">{len(grp)} 条</span></div>'
        if grp:
            secs += "".join(item_html(i + 1, it) for i, it in enumerate(grp))
        else:
            secs += '<div class="item"><div class="ibrief">今日该档无够格条目(不凑数,诚实留空)</div></div>'
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"><meta http-equiv="Pragma" content="no-cache">
<title>同光科技 · 全球市场头条 · {news_date}</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#0b1120;color:#e2e8f0;line-height:1.6;padding:20px}}
.wrap{{max-width:980px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid #334155;border-radius:16px;padding:24px 28px;margin-bottom:16px}}
.header h1{{font-size:24px;font-weight:900;color:#60a5fa}}
.sub{{font-size:13px;color:#94a3b8;margin-top:6px}}
.nav{{margin-top:10px;font-size:12.5px}}.nav a{{color:#60a5fa;text-decoration:none;font-weight:700;margin-right:14px}}
.fresh{{border-radius:12px;padding:11px 16px;margin-bottom:16px;font-size:12.5px}}
.fresh.ok{{background:rgba(74,222,128,.08);border:1px solid rgba(74,222,128,.25);color:#bbf7d0}}
.fresh.stale{{background:rgba(251,146,60,.1);border:1px solid rgba(251,146,60,.35);color:#fed7aa}}
.section{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:16px;font-weight:800;margin:18px 0 12px;padding:10px 14px;background:linear-gradient(90deg,rgba(96,165,250,.12),transparent);border-left:4px solid #60a5fa;border-radius:8px}}
.ssub{{font-size:11px;font-weight:400;color:#64748b}}
.scnt{{margin-left:auto;font-size:12px;font-weight:600;color:#94a3b8;background:rgba(148,163,184,.15);padding:2px 10px;border-radius:10px}}
.item{{background:#111a2e;border:1px solid #334155;border-radius:13px;padding:14px 17px;margin-bottom:10px}}
.ihd{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
.irk{{font-size:13px;font-weight:900;color:#fbbf24;background:rgba(251,191,36,.12);border-radius:8px;padding:1px 8px}}
.ittl{{font-size:15.5px;font-weight:800;color:#f1f5f9;flex:1;min-width:200px}}
.imp{{font-size:10.5px;color:#a5b4fc;background:rgba(165,180,252,.13);padding:2px 8px;border-radius:10px}}
.ibrief{{font-size:13px;color:#cbd5e1;margin-top:6px}}
.ichain{{font-size:12.5px;color:#fde68a;background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.18);border-radius:9px;padding:7px 11px;margin-top:8px}}
.isrc{{font-size:11px;color:#64748b;margin-top:7px}}.isrc a{{color:#93c5fd;text-decoration:none}}
.foot{{text-align:center;font-size:11px;color:#475569;margin-top:20px;line-height:1.8}}
</style></head><body><div class="wrap">
<div class="header"><div style="font-family:Georgia,serif;font-size:12px;letter-spacing:4px;color:#c8a562;margin-bottom:8px">LUMORA · 同光科技</div><h1>🌍 全球市场头条 · {news_date}</h1>
<div class="sub">传导链视角:国际局势 → 美股 → A股 · 油气市场 → 莫桑比克/东非经营 · 三档 15-21 条 · 信源 Finnhub / 东财环球 / OilPrice / 财经RSS(真实链接可溯源)</div>
<div class="nav"><a href="index.html">🏠 首页</a><a href="board.html">📡 股票看板</a><a href="ops.html">📊 运营看板</a><button onclick="newsUpd()" style="background:#f97316;color:#fff;border:none;border-radius:8px;padding:4px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit">🔁 刷新头条</button><span id="nupd" style="color:#94a3b8;font-size:12px;margin-left:6px"></span><span style="color:#7c8aa3;margin-left:8px">🕐 本页生成 {BUILD_TS} 北京</span></div></div>
<script>
const DT="__DISPATCH_TOKEN__";
async function newsUpd(){{
  const m=document.getElementById('nupd');
  if(!DT||DT.indexOf('__DISPATCH')>=0){{m.textContent='刷新触发未配置';return;}}
  m.textContent='触发中…';
  try{{
    const r=await fetch('https://api.github.com/repos/xiaomin4576-ui/meigu-ai-stock-board/actions/workflows/daily-board.yml/dispatches',{{method:'POST',headers:{{'Authorization':'Bearer '+DT,'Accept':'application/vnd.github+json'}},body:JSON.stringify({{ref:'main',inputs:{{mode:'news'}}}})}});
    m.textContent = r.status===204 ? '✅ 已触发重抓头条(不动个股研判),约5分钟后刷新本页看最新' : '❌ 触发失败('+r.status+')';
  }}catch(e){{m.textContent='❌ 网络出错';}}
}}
</script>
{fresh}
{secs}
<div class="foot">头条由 AI 从真实信源筛编,「传导链」为推演视角非事实断言 · 仅研究/学习用途,<b>非投资建议</b></div>
</div></body></html>"""
    out = os.path.join(STATE, "news.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out)


if __name__ == "__main__":
    main()
