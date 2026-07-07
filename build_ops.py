#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「运营看板」渲染:全站数据资产/构建健康度/DeepSeek 消耗 → state/ops.html。
指标三档(用户确认口径):
  ✅ 全自动:行情快照/研判期数/台账/归档/头条期数、同光文章与报告数、Actions 构建健康度(有 GITHUB_TOKEN 时)、
            DeepSeek token 消耗(state/usage.jsonl)与账户余额(有 key 时)。
  ⏸ 暂缓:访问量(需 GoatCounter,用户选择先不做——页内如实说明)。
  ❌ 做不了(诚实披露):Claude 研判 token(Anthropic 无查询接口)、盘势问答全站 token 汇总(无后端,仅本设备)。
本地跑(无 GITHUB_TOKEN)时构建健康度标"本地构建未获取"。"""
import os, re, json, glob, datetime, urllib.request, ssl

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
_BJ = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
TODAY = _BJ.date().isoformat()
BUILD_TS = _BJ.strftime("%Y-%m-%d %H:%M")
REPO = "xiaomin4576-ui/meigu-ai-stock-board"


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _api(url, token=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "ops-builder",
                                               **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return json.loads(r.read().decode("utf-8"))


def stat_meigu():
    """美股看板侧数据资产。"""
    datas = sorted(glob.glob(os.path.join(STATE, "data_*.json")))
    calls = sorted(glob.glob(os.path.join(STATE, "calls_*.json")))
    boards = sorted(glob.glob(os.path.join(STATE, "ai_stock_board_*.html")))
    newses = [f for f in sorted(glob.glob(os.path.join(STATE, "news_*.json"))) if re.search(r"news_\d{4}-\d{2}-\d{2}\.json$", f)]
    total_bytes = sum(os.path.getsize(f) for f in datas)
    ledger = os.path.join(STATE, "predictions.jsonl")
    n_pred = sum(1 for _ in open(ledger, encoding="utf-8")) if os.path.exists(ledger) else 0
    cov = "—"
    if datas:
        try:
            meta = json.load(open(datas[-1], encoding="utf-8")).get("meta", {})
            cov = f"{meta.get('fresh','?')}/{meta.get('total','?')} 当日真值"
        except Exception:
            pass
    d = lambda fs, pat: (re.search(pat, os.path.basename(fs[-1])).group(1) if fs else "—")
    return {"行情快照": f"{len(datas)} 份 · {total_bytes//1024} KB · 最新 {d(datas, r'data_(.*)\.json')}",
            "数据覆盖率": cov,
            "研判期数": f"{len(calls)} 期 · 最新 {d(calls, r'calls_(.*)\.json')}",
            "预测台账": f"{n_pred} 条(复盘校准依据)",
            "看板归档": f"{len(boards)} 期",
            "全球头条": (f"{len(newses)} 期 · 最新 {d(newses, r'news_(.*)\.json')}" if newses else "尚无(首期待生成)")}


def stat_tongguang():
    """同光早报侧(CI 时用镜像 clone 的 /tmp/tg,本地用桌面工程;都没有则如实标注)。"""
    for base in (os.environ.get("TG_DIR") or "", "/tmp/tg/docs", os.path.expanduser("~/Desktop/tongguang-ai-daily-routine/docs")):
        p = os.path.join(base, "data", "index.json") if base else ""
        if p and os.path.exists(p):
            try:
                j = json.load(open(p, encoding="utf-8"))
                arts = j.get("articles", [])
                reps = j.get("reports", [])
                latest = max((a.get("date", "") for a in arts), default="—")
                return {"文章库": f"{len(arts)} 篇(181 信源)", "早报期数": f"{len(reps)} 期",
                        "最新早报": latest, "语料体积": f"{os.path.getsize(p)//1024} KB(问答语料源)"}
            except Exception:
                pass
    return {"文章库": "本次构建未取到镜像(不影响线上)"}


def stat_actions():
    """构建健康度:最近 50 次 workflow run。"""
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    try:
        j = _api(f"https://api.github.com/repos/{REPO}/actions/runs?per_page=50", token or None)
        runs = j.get("workflow_runs", [])
        if not runs:
            return {"构建记录": "未获取"}
        ok = sum(1 for r in runs if r.get("conclusion") == "success")
        bad = sum(1 for r in runs if r.get("conclusion") in ("failure", "timed_out"))
        cxl = sum(1 for r in runs if r.get("conclusion") == "cancelled")
        return {"最近50次构建": f"成功 {ok} · 失败 {bad} · 取消/超时 {cxl}",
                "成功率": f"{round(ok/len(runs)*100)}%",
                "最近一次": f"{runs[0].get('created_at','')[:16].replace('T',' ')} UTC · {runs[0].get('conclusion') or runs[0].get('status')}"}
    except Exception:
        return {"构建记录": "本地构建未获取(线上 CI 会带 GITHUB_TOKEN 自动统计)"}


def stat_deepseek():
    """DeepSeek 消耗:usage.jsonl 汇总 + 余额接口。"""
    out = {}
    up = os.path.join(STATE, "usage.jsonl")
    if os.path.exists(up):
        tot = {"research": [0, 0], "news": [0, 0], "其他": [0, 0]}
        n = 0
        for line in open(up, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            n += 1
            k = r.get("purpose") if r.get("purpose") in tot else "其他"
            tot[k][0] += r.get("total_tokens") or 0
            tot[k][1] += 1
        out["已落账调用"] = f"{n} 次(自 2026-07-07 起计;此前调用未落账,如实缺记)"
        for k, (tk, c) in tot.items():
            if c:
                label = {"research": "个股研判", "news": "头条研判"}.get(k, k)
                out[f"{label}消耗"] = f"{tk:,} tokens / {c} 次"
    else:
        out["已落账调用"] = "暂无记录(usage.jsonl 自本功能上线起累积)"
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if key:
        try:
            j = _api("https://api.deepseek.com/user/balance", key)
            bi = (j.get("balance_infos") or [{}])[0]
            out["账户余额"] = f"{bi.get('total_balance','?')} {bi.get('currency','')}"
        except Exception:
            out["账户余额"] = "查询失败(不影响功能)"
    else:
        out["账户余额"] = "本地构建无 key 未查询"
    return out


def sec(title, color, kv, note=""):
    rows = "".join(f'<div class="row"><span class="k">{k}</span><span class="v">{v}</span></div>' for k, v in kv.items())
    n = f'<div class="note">{note}</div>' if note else ""
    return f'<div class="panel"><div class="ph" style="color:{color}">{title}</div>{rows}{n}</div>'


def main():
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<title>运营看板 · {TODAY}</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#0b1120;color:#e2e8f0;line-height:1.6;padding:20px}}
.wrap{{max-width:980px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid #334155;border-radius:16px;padding:24px 28px;margin-bottom:16px}}
.header h1{{font-size:24px;font-weight:900;color:#a78bfa}}
.sub{{font-size:13px;color:#94a3b8;margin-top:6px}}
.nav{{margin-top:10px;font-size:12.5px}}.nav a{{color:#60a5fa;text-decoration:none;font-weight:700;margin-right:14px}}
.gridp{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:760px){{.gridp{{grid-template-columns:1fr}}}}
.panel{{background:#111a2e;border:1px solid #334155;border-radius:14px;padding:16px 18px}}
.ph{{font-size:15px;font-weight:800;margin-bottom:10px}}
.row{{display:flex;justify-content:space-between;gap:12px;font-size:12.5px;padding:5px 0;border-bottom:1px dashed rgba(51,65,85,.5)}}
.row:last-of-type{{border-bottom:none}}
.k{{color:#94a3b8;white-space:nowrap}}.v{{color:#e2e8f0;text-align:right}}
.note{{font-size:11px;color:#64748b;margin-top:8px;line-height:1.7}}
.honest{{background:rgba(251,146,60,.07);border:1px solid rgba(251,146,60,.25);border-radius:13px;padding:13px 17px;margin-top:14px;font-size:12px;color:#fed7aa;line-height:1.8}}
.foot{{text-align:center;font-size:11px;color:#475569;margin-top:18px}}
</style></head><body><div class="wrap">
<div class="header"><h1>📊 运营看板 · {TODAY}</h1>
<div class="sub">全站数据资产 · 构建健康度 · AI 引擎消耗 —— 每次构建自动更新</div>
<div class="nav"><a href="index.html">🏠 首页</a><a href="board.html">📡 股票看板</a><a href="news.html">🌍 全球头条</a><span style="color:#7c8aa3">🕐 本页生成 {BUILD_TS} 北京</span></div></div>
<div class="gridp">
{sec("📡 美股AI看板 · 数据资产", "#34d399", stat_meigu())}
{sec("📰 同光AI早报 · 语料资产", "#60a5fa", stat_tongguang())}
{sec("⚙️ 构建健康度(GitHub Actions)", "#fbbf24", stat_actions(), "免费档 cron 有延迟/跳过属平台特性;成功率含被后续运行顶替的取消")}
{sec("🤖 DeepSeek 引擎消耗", "#a78bfa", stat_deepseek(), "覆盖:🔁更新研判(19票)+ 头条研判;盘势问答为浏览器直连,token 只在各自设备本地可见")}
</div>
<div class="honest"><b>诚实披露——这些指标当前做不了:</b><br>
· <b>访问量/访客数</b>:静态站需接第三方统计(GoatCounter 免费),用户选择暂缓;要开时注册后一行代码接入。<br>
· <b>Claude 研判 token</b>:Anthropic 不提供用量查询接口,Claude 亲研部分无法自动进表。<br>
· <b>盘势问答全站消耗</b>:问答无后端(浏览器直连 DeepSeek),无法汇总所有访问者的用量。</div>
<div class="foot">仅站务运营指标,不含任何投资内容</div>
</div></body></html>"""
    out = os.path.join(STATE, "ops.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out)


if __name__ == "__main__":
    main()
