#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑦ 历史回测:用真实 3 年 yfinance 数据,测本策略【核心规则】的实际表现,
   用证据代替"承诺精准度"。规则(本 skill 的简化可回测版):
     · 上升趋势(收盘 > MA200)中
     · 回调到 MA50 附近(收盘在 MA50 的 -2%~+5%)→ 入场
     · 目标 +25% / 止损 -10%(R:R = 2.5:1),最长持有 126 个交易日(~6月)
     · 同一标的同时只持一仓(解决后再开新仓)
   输出:命中率 / 止损率 / 超时率 / 平均盈亏 / 实际 R:R → state/backtest.json
⚠️ 诚实警告:测试标的是 AI 大牛市里的赢家,结果被行情严重美化,不代表未来,更非 90%。"""
import json, os, time, datetime
import requests
import yfinance as yf

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
TARGET, STOP, MAXHOLD = 0.25, 0.10, 126
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _session():
    """带浏览器 UA 的 session,降低 GitHub Actions 数据中心 IP 被 Yahoo 限流概率。"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return s


_SESS = _session()


def backtest_one(tk):
    # 简单重试:限流时退避重试 2 次(总 3 次),仍失败抛出由 main 记 err 跳过
    df = None
    for i in range(3):
        try:
            df = yf.Ticker(tk, session=_SESS).history(period="3y", interval="1d", auto_adjust=True)
            if df is not None and len(df) > 0:
                break
        except Exception:
            pass
        time.sleep(2.0 * (2 ** i))
    if df is None or len(df) == 0:
        raise RuntimeError("行情为空(可能被限流)")
    c = df["Close"].dropna()
    lo = df["Low"].dropna()
    hi = df["High"].dropna()
    if len(c) < 250:
        return []
    ma50 = c.rolling(50).mean()
    ma200 = c.rolling(200).mean()
    trades, i, n = [], 200, len(c)
    while i < n - 1:
        px = float(c.iloc[i])
        m50, m200 = float(ma50.iloc[i]), float(ma200.iloc[i])
        if m50 != m50 or m200 != m200:  # NaN
            i += 1; continue
        # 上升趋势 + 回调到 MA50 附近
        if px > m200 and (m50 * 0.98) <= px <= (m50 * 1.05):
            entry = px
            tgt, stp = entry * (1 + TARGET), entry * (1 - STOP)
            outcome = None
            for j in range(i + 1, min(i + 1 + MAXHOLD, n)):
                if float(lo.iloc[j]) <= stp:
                    outcome = ("loss", -STOP); break
                if float(hi.iloc[j]) >= tgt:
                    outcome = ("win", TARGET); break
            if outcome is None:
                outcome = ("timeout", float(c.iloc[min(i + MAXHOLD, n - 1)]) / entry - 1)
            trades.append(outcome)
            i = min(i + MAXHOLD, n - 1) if outcome[0] == "timeout" else i + 30  # 冷却,避免重叠
        else:
            i += 1
    return trades


def main():
    cfg = json.load(open(os.path.join(DIR, "config.json"), encoding="utf-8"))
    tickers = [s["ticker"] for s in cfg["stocks"] if s["ticker"] != cfg.get("benchmark")]
    allt = []
    per = {}
    for tk in tickers:
        try:
            t = backtest_one(tk)
            per[tk] = len(t)
            allt += t
        except Exception as e:
            per[tk] = f"err:{str(e)[:40]}"
    n = len(allt)
    if n == 0:
        print("无信号"); return
    wins = [r for r in allt if r[0] == "win"]
    losses = [r for r in allt if r[0] == "loss"]
    tos = [r for r in allt if r[0] == "timeout"]
    rets = [r[1] for r in allt]
    win_rate = round(100 * len(wins) / n)
    avg = round(100 * sum(rets) / n, 1)
    # 实际盈亏比:平均盈利 / 平均亏损绝对值
    avg_win = (sum(r[1] for r in wins) / len(wins)) if wins else 0
    avg_loss = (sum(r[1] for r in losses) / len(losses)) if losses else 0
    rr = round(abs(avg_win / avg_loss), 2) if avg_loss else None
    out = {
        "asof": datetime.date.today().isoformat(),
        "rule": f"上升趋势(>MA200)回调至MA50附近入场,目标+{int(TARGET*100)}%/止损-{int(STOP*100)}%,持有≤{MAXHOLD}日",
        "universe": tickers, "lookback": "3y", "signals": n, "per_stock_signals": per,
        "win_rate_pct": win_rate, "stopped_pct": round(100 * len(losses) / n),
        "timeout_pct": round(100 * len(tos) / n), "avg_trade_return_pct": avg,
        "realized_rr": rr,
        "caveat": "测试标的为AI大牛市赢家,存在幸存者/行情偏差,结果被严重美化;不代表未来表现,绝非承诺胜率。",
    }
    os.makedirs(STATE, exist_ok=True)
    json.dump(out, open(os.path.join(STATE, "backtest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({k: out[k] for k in ["signals", "win_rate_pct", "stopped_pct", "timeout_pct", "avg_trade_return_pct", "realized_rr"]}, ensure_ascii=False, indent=2))
    print("⚠️", out["caveat"])


if __name__ == "__main__":
    main()
