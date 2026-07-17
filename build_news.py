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

CAT = {"macro": ("🌍 宏观 / 地缘", "影响美股整体:利率 · 关税 · 地缘 · 大宗 · 政策", "#7ab8ff"),
       "oil": ("🛢️ 全球石油 / 能源", "OPEC+ · 油价 · LNG/天然气 · 能源巨头 · 传导视角:莫桑比克/东非能源经营(联合能源 Union)", "#f97316"),
       "tech": ("🤖 科技 / AI 产业", "影响科技板块:财报 · 芯片管制 · AI 监管 · 产业链", "#4ade80")}


def macro_panel():
    """「📅 宏观快线」条:美国宏观(BLS官方)+中美利差+黄金原油实时+社融——蒸馏自艾丽框架的
    '数据三点对照+跨资产观察'缺口补齐。缺哪块显哪块,过期标注,绝不冒充。"""
    files = [f for f in sorted(glob.glob(os.path.join(STATE, "macro_*.json")))
             if re.search(r"macro_\d{4}-\d{2}-\d{2}\.json$", f)]
    if not files:
        return ""
    m = json.load(open(files[-1], encoding="utf-8"))
    b = m.get("blocks", {})
    cells = []
    # 美联储政策利率 EFFR + 下次FOMC(利率是成长股估值锚,放最前)
    fed = b.get("美联储政策", {})
    if "error" not in fed and fed.get("EFFR%") is not None:
        fomc_note = f'距FOMC {esc(fed.get("距FOMC天"))}天' if fed.get("距FOMC天") is not None else esc(fed.get("下次FOMC", ""))
        cells.append(f'<div class="mcell"><div class="mk">联邦基金利率<span class="mp">{esc(fed.get("日期",""))}</span></div>'
                     f'<div class="mv">{esc(fed["EFFR%"])}%</div><div class="ms">前值 {esc(fed.get("前值%","—"))}% · {fomc_note}</div></div>')
    us = b.get("美国宏观", {})
    if "error" not in us:
        for k in ("非农新增(千人)", "失业率%", "CPI同比%"):
            v = us.get(k)
            if v:
                arrow = "" if v.get("前值") is None else (" ↑" if v["值"] > v["前值"] else (" ↓" if v["值"] < v["前值"] else " →"))
                cells.append(f'<div class="mcell"><div class="mk">{esc(k)}<span class="mp">{esc(v.get("期",""))}</span></div>'
                             f'<div class="mv">{esc(v["值"])}{arrow}</div><div class="ms">前值 {esc(v.get("前值","—"))}</div></div>')
    r = b.get("中美利率", {})
    if "error" not in r and r.get("美10Y%"):
        cells.append(f'<div class="mcell"><div class="mk">美/中 10Y<span class="mp">{esc(r.get("日期",""))}</span></div>'
                     f'<div class="mv">{esc(r["美10Y%"])} / {esc(r["中10Y%"])}</div><div class="ms">利差 {esc(r.get("利差bp","—"))}bp</div></div>')
    # 财新制造业PMI(中国制造/算力景气领先指标,50荣枯线)
    pmi = b.get("中国制造业", {})
    if "error" not in pmi and pmi.get("财新制造业PMI") is not None:
        cells.append(f'<div class="mcell"><div class="mk">财新制造业PMI<span class="mp">{esc(pmi.get("数据月份",""))}</span></div>'
                     f'<div class="mv">{esc(pmi["财新制造业PMI"])}</div><div class="ms">{esc(pmi.get("荣枯",""))} · 前值 {esc(pmi.get("前值","—"))}</div></div>')
    c = b.get("大宗实时", {})
    for name in ("纽约黄金", "纽约原油", "美天然气"):
        v = c.get(name) if "error" not in c else None
        if v:
            cells.append(f'<div class="mcell"><div class="mk">{esc(name)}<span class="mp">实时</span></div>'
                         f'<div class="mv">{esc(v["价"])}</div><div class="ms">{"+" if v["涨跌%"]>=0 else ""}{esc(v["涨跌%"])}%</div></div>')
    s = b.get("中国社融", {})
    if "error" not in s and s.get("社融增量(亿)") is not None:
        cells.append(f'<div class="mcell"><div class="mk">中国社融增量<span class="mp">{esc(s.get("数据月份",""))}·滞后源</span></div>'
                     f'<div class="mv">{esc(s["社融增量(亿)"])}亿</div><div class="ms">贷款 {esc(s.get("其中人民币贷款(亿)","—"))}亿</div></div>')
    if not cells:
        return ""
    stale = "" if m.get("asof") == TODAY else f'<span style="color:#fbbf24">(数据抓取于 {esc(m.get("asof"))})</span>'
    return (f'<div class="macro"><div class="mtitle">📅 宏观快线 {stale}'
            f'<span class="msub">纽约联储(EFFR)· BLS · 中债/美债 · 财新PMI · 腾讯外盘(金/油/气)· 三点对照(实际/前值;预期无免费源如实缺)</span></div>'
            f'<div class="mgrid">{"".join(cells)}</div></div>')


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


def _bj_ts(ts):
    """审计F20:发布时间混时区(finnhub 是 UTC ISO +00:00、东财已是北京、RSS 是 RFC822)显示时无标注易误读。
    带时区的 ISO 一律转北京并标"北京";东财本地时间补"北京"标;解析不了的原样截断(不猜不谎标)。"""
    s = str(ts or "").strip()
    if not s:
        return ""
    if "T" in s:
        try:
            dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d %H:%M") + " 北京"
        except Exception:
            pass
    return s[:16] + (" 北京" if re.match(r"\d{4}-\d{2}-\d{2} ", s) else "")


def item_html(rank, it):
    imp = it.get("impact") or "?"
    src = esc(it.get("source"))
    url = str(it.get("url") or "")
    ts = esc(_bj_ts(it.get("ts")))
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
        # 审计F19:序号徽章(irk)承载"档内影响力排名"语义(研判 prompt 硬纪律"各档内按 impact 降序"),
        # 但 items 按模型返回原序未必已排序 → 渲染前按 impact 稳定降序,让徽章排名恒与影响力一致。
        grp = sorted([it for it in items if it.get("cat") == cat], key=lambda it: -(it.get("impact") or 0))
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
body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#0a1020;color:#f2f6fc;line-height:1.6;padding:20px}}
body::before{{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;background:radial-gradient(1100px 520px at 50% -8%,rgba(226,192,126,.10),transparent 62%),radial-gradient(800px 400px at 85% 110%,rgba(122,184,255,.06),transparent 60%)}}
@media(max-width:640px){{body::before{{background:radial-gradient(550px 260px at 50% -8%,rgba(226,192,126,.10),transparent 62%),radial-gradient(400px 200px at 85% 110%,rgba(122,184,255,.06),transparent 60%)}}}}
.wrap{{max-width:980px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#1c2a4a,#101b33);border:1px solid #2f4166;border-radius:16px;padding:24px 28px;margin-bottom:16px}}
.header h1{{font-size:24px;font-weight:900;color:#7ab8ff}}
.sub{{font-size:14px;color:#94a6c4;margin-top:6px}}
.nav{{margin-top:10px;font-size:14px}}.nav a{{color:#7ab8ff;text-decoration:none;font-weight:700;margin-right:14px}}
.fresh{{border-radius:12px;padding:11px 16px;margin-bottom:16px;font-size:14px}}
.fresh.ok{{background:rgba(74,222,128,.08);border:1px solid rgba(74,222,128,.25);color:#4ade80}}
.fresh.stale{{background:rgba(251,146,60,.1);border:1px solid rgba(251,146,60,.35);color:#fbbf24}}
.section{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:16px;font-weight:800;margin:18px 0 12px;padding:10px 14px;background:linear-gradient(90deg,rgba(96,165,250,.12),transparent);border-left:4px solid #7ab8ff;border-radius:8px}}
.ssub{{font-size:12px;font-weight:400;color:#94a6c4}}
.scnt{{margin-left:auto;font-size:12px;font-weight:600;color:#94a6c4;background:rgba(148,163,184,.15);padding:2px 10px;border-radius:10px}}
.item{{background:#1c2a4a;border:1px solid #2f4166;border-radius:13px;padding:14px 17px;margin-bottom:10px}}
.ihd{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
.irk{{font-size:14px;font-weight:900;color:#fbbf24;background:rgba(251,191,36,.12);border-radius:8px;padding:1px 8px}}
.ittl{{font-size:15.5px;font-weight:800;color:#f2f6fc;flex:1;min-width:200px}}
.imp{{font-size:12px;color:#33d6c5;background:rgba(165,180,252,.13);padding:2px 8px;border-radius:10px}}
.ibrief{{font-size:14px;color:#c9d5e8;margin-top:6px}}
.ichain{{font-size:14px;color:#fbbf24;background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.18);border-radius:9px;padding:7px 11px;margin-top:8px}}
.isrc{{font-size:12px;color:#94a6c4;margin-top:7px}}.isrc a{{color:#7ab8ff;text-decoration:none}}
.foot{{text-align:center;font-size:12px;color:#94a6c4;margin-top:20px;line-height:1.8}}
.macro{{background:#101b33;border:1px solid rgba(96,165,250,.35);border-radius:13px;padding:13px 16px;margin-bottom:14px}}
.mtitle{{font-size:14px;font-weight:800;color:#7ab8ff;margin-bottom:9px}}
.msub{{font-size:12px;font-weight:400;color:#94a6c4;margin-left:8px}}
.mgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(138px,1fr));gap:8px}}
.mcell{{background:rgba(51,65,85,.3);border-radius:9px;padding:8px 10px}}
.mk{{font-size:12px;color:#94a6c4}}
.mp{{font-size:9px;color:#94a6c4;margin-left:4px}}
.mv{{font-size:16px;font-weight:800;color:#f2f6fc;margin-top:2px}}
.ms{{font-size:12px;color:#94a6c4}}
.item,.header,.macro{{border-top-color:rgba(226,192,126,.35)}}
.mv{{font-variant-numeric:tabular-nums}}
</style></head><body><div class="wrap">
<div class="header"><div style="font-family:Georgia,serif;font-size:12px;letter-spacing:4px;color:#e2c07e;margin-bottom:8px">LUMORA · 同光科技</div><h1>🌍 全球市场头条 · {news_date}</h1>
<div class="sub">传导链视角:国际局势 → 美股 → A股 · 油气市场 → 莫桑比克/东非经营 · 三档 15-21 条 · 信源 Finnhub / 东财环球 / OilPrice / CNBC / 谷歌定向聚合 等(真实链接可溯源)</div>
<div class="nav"><a href="home.html">🏠 首页</a><button onclick="newsUpd()" style="background:#f97316;color:#fff;border:none;border-radius:8px;padding:4px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit">🔁 刷新头条</button><span id="nupd" style="color:#94a6c4;font-size:12px;margin-left:6px"></span><span style="color:#94a6c4;margin-left:8px">🕐 本页生成 {BUILD_TS} 北京</span></div></div>
<script>
const DT="__DISPATCH_TOKEN__";
async function newsUpd(){{
  const m=document.getElementById('nupd');
  if(!DT||DT.indexOf('__DISPATCH')>=0){{m.textContent='刷新触发未配置';return;}}
  m.textContent='触发中…';
  try{{
    const r=await fetch('https://api.github.com/repos/xiaomin4576-ui/meigu-ai-stock-board/actions/workflows/daily-board.yml/dispatches',{{method:'POST',headers:{{'Authorization':'Bearer '+DT,'Accept':'application/vnd.github+json'}},body:JSON.stringify({{ref:'main',inputs:{{mode:'news'}}}})}});
    if(r.status!==204){{m.textContent='❌ 触发失败('+r.status+')';return;}}
    m.textContent='✅ 已触发,云端构建中(一般5-15分钟)…';
    const t0=Date.now();
    const timer=setInterval(async function(){{
      try{{
        const rr=await fetch('https://api.github.com/repos/xiaomin4576-ui/meigu-ai-stock-board/actions/runs?event=workflow_dispatch&per_page=1',{{headers:{{'Authorization':'Bearer '+DT,'Accept':'application/vnd.github+json'}}}});
        const j=await rr.json();const run=j.workflow_runs&&j.workflow_runs[0];
        const mins=Math.max(1,Math.round((Date.now()-t0)/60000));
        if(run&&run.status==='completed'&&new Date(run.created_at).getTime()>t0-120000){{
          clearInterval(timer);
          if(run.conclusion==='success'){{m.innerHTML='🎉 最新头条已上线!<a href="javascript:void(0)" onclick="location.href=\\'news.html?t=\\'+Date.now()" style="color:#4ade80;font-weight:800">点此加载</a>';}}
          else{{m.textContent='⚠️ 构建结束('+run.conclusion+'),稍后再试';}}
        }}else{{m.textContent='⏳ 云端构建中… 已等 '+mins+' 分钟';}}
      }}catch(e){{}}
    }},20000);
  }}catch(e){{m.textContent='❌ 网络出错';}}
}}
</script>
{fresh}
{macro_panel()}
{secs}
<div class="foot">头条由 AI 从真实信源筛编,「传导链」为推演视角非事实断言 · 仅研究/学习用途,<b>非投资建议</b></div>
</div></body></html>"""
    out = os.path.join(STATE, "news.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out)


if __name__ == "__main__":
    main()
