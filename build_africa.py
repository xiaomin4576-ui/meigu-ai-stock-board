#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""非洲科技脉搏——把 fetch_africa.py 抓的真实非洲科技/AI 动态渲染成 LUMORA 主题自包含页 state/africa.html。
同光科技在莫桑比克,本板块跟踪整个非洲大陆的科技与 AI 一举一动。
诚实纪律:只渲染真实抓到的条目+来源链接;莫桑比克/南部非洲优先;AI 档单列。"""
import os, re, json, glob, datetime, html as _html

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
_BJ = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
TODAY = _BJ.date().isoformat()
BUILD_TS = _BJ.strftime("%Y-%m-%d %H:%M")


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


def _card(it):
    country = it.get("country")
    tags = ""
    if country:
        tags += f'<span class="ct">{esc(country)}</span>'
    if it.get("is_ai"):
        tags += '<span class="ai">🤖 AI</span>'
    src = esc(it.get("source"))
    date = _fmt_date(it.get("date"))
    url = it.get("url", "")
    title = esc(it.get("title"))
    title_html = f'<a href="{esc(url)}" target="_blank" rel="noopener">{title} ↗</a>' if url.startswith("http") else title
    brief = f'<div class="bf">{esc(it.get("brief"))}</div>' if it.get("brief") else ""
    return (f'<div class="item">'
            f'<div class="meta">{tags}<span class="sc">{src}</span><span class="dt">{date}</span></div>'
            f'<div class="ti">{title_html}</div>{brief}</div>')


def main():
    files = sorted(glob.glob(os.path.join(STATE, "africa_raw_*.json")))
    data = json.load(open(files[-1], encoding="utf-8")) if files else {"items": [], "meta": {}}
    items = data.get("items", [])
    meta = data.get("meta", {})
    asof = data.get("asof", TODAY)
    fetched = data.get("fetched_at", "")

    ai_items = [x for x in items if x.get("is_ai")]
    rest = [x for x in items if not x.get("is_ai")]
    # 莫桑比克/南部非洲优先置顶(同光所在地)
    PRIOR = ("🇲🇿", "🇿🇦", "🇦🇴", "🇿🇲", "🇿🇼")
    rest.sort(key=lambda x: 0 if (x.get("country") or "")[:1] and any((x.get("country") or "").startswith(p) for p in PRIOR) else 1)

    ai_html = ("".join(_card(x) for x in ai_items)) if ai_items else '<div class="empty">本期无 AI 前沿条目命中</div>'
    rest_html = ("".join(_card(x) for x in rest)) if rest else '<div class="empty">暂无更多条目</div>'

    if not items:
        body = ('<div class="empty" style="grid-column:1/-1;padding:40px">暂无非洲科技数据(采集失败或首次运行)。'
                '数据源=非洲本地科技媒体 RSS,下次构建自动补齐。</div>')
    else:
        body = (f'<div class="sec">🤖 AI / 前沿科技 <span class="cnt">{len(ai_items)}</span></div>'
                f'<div class="grid">{ai_html}</div>'
                f'<div class="sec">📡 非洲科技全景(莫桑比克 / 南部非洲优先) <span class="cnt">{len(rest)}</span></div>'
                f'<div class="grid">{rest_html}</div>')

    n_total = meta.get("total", len(items))
    n_ai = meta.get("ai_flagged", len(ai_items))
    n_ctry = meta.get("countries", 0)

    html_out = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"><meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0">
<title>非洲科技脉搏 · {asof}</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#0a1020;color:#f2f6fc;line-height:1.6;padding:20px}}
body::before{{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;background:radial-gradient(1100px 520px at 50% -8%,rgba(226,192,126,.10),transparent 62%),radial-gradient(800px 400px at 85% 110%,rgba(122,184,255,.06),transparent 60%)}}
@media(max-width:640px){{body{{padding:14px}}body::before{{background:radial-gradient(550px 260px at 50% -8%,rgba(226,192,126,.10),transparent 62%)}}}}
.wrap{{max-width:1100px;margin:0 auto}}
.nav{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:14px;font-size:13px}}
.nav a{{color:#33d6c5;text-decoration:none;font-weight:700;background:rgba(51,214,197,.1);border:1px solid rgba(51,214,197,.3);border-radius:10px;padding:6px 12px}}
.nav a.o{{color:#7ab8ff;background:rgba(122,184,255,.1);border-color:rgba(122,184,255,.3)}}
.nav .ts{{color:#94a6c4;margin-left:auto}}
.header{{background:linear-gradient(135deg,#1c2a4a,#101b33);border:1px solid #2f4166;border-top-color:rgba(226,192,126,.35);border-radius:16px;padding:22px 24px;margin-bottom:16px}}
.header h1{{font-size:24px;font-weight:900;color:#e2c07e;text-shadow:0 0 20px rgba(226,192,126,.25)}}
.header .sub{{font-size:14px;color:#c9d5e8;margin-top:8px}}
.kpis{{display:flex;flex-wrap:wrap;gap:18px;margin-top:14px;font-variant-numeric:tabular-nums}}
.kpi b{{font-size:22px;color:#f2f6fc;font-weight:800}}.kpi span{{font-size:12px;color:#94a6c4;display:block}}
.sec{{font-size:15px;font-weight:800;color:#33d6c5;margin:18px 2px 10px}}
.sec .cnt{{font-size:12px;color:#94a6c4;font-weight:600;margin-left:6px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:720px){{.grid{{grid-template-columns:1fr}}}}
.item{{background:#1c2a4a;border:1px solid #2f4166;border-radius:12px;padding:14px 16px}}
.item .meta{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:11.5px;margin-bottom:7px}}
.ct{{color:#fbbf24;background:rgba(251,191,36,.12);border-radius:20px;padding:2px 9px;font-weight:700}}
.ai{{color:#4ade80;background:rgba(74,222,128,.14);border-radius:20px;padding:2px 9px;font-weight:700}}
.sc{{color:#7ab8ff;font-weight:600}}
.dt{{color:#94a6c4;margin-left:auto}}
.item .ti{{font-size:14.5px;font-weight:700;color:#f2f6fc;line-height:1.5}}
.item .ti a{{color:#f2f6fc;text-decoration:none}}.item .ti a:hover{{color:#7ab8ff}}
.item .bf{{font-size:12.5px;color:#94a6c4;margin-top:6px;line-height:1.6}}
.empty{{color:#94a6c4;font-size:13px;padding:14px;text-align:center;grid-column:1/-1}}
.foot{{margin-top:22px;padding:14px 4px;font-size:12px;color:#94a6c4;line-height:1.8;border-top:1px solid #2f4166}}
.foot b{{color:#c9d5e8}}
</style></head><body>
<div class="wrap">
<div class="nav"><a href="home.html">🏠 首页</a><a class="o" href="board.html">📈 股票看板</a><a class="o" href="news.html">🌍 全球头条</a><a class="o" href="tongguang/">📰 全球AI早报</a><span class="ts">🕐 {BUILD_TS} 北京</span></div>
<div class="header">
  <h1>🌍 非洲科技脉搏</h1>
  <div class="sub">同光科技立足莫桑比克 · 跟踪整个非洲大陆科技与 AI 的一举一动 · 数据源为非洲本地科技媒体(真实可溯)</div>
  <div class="kpis"><div class="kpi"><b>{n_total}</b><span>今日条目</span></div><div class="kpi"><b>{n_ai}</b><span>AI / 前沿</span></div><div class="kpi"><b>{n_ctry}</b><span>覆盖国家</span></div></div>
</div>
{body}
<div class="foot">
  数据源:<b>TechCabal · Disrupt Africa · Techpoint Africa · IT News Africa · TechAfrica News · Condia</b> 等非洲本地科技媒体 RSS(每次构建实时抓取,链接直达原文可溯)<br>
  采集时间 {esc(fetched)} 北京 · 仅供研究与学习,非投资建议 · LUMORA · 同光科技
</div>
</div>
</body></html>"""
    os.makedirs(STATE, exist_ok=True)
    out = os.path.join(STATE, "africa.html")
    open(out, "w", encoding="utf-8").write(html_out)
    print(f"✅ 非洲科技脉搏页 → {out}({len(items)} 条 · AI {n_ai} · {n_ctry} 国)")


if __name__ == "__main__":
    main()
