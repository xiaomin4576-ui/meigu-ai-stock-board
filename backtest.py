#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑦ 历史回测(2026-07 指标审计第二批:改测【现行分档策略】,替换此前错配的 MA50 简化规则)。
   金融教授关切"现行策略零回测"——本脚本用真实 ~5 年 yfinance 数据,尽量忠实地回测当前看板在用的规则骨架:
     · 趋势过滤:收盘 > MA200(上升趋势)
     · 买点:回踩到结构支撑(强势档=价>MA20→锚 MA20;破位档→锚 MA50)附近入场
     · 分档止损:强势档 -6% / 破位档 -10%(与 build_board 卡片同口径)
     · 目标:按 R:R=2.5 反推(强势档 +15% / 破位档 +25%),持有 ≤ 270 交易日(现行长期视角)
     · 交易成本:每笔往返 -0.20%(手续费+滑点近似)
     · 跳空穿止损按【当日开盘价】成交(建模"一字跌停/跳空缺口 止损无法在止损价成交"的真实损失)
   产出:命中率(+95%置信区间)/止损率/超时率/平均盈亏/实际R:R/每笔夏普/最大连亏/分年度胜率 → state/backtest.json
   ⚠️ 三重诚实边界(务必随结果展示):
     ① 幸存者/行情偏差:池=当前 AI 牛市赢家,历史被严重美化,绝非未来、绝非高胜率;
     ② 规则骨架 ≠ 全系统:LLM 逐票信号与目标价【无法历史重放】,本回测只测机械的入场/止损/目标/持有骨架,
        用途是给"规则的边际"一个可证伪的下限,不是给整套研判背书;
     ③ 规则为事前设定(未在本段数据上调参),故全期结果近似样本外,但仍非严格 walk-forward 调参检验。"""
import json, os, datetime, math, warnings
warnings.filterwarnings("ignore")

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
HORIZON = 270            # 现行长期持有窗口(交易日近似)
RR = 2.5                 # 目标按 R:R=2.5 反推(与页面自述盈亏比一致)
TX = 0.002               # 每笔往返交易成本(手续费+滑点近似)
COOLDOWN = 20            # 平仓后冷却交易日,避免同票重叠开仓
STRONG_STOP, WEAK_STOP = 0.06, 0.10


def _limit_of(tk):
    """A股/创业板/科创板 日涨跌停幅度(用于诚实标注;68/30 为 20%,主板 10%)。"""
    if tk.endswith((".SS", ".SZ")):
        code = tk.split(".")[0]
        return 0.20 if code[:2] in ("68", "30") else 0.10
    return None


def backtest_one(tk, close, open_, low, high, ma20, ma50, ma200):
    trades = []
    n = len(close)
    i = 200
    while i < n - 1:
        px, m20, m50, m200 = close[i], ma20[i], ma50[i], ma200[i]
        if any(x != x for x in (px, m20, m50, m200)):   # NaN
            i += 1; continue
        strong = px > m20
        anchor = m20 if strong else m50
        # 上升趋势 + 回踩到锚定支撑附近(支撑上方 0~6% 视为"到位可挂单入场")
        if px > m200 and anchor <= px <= anchor * 1.06:
            entry = px
            stop_rate = STRONG_STOP if strong else WEAK_STOP
            stp = entry * (1 - stop_rate)
            tgt = entry * (1 + RR * stop_rate)          # R:R=2.5 → 强势+15%/破位+25%
            outcome, gap = None, False
            for j in range(i + 1, min(i + 1 + HORIZON, n)):
                oj, lj, hj = open_[j], low[j], high[j]
                if lj <= stp:                            # 触及止损
                    fill = min(oj, stp) if oj == oj else stp   # 跳空:开盘已在止损下方→按开盘(更差)成交
                    if fill < stp:
                        gap = True
                    outcome = ("loss", fill / entry - 1); break
                if hj >= tgt:                            # 触及目标(保守按目标价成交)
                    outcome = ("win", tgt / entry - 1); break
            if outcome is None:
                outcome = ("timeout", close[min(i + HORIZON, n - 1)] / entry - 1)
            ret = outcome[1] - TX                        # 扣交易成本
            trades.append({"year": None, "kind": outcome[0], "ret": ret, "gap": gap, "idx": i})
            i = (min(i + HORIZON, n - 1) if outcome[0] == "timeout" else i + COOLDOWN)
        else:
            i += 1
    return trades


def _wilson_ci(k, n, z=1.96):
    """胜率的 Wilson 95% 置信区间(小样本更稳)。"""
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(100 * (c - hw) / d), round(100 * (c + hw) / d)]


def main():
    cfg = json.load(open(os.path.join(DIR, "config.json"), encoding="utf-8"))
    bench = cfg.get("benchmark")
    tickers = [s["ticker"] for s in cfg["stocks"] if s["ticker"] != bench]
    import yfinance as yf
    import pandas as pd
    raw = yf.download(tickers, period="5y", interval="1d", progress=False, auto_adjust=True)
    if raw is None or len(raw) == 0:
        # 取数全挂:绝不用空结果覆盖上期(规则9)
        if os.path.exists(os.path.join(STATE, "backtest.json")):
            print("⚠️ 回测取数全挂,保留上期 backtest.json 不覆盖"); return
        print("⚠️ 回测取数全挂且无上期,跳过"); return

    allt, per, dates_idx = [], {}, None
    for tk in tickers:
        try:
            c = raw["Close"][tk].dropna()
            if len(c) < 300:
                per[tk] = "数据不足"; continue
            idx = c.index
            o = raw["Open"][tk].reindex(idx).tolist()
            lo = raw["Low"][tk].reindex(idx).tolist()
            hi = raw["High"][tk].reindex(idx).tolist()
            cl = c.tolist()
            ma20 = c.rolling(20).mean().tolist()
            ma50 = c.rolling(50).mean().tolist()
            ma200 = c.rolling(200).mean().tolist()
            t = backtest_one(tk, cl, o, lo, hi, ma20, ma50, ma200)
            for x in t:
                x["year"] = idx[x["idx"]].year
            per[tk] = len(t)
            allt += t
        except Exception as e:
            per[tk] = f"err:{str(e)[:30]}"

    n = len(allt)
    if n == 0:
        if os.path.exists(os.path.join(STATE, "backtest.json")):
            print("⚠️ 无信号,保留上期不覆盖"); return
        print("⚠️ 无信号"); return

    wins = [x for x in allt if x["kind"] == "win"]
    losses = [x for x in allt if x["kind"] == "loss"]
    tos = [x for x in allt if x["kind"] == "timeout"]
    rets = [x["ret"] for x in allt]
    win_rate = round(100 * len(wins) / n)
    avg = round(100 * sum(rets) / n, 1)
    avg_win = (sum(x["ret"] for x in wins) / len(wins)) if wins else 0
    avg_loss = (sum(x["ret"] for x in losses) / len(losses)) if losses else 0
    rr = round(abs(avg_win / avg_loss), 2) if avg_loss else None
    # 每笔夏普(平均/标准差,非年化)+ 最大连亏
    mean_r = sum(rets) / n
    std_r = (sum((r - mean_r) ** 2 for r in rets) / n) ** 0.5
    sharpe = round(mean_r / std_r, 2) if std_r else None
    mc, cur = 0, 0
    for x in allt:
        cur = cur + 1 if x["kind"] == "loss" else 0
        mc = max(mc, cur)
    # 分年度胜率(看跨体制稳定性)
    years = sorted({x["year"] for x in allt})
    per_year = {}
    for y in years:
        yl = [x for x in allt if x["year"] == y]
        yw = [x for x in yl if x["kind"] == "win"]
        per_year[str(y)] = {"n": len(yl), "win_rate": round(100 * len(yw) / len(yl)) if yl else None}
    gap_n = sum(1 for x in losses if x["gap"])

    out = {
        "asof": datetime.date.today().isoformat(),
        "strategy": "current_tiered",
        "rule": "上升趋势(>MA200)回踩至结构支撑(强势档锚MA20/破位档锚MA50)入场·分档止损(强势-6%/破位-10%)·目标按R:R2.5反推·持有≤270日·扣往返成本0.2%·跳空穿止损按开盘成交",
        "universe": tickers, "lookback": "5y", "horizon_days": HORIZON, "signals": n, "per_stock_signals": per,
        "win_rate_pct": win_rate, "win_rate_ci95": _wilson_ci(len(wins), n),
        "stopped_pct": round(100 * len(losses) / n), "timeout_pct": round(100 * len(tos) / n),
        "avg_trade_return_pct": avg, "realized_rr": rr, "per_trade_sharpe": sharpe,
        "max_consecutive_losses": mc, "gap_slippage_trades": gap_n, "tx_cost_pct": round(TX * 100, 2),
        "per_year_win_rate": per_year,
        "caveat": ("幸存者/牛市偏差:池为当前AI赢家,历史被美化,绝非未来更非高胜率；且本回测只测【机械规则骨架"
                   "(入场/分档止损/R:R目标/持有)】,LLM逐票信号与目标价无法历史重放,不代表整套研判；A股涨跌停/T+1"
                   "仅以'跳空穿止损按开盘成交'近似,规则为事前设定近似样本外但非严格walk-forward。"),
    }
    os.makedirs(STATE, exist_ok=True)
    json.dump(out, open(os.path.join(STATE, "backtest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 现行分档策略回测:{n}笔·命中{win_rate}%(CI{out['win_rate_ci95']})·止损{out['stopped_pct']}%·"
          f"R:R{rr}·每笔夏普{sharpe}·最大连亏{mc}·跳空滑点{gap_n}笔·分年度{ {y:per_year[y]['win_rate'] for y in per_year} }")
    print("⚠️", out["caveat"])


if __name__ == "__main__":
    main()
