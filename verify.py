#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 自动验证 + 校准:读 state/predictions.jsonl(历史各期预测)+ yfinance 真实价。
· 即时可达性校验(最新一期):买入价是否在近20交易日真实成交区间内、目标隐含涨幅是否过激。
· 历史复盘(过往各期):买入区间是否被触及、距目标完成度、方向胜率、到期实际收益 vs 预测。
· 记分卡 + 校准建议 → state/verification.json,供看板与 Claude 出建议时读用。"""
import json, os, datetime
import yfinance as yf
import pandas as _pd

def _median(a):
    """中位数——pace 用它而非均值,免被少数快仓拉偏,更代表'典型在途节奏'(审计建议)。"""
    if not a:
        return None
    b = sorted(a); n = len(b); m = n // 2
    return b[m] if n % 2 else (b[m - 1] + b[m]) / 2


DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
LEDGER = os.path.join(STATE, "predictions.jsonl")
OUT = os.path.join(STATE, "verification.json")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()  # 北京时间


def main():
    cfg = json.load(open(os.path.join(DIR, "config.json"), encoding="utf-8"))
    # 审计修复:基准 ETF(QQQ 等)只作相对强弱对比锚,绝不当选股仓计入复盘——
    # 否则其"买入/底仓"信号会漏进入场集,污染方向胜率/入场率分母(实测虚高胜率)。
    # 审计F18:config.json 的键是单数 benchmark(:7),此前读复数 benchmarks → 恒取兜底 ["QQQ"](凑巧对);
    # 兼容复数(未来多基准)+ 单数真值 + 兜底,读对配置不再靠巧合。
    BENCH = set(cfg.get("benchmarks") or ([cfg["benchmark"]] if cfg.get("benchmark") else ["QQQ"]))
    PACE_MIN_DAYS = int(cfg.get("pace_min_days", 14))  # 嫩仓 pace 会炸表(1天仓 elapsed→几十×),低于此天数不计入在途节奏
    recs = []
    if os.path.exists(LEDGER):
        for ln in open(LEDGER, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    recs.append(json.loads(ln))
                except Exception:
                    pass
    latest = max((r.get("date") for r in recs if r.get("date")), default=None)
    cache = {}

    def ohlc(tk):
        if tk not in cache:
            cache[tk] = yf.Ticker(tk).history(period="1y", interval="1d", auto_adjust=True)
        return cache[tk]

    feasibility, review = {}, []
    for r in recs:
        tk, rdate = r.get("ticker"), r.get("date")
        if not tk or not rdate:   # 跳过缺关键字段的台账行,避免 KeyError 中断整次复盘
            continue
        if tk in BENCH:           # 基准锚(QQQ)不进可达性/记分卡,只在别处作对比基准
            continue
        try:
            df = ohlc(tk); cur = float(df["Close"].dropna().iloc[-1])
        except Exception:
            continue
        bl, bh, tl, th = r.get("buy_low"), r.get("buy_high"), r.get("target_low"), r.get("target_high")
        buy_mid = (bl + bh) / 2 if bl and bh else None
        tgt_mid = (tl + th) / 2 if tl and th else None
        is_buy = str(r.get("signal", "")).startswith("买入")
        if rdate == latest:
            if not (bl and bh):
                continue   # 审计F8:无买区(观望留空/护栏降级"—")不做可达性判定,免得被记 False 误报"需关注"
            low20 = float(df["Low"].dropna().tail(20).min()); high20 = float(df["High"].dropna().tail(20).max())
            reach = bool(bl and bh and bl <= high20 and bh >= low20)
            note = ("✅ 可达(近20日区间覆盖买入价)" if reach else
                    ("⚠️ 买入价低于近20日低点,可能挂不上" if (bl and low20 > bh) else
                     ("⚠️ 买入价高于近20日高点,等同追高" if (bh and high20 < bl) else "—")))
            implied = round((tgt_mid / cur - 1) * 100, 1) if tgt_mid else None
            feasibility[tk] = {"cur": round(cur, 2), "buy_reachable": reach, "note": note,
                               "recent20_low": round(low20, 2), "recent20_high": round(high20, 2),
                               "target_implied_move_pct": implied,
                               "target_aggressive": bool(implied is not None and implied > cfg["target_aggressive_pct"])}
        else:
            since = df[df.index.date >= datetime.date.fromisoformat(rdate)]
            lows = since["Low"].dropna() if len(since) else None
            # entry_hit 仅对"买入"信号有意义:买入区间下沿是否被真实触及(挂单能否成交入场)
            entry_hit = (bool(bh and lows is not None and len(lows) and float(lows.min()) <= bh)
                         if (is_buy and lows is not None) else None)
            entered = bool(is_buy and entry_hit)   # 真实入场 = 买入信号 且 买入价被触及
            matured = TODAY >= r.get("eval_date", "9999")
            # 方向/进度/到期收益:只对"真实入场"的买入仓计算,绝不给观望票或未入场的票虚报收益
            direction_ok = bool(cur >= buy_mid) if (entered and buy_mid) else None
            progress = (round((cur - buy_mid) / (tgt_mid - buy_mid) * 100, 1)
                        if (entered and buy_mid and tgt_mid and tgt_mid != buy_mid) else None)
            realized = round((cur / buy_mid - 1) * 100, 1) if (entered and buy_mid) else None
            review.append({"date": rdate, "ticker": tk, "signal": r.get("signal"),
                           "price_at_call": r.get("price_at_call"), "cur": round(cur, 2),
                           "entry_hit": entry_hit, "entered": entered, "direction_ok": direction_ok,
                           "progress_to_target_pct": progress, "matured": matured,
                           "realized_return_pct": realized})

    # 相对QQQ超额裁判(2026-07:LLM 黑箱 vs 纯规则,谁的【买入】信号跑赢指数)。用超额滤掉大盘beta,
    # 分 20交易日(~1月)/60交易日(~1季)滚动窗口。规则信号从台账有 rule_signal 的行起累积(今日起)。
    def fwd_excess(tk, call_date, ndays):
        try:
            s = ohlc(tk)["Close"].dropna(); q = ohlc("QQQ")["Close"].dropna()
            cd = _pd.Timestamp(call_date)
            if s.index.tz is not None:
                cd = cd.tz_localize(s.index.tz)
            si = s.index.searchsorted(cd); qi = q.index.searchsorted(cd)
            if si + ndays >= len(s) or qi + ndays >= len(q):   # 未到 ndays / 越界
                return None
            sr = float(s.iloc[si + ndays]) / float(s.iloc[si]) - 1
            qr = float(q.iloc[qi + ndays]) / float(q.iloc[qi]) - 1
            return (sr - qr) * 100
        except Exception:
            return None

    excess = {"llm": {20: [], 60: []}, "rule": {20: [], 60: []}}
    for r in recs:
        tk, cd = r.get("ticker"), r.get("date")
        if not tk or tk in BENCH or not cd:
            continue
        for eng, sigk in (("llm", "signal"), ("rule", "rule_signal")):
            if str(r.get(sigk, "")).startswith("买入"):   # 只统计【买入】信号(真取了仓位)
                for nd in (20, 60):
                    e = fwd_excess(tk, cd, nd)
                    if e is not None:
                        excess[eng][nd].append(e)
    _avg = lambda a: round(sum(a) / len(a), 1) if a else None
    rel_qqq = {
        "llm_1m": _avg(excess["llm"][20]), "llm_1m_n": len(excess["llm"][20]),
        "rule_1m": _avg(excess["rule"][20]), "rule_1m_n": len(excess["rule"][20]),
        "llm_3m": _avg(excess["llm"][60]), "llm_3m_n": len(excess["llm"][60]),
        "rule_3m": _avg(excess["rule"][60]), "rule_3m_n": len(excess["rule"][60]),
        "basis": "买入信号持有 N 交易日相对 QQQ 的超额收益均值(滤大盘beta);规则信号自台账有 rule_signal 起累积。样本小时仅供观察、非结论。",
    }

    # 审计F9(规则9"空结果绝不落盘"):有历史台账在评、本次却一条复盘都没算出(yfinance 全挂)时,
    # 绝不用空复盘覆盖 verification.json / 追加空史行——否则看板复盘区会退化成"首期"、把全部历史藏起来。
    hist_dates = {r.get("date") for r in recs if r.get("date")} - {latest}
    if hist_dates and not review:
        print(json.dumps({"warning": "复盘取数全挂(0 行),保留上期 verification.json 不覆盖"}, ensure_ascii=False))
        return
    sc = {"n_open": len(review),
          "n_entered": sum(1 for x in review if x.get("entered")),   # 真实入场样本数=方向胜率/收益的分母(审计:此前用 n_open 贴错'已入场仓位'标签)
          "n_periods": len({x["date"] for x in review}),             # 历史在评的不同预测期数(distinct dates)
          "basis": "胜率/进度/到期收益仅统计【买入信号且买入价被真实触及(入场)】的仓位;观望、回避、买入价未触及(未入场)一律不计入,绝不虚报。基准 ETF(QQQ)不计入。"}
    HORIZON = cfg.get("horizon_days", 270)
    if review:
        eh = [x["entry_hit"] for x in review if x["entry_hit"] is not None]
        dr = [x["direction_ok"] for x in review if x["direction_ok"] is not None]
        pr = [x["progress_to_target_pct"] for x in review if x["progress_to_target_pct"] is not None]
        mat = [x for x in review if x["matured"] and x["realized_return_pct"] is not None]
        # pace_ratio:把进度按"已过时间占horizon比"归一化——≈1踩点、<0.6落后、>1.4超前。
        # 取代把在途裸进度当到期成绩(方向胜率高时,裸进度低只是时间没到,拿它压目标=误伤未兑现上行)。
        paces = []
        for x in review:
            if x["progress_to_target_pct"] is None:
                continue
            try:
                elapsed = (datetime.date.fromisoformat(TODAY) - datetime.date.fromisoformat(x["date"])).days
            except Exception:
                continue
            if elapsed < PACE_MIN_DAYS:   # 审计修复:嫩仓 progress/(极小时间占比) 会炸到几十×,污染均值,剔除
                continue
            frac = elapsed / HORIZON
            paces.append(x["progress_to_target_pct"] / 100 / frac)
        sc.update({"entry_hit_rate": round(100 * sum(eh) / len(eh)) if eh else None,
                   "direction_win_rate": round(100 * sum(dr) / len(dr)) if dr else None,
                   "avg_progress_to_target_pct": round(sum(pr) / len(pr), 1) if pr else None,
                   "avg_pace_ratio": round(_median(paces), 2) if paces else None,   # 中位数:免被快仓拉偏(嫩仓已剔)
                   "matured_n": len(mat),
                   "matured_avg_realized_pct": round(sum(x["realized_return_pct"] for x in mat) / len(mat), 1) if mat else None})
        # 审计第一批·校准诚实化:上面的 dr 是逐(日,票)快照——同一票跨期被重复计入=【伪重复 pseudo-replication】,
        # 非独立观测,虚增样本量且带自相关,胜率不能当统计结论。补【按票去重】独立口径:每票只取最近一次入场快照。
        entered_dir = [x for x in review if x.get("entered") and x.get("direction_ok") is not None]
        latest_by_tk = {}
        for x in sorted(entered_dir, key=lambda z: z["date"]):
            latest_by_tk[x["ticker"]] = x          # 按日期升序后写覆盖→每票保留最近一次
        dr_u = [x["direction_ok"] for x in latest_by_tk.values()]
        sc["n_entered_unique"] = len(latest_by_tk)     # 独立样本量(去重后的票数,远小于 n_entered)
        sc["direction_win_rate_unique"] = round(100 * sum(dr_u) / len(dr_u)) if dr_u else None
        sc["verified"] = bool(len(mat) >= cfg.get("min_periods_for_calibration", 5))   # 到期样本达标才算"经统计验证"
        sc["rel_qqq"] = rel_qqq                          # 相对QQQ超额裁判(LLM vs 规则)
        sc["basis"] += ("｜⚠️方向胜率为【在途·未到期】值:在途口径含同票逐日快照(伪重复非独立),另附【按票去重】"
                        f"独立口径 n={sc['n_entered_unique']};到期样本 matured_n={len(mat)},"
                        f"未达 {cfg.get('min_periods_for_calibration', 5)} 期前一律不构成'系统准不准'的统计结论。")

    n_hist = len({r.get("date") for r in recs if r.get("date")} - {latest})
    need = cfg["min_periods_for_calibration"]
    mat_n = sc.get("matured_n", 0)
    ap = sc.get("avg_progress_to_target_pct")
    pace = sc.get("avg_pace_ratio")
    ehr = sc.get("entry_hit_rate")
    if mat_n >= need:
        # 只有【到期样本】够了才做真·目标价校准(用已实现收益,不用在途进度)
        mar = sc.get("matured_avg_realized_pct")
        calib = (f"到期 {mat_n} 期 · 实际收益均值 {mar}% → 目标价"
                 + ("偏激进,下期收窄" if (mar is not None and mar < 25)
                    else "兑现良好,维持" if (mar is not None and mar <= 60) else "偏保守,可上调") + "。")
    else:
        # matured 不足:目标价终值【暂不可校准】,绝不用在途 progress 反推激进度(会机械压低未兑现的目标)。
        # 改为反馈【当下就能校准的买点】:入场触及率(买区挂不挂得上),这是可立即改进的杠杆。
        buy_hint = ("偏低 → 下期对上期未触及的票按现价重锚最近结构支撑、收窄买区折让" if (ehr is not None and ehr < 65)
                    else "良好")
        pace_hint = f" · 在途节奏 pace={pace}(≈1踩点/<0.6落后/>1.4超前)" if pace is not None else ""
        calib = (f"到期样本 {mat_n} 期(<{need}),目标价终值【暂不可校准】——{n_hist} 期在途预测均未走完 {HORIZON} 天窗口,"
                 f"当前平均进度 {ap}% 属半程未实现{pace_hint},【不作收窄依据】。当下可校准的是买点:入场触及率 {ehr}% {buy_hint}。")

    json.dump({"asof": TODAY, "latest_call_date": latest, "feasibility": feasibility,
               "review": review, "scorecard": sc, "calibration": calib},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # 记分卡历史逐日累积(替换式:同日重跑覆盖当日行)——表盘"进化曲线"的数据源,
    # 让"方向胜率/入场率是否越用越准"从口号变成可见的趋势线(闭环已接通,这里是它的仪表)
    hist_p = os.path.join(STATE, "scorecard_history.jsonl")
    kept = []
    if os.path.exists(hist_p):
        for ln in open(hist_p, encoding="utf-8"):
            try:
                if json.loads(ln).get("date") != TODAY:
                    kept.append(ln.strip())
            except Exception:
                continue
    kept.append(json.dumps({"date": TODAY, **{k: sc.get(k) for k in
                ("entry_hit_rate", "direction_win_rate", "avg_pace_ratio", "matured_n", "n_open")}},
                ensure_ascii=False))
    open(hist_p, "w", encoding="utf-8").write("\n".join(kept) + "\n")
    bad = [tk for tk, v in feasibility.items() if not v["buy_reachable"] or v["target_aggressive"]]
    print(json.dumps({"feasibility_checked": len(feasibility), "需关注": bad,
                      "review_open": len(review), "scorecard": sc, "calibration": calib},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
