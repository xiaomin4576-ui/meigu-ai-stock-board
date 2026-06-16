#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑥ 历史归档看板(阅读库式):扫 state/ 下所有每日看板 + 复盘记分卡,
生成 state/index.html——翻历史早报 + 看复盘表现曲线(随台账累积)。"""
import json, os, glob, re, datetime

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")


def jload(p, d=None):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d


def main():
    boards = sorted(glob.glob(os.path.join(STATE, "ai_stock_board_*.html")), reverse=True)
    rows = []
    for b in boards:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(b))
        if not m:
            continue
        date = m.group(1)
        calls = jload(os.path.join(STATE, f"calls_{date}.json"), {})
        st = calls.get("stocks", {})
        buy = sum(1 for a in st.values() if str(a.get("sig", "")).startswith("买入"))
        watch = sum(1 for a in st.values() if "观望" in str(a.get("sig", "")))
        top = (calls.get("ranking") or list(st.keys()))[:3]
        top_str = " · ".join(top)
        rows.append(f'<tr><td><a href="ai_stock_board_{date}.html">{date}</a></td>'
                    f'<td>{len(st)}</td><td style="color:#4ade80">{buy} 买入</td>'
                    f'<td style="color:#fbbf24">{watch} 观望</td><td>{top_str}</td></tr>')
    v = jload(os.path.join(STATE, "verification.json"), {})
    sc = v.get("scorecard", {})
    n_open = sc.get("n_open", 0)
    if n_open > 0:
        card = (f'历史在评 {n_open} 期 · 买入触及率 {sc.get("entry_hit_rate","—")}% · '
                f'方向胜率 {sc.get("direction_win_rate","—")}% · 平均目标完成度 {sc.get("avg_progress_to_target_pct","—")}% · '
                f'已到期 {sc.get("matured_n",0)} 期(实际 {sc.get("matured_avg_realized_pct","—")}%)')
    else:
        card = "首期 · 复盘表现曲线将随每日台账累积(买入触及率 / 方向胜率 / 目标完成度 / 到期实际收益)"
    nboards = len(rows)
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0"><title>美股 AI 早报 · 历史归档</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#0b1120;color:#e2e8f0;padding:24px;line-height:1.6}}
.wrap{{max-width:920px;margin:0 auto}}h1{{color:#60a5fa;font-size:24px;font-weight:900}}.sub{{color:#94a3b8;font-size:13px;margin:6px 0 18px}}
.sc{{background:#0f1a30;border:1px solid #2a3a5a;border-radius:12px;padding:16px 18px;margin-bottom:18px}}
.sc b{{color:#a5b4fc}}.scv{{font-size:13px;color:#cbd5e1;margin-top:6px}}
table{{width:100%;border-collapse:collapse;background:#111a2e;border:1px solid #334155;border-radius:12px;overflow:hidden}}
th,td{{padding:11px 14px;text-align:left;font-size:13px;border-bottom:1px solid #243049}}
th{{background:#1e293b;color:#94a3b8;font-size:12px}}a{{color:#60a5fa;text-decoration:none;font-weight:700}}a:hover{{text-decoration:underline}}
.foot{{color:#475569;font-size:11px;margin-top:16px;line-height:1.7}}
</style></head><body><div class="wrap">
<h1>📚 美股 AI 科技股早报 · 历史归档</h1>
<div class="sub">共 {nboards} 期 · 阅读库式翻历史 + 复盘表现 · 仅研究用途非投资建议</div>
<div class="sc"><b>🔍 复盘记分卡:</b><div class="scv">{card}</div></div>
<table><thead><tr><th>日期</th><th>标的数</th><th>买入</th><th>观望</th><th>买点 Top3</th></tr></thead>
<tbody>{''.join(rows) if rows else '<tr><td colspan=5>暂无</td></tr>'}</tbody></table>
<div class="foot">每天跑早报自动归档一期;预测台账(predictions.jsonl)逐日累积,复盘记分卡随之更新。<br>⚠️ 仅供研究/学习,非投资建议。</div>
</div></body></html>"""
    open(os.path.join(STATE, "index.html"), "w", encoding="utf-8").write(html)
    print(f"✅ 归档看板已生成:{os.path.join(STATE, 'index.html')}({nboards} 期)")


if __name__ == "__main__":
    main()
