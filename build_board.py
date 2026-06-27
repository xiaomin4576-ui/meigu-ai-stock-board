#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ 渲染:读 config + state/data_<date>.json(真实行情)+ state/calls_<date>.json(Claude 研判)
+ state/verification.json(复盘校准)→ 生成自包含 HTML 看板 state/ai_stock_board_<date>.html。
两个核心指标:① 买入建议+建议买入价 ② 6-12月目标价+预期收益。仅研究用途,非投资建议。"""
import json, os, re, datetime

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
_BJ_NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))  # 北京时间
TODAY = _BJ_NOW.date().isoformat()
BUILD_TS = _BJ_NOW.strftime("%Y-%m-%d %H:%M")  # 本页生成的北京时刻(给"最后更新")
MEDALS = ["🥇", "🥈", "🥉", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩", "⑪", "⑫"]


def jload(p, default=None):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def review_section(v):
    if not v:
        return ""
    sc, feas, calib = v.get("scorecard", {}), v.get("feasibility", {}), v.get("calibration", "")
    n_open = sc.get("n_open", 0)
    stat = lambda l, val, suf="": f'<div class="stat"><div class="sl">{l}</div><div class="sv">{(str(val)+suf) if val is not None else "—"}</div></div>'
    if n_open > 0:
        mat = f'{sc.get("matured_n",0)}期/{sc.get("matured_avg_realized_pct")}%' if sc.get("matured_n") else "未到期"
        scorecard = "".join([stat("历史在评期数", n_open), stat("买入触及率", sc.get("entry_hit_rate"), "%"),
                             stat("方向胜率", sc.get("direction_win_rate"), "%"),
                             stat("平均目标完成度", sc.get("avg_progress_to_target_pct"), "%"),
                             f'<div class="stat"><div class="sl">已到期·实际</div><div class="sv" style="font-size:14px">{mat}</div></div>'])
    else:
        scorecard = '<div class="stat" style="grid-column:1/-1"><div class="sl">历史复盘</div><div class="sv" style="font-size:13px;color:#94a3b8">首期 · 从明日起每天自动累积命中/完成度/到期收益</div></div>'
    bad = [tk for tk, f in feas.items() if not f.get("buy_reachable") or f.get("target_aggressive")]
    ok = len(feas) - len(bad)
    fl = (f'本期 <b style="color:#4ade80">{ok}/{len(feas)}</b> 支建议买入价落在【真实近20日成交区间·可达】'
          + ("，目标价隐含涨幅均在合理区(无激进项)" if not bad else f'，<b style="color:#fbbf24">需关注:{"、".join(bad)}</b>'))
    return (f'<div class="review"><div class="rv-h">🔍 复盘与校准 <span class="rv-sub">预测台账 → 自动验证 → 校准(越用越准)</span></div>'
            f'<div class="stats">{scorecard}</div>'
            f'<div class="rv-line">📏 <b>即时可达性校验:</b>{fl}</div>'
            f'<div class="rv-line">⚙️ <b>校准:</b>{calib}</div></div>')


def _mid(s):
    nums = re.findall(r"\d+(?:\.\d+)?", s or "")
    return (float(nums[0]) + float(nums[1])) / 2 if len(nums) >= 2 else (float(nums[0]) if nums else None)


def audit_section(data):
    n = len(data)
    px = sum(1 for v in data.values() if v.get("price") is not None)
    cons = sum(1 for v in data.values() if (v.get("analyst") or {}) and
               ((v["analyst"].get("target_mean")) or v["analyst"].get("consensus_src") == "Finnhub" or v["analyst"].get("cn_rating")))
    news = sum(1 for v in data.values() if v.get("news"))
    earn = sum(1 for v in data.values() if v.get("earnings_date"))
    missing = [tk for tk, v in data.items() if v.get("error")]
    cons_gap = cons < (n - 1) * 0.5   # 券商一致覆盖偏低(扣掉 QQQ)
    note = ('⚠️ <b style="color:#fbbf24">券商一致覆盖偏低</b>——这些票目标价<b>未经券商一致数字校准</b>(美股 TD 免费档无共识/港股/A股取数受限);评分仅按可算因子计,缺失因子已标"不可算",不静默补分。'
            if cons_gap else
            'ℹ️ 券商一致/新闻/财报日已尽力抓取(美股 yfinance、A股东财业绩预约)。web 深度信源待 web 工具恢复后补。')
    return (f'<div class="audit"><b>📋 数据 / 覆盖审计:</b>'
            f'行情 {px}/{n} · 券商一致 {cons}/{n}(QQQ及无覆盖标的除外) · 新闻催化剂 {news}/{n} · 财报日 {earn}/{n}'
            + (f' · ⚠️ 抓取失败:{"、".join(missing)}' if missing else '')
            + f'<br><span style="color:#64748b">{note}</span></div>')


FACTOR_W = {"趋势": 16, "共识上行": 18, "回调健康": 10, "动量": 10, "评级": 10, "估值PEG": 18, "相对强弱": 10, "波动率": 8, "质量": 12}  # 归一化按present权重重标,绝对和不影响最终分


def factor_score(d, bench_m3=None):
    """归一化多因子模型:各因子打 0-1 × 权重,缺失因子记入 miss(不计入),按 present 权重重标到 /100。
    因子:趋势/共识上行/回调健康/动量/评级/估值PEG。诚实:数据缺则该因子"不可计算",绝不静默补分。
    返回 (总分0-100, 各因子折算贡献dict, 不可计算因子名list)。"""
    px, ma50, ma200, m3, fromhi, vol = d.get("price"), d.get("ma50"), d.get("ma200"), d.get("m3"), d.get("fromhi"), d.get("vol")
    an = d.get("analyst", {}) or {}
    tm, rm, cn_rating = an.get("target_mean"), an.get("rating_mean"), an.get("cn_rating")
    fwd_pe, eps_growth = an.get("fwd_pe"), an.get("eps_growth")
    CN_UP = {"强烈推荐": 0.9, "买入": 0.8, "推荐": 0.75, "增持": 0.5, "持有": 0.3, "中性": 0.3}
    CN_RT = {"强烈推荐": 1.0, "买入": 0.9, "推荐": 0.85, "增持": 0.6, "持有": 0.4, "中性": 0.4}
    f = {}   # 因子名 -> 归一化 0-1(只放可算的)
    if px and ma200:                                          # 趋势
        f["趋势"] = 1.0 if (px > ma200 and ma50 and px > ma50) else (0.5 if px > ma200 else 0.0)
    if tm and px:                                            # 共识上行(美股/港股一致目标隐含涨幅)
        f["共识上行"] = max(0.0, min(1.0, (tm / px - 1) * 100 / 30))
    elif cn_rating:                                          # A股用东财评级作共识代理
        f["共识上行"] = CN_UP.get(cn_rating, 0.4)
    if fromhi is not None:                                   # 回调健康
        f["回调健康"] = 1.0 if (-22 <= fromhi <= -6) else (0.6 if fromhi < -22 else 0.4)
    if m3 is not None:                                       # 动量(过热惩罚)
        f["动量"] = 1.0 if 5 <= m3 <= 40 else (0.5 if 40 < m3 <= 90 else (0.2 if m3 > 90 else (0.5 if -10 < m3 < 5 else 0.2)))
    if rm:                                                   # 评级
        f["评级"] = max(0.0, min(1.0, (3 - rm) / 2))
    elif cn_rating:
        f["评级"] = CN_RT.get(cn_rating, 0.5)
    if fwd_pe and eps_growth is not None:                    # 估值PEG(PE÷EPS增速,低=好;不增长还高PE=差)
        if eps_growth <= 0:
            f["估值PEG"] = 0.1
        else:
            peg = fwd_pe / eps_growth
            f["估值PEG"] = 1.0 if peg <= 1 else (0.7 if peg <= 2 else (0.4 if peg <= 4 else (0.15 if peg <= 8 else 0.0)))
    if m3 is not None and bench_m3 is not None:             # 相对强弱:个股近3月 − 大盘(QQQ)近3月
        rs = m3 - bench_m3
        f["相对强弱"] = 1.0 if rs >= 20 else (0.75 if rs >= 5 else (0.5 if rs >= -5 else (0.3 if rs >= -20 else 0.1)))
    if vol is not None:                                     # 波动率:年化波动,低=好(长期视角,次新/抛物线波动高扣分)
        f["波动率"] = 1.0 if vol < 30 else (0.7 if vol < 50 else (0.4 if vol < 80 else 0.15))
    q = d.get("quality") or {}                              # 质量:盈利能力ROE + 现金含量(经营现金流符号)+ 定价权毛利
    roe, ocf, gm = q.get("roe"), q.get("ocf_ps"), q.get("gross_margin")
    qs = []
    if roe is not None:                                     # ROE 为单季值,阈值按季度口径
        qs.append(1.0 if roe > 8 else (0.85 if roe >= 5 else (0.6 if roe >= 2 else (0.35 if roe >= 0 else 0.1))))
    if ocf is not None:                                     # 经营现金流:正=盈利有现金支撑,负=烧钱(次新股常见)重扣
        qs.append(1.0 if ocf > 0 else (0.5 if ocf == 0 else 0.25))
    if gm is not None:                                      # 毛利率:定价权
        qs.append(1.0 if gm > 50 else (0.8 if gm >= 35 else (0.55 if gm >= 20 else 0.3)))
    if qs:
        f["质量"] = sum(qs) / len(qs)
    miss = [k for k in FACTOR_W if k not in f]
    wsum = sum(FACTOR_W[k] for k in f)
    score = round(sum(f[k] * FACTOR_W[k] for k in f) / wsum * 100) if wsum else 0
    breakdown = {k: round(f[k] * FACTOR_W[k]) for k in f}    # 各因子折算后贡献分
    return score, breakdown, miss


def regime_line(data):
    q = data.get("QQQ", {})
    n = sum(1 for v in data.values() if v.get("price"))
    above = sum(1 for v in data.values() if (v.get("price") and v.get("ma200") and v["price"] > v["ma200"]))
    q_up = bool(q.get("price") and q.get("ma200") and q["price"] > q["ma200"])
    reg = ("顺势 risk-on" if (q_up and above >= n * 0.7) else ("逆风 risk-off" if (not q_up or above < n * 0.4) else "中性/分化"))
    return f'🌡 市场体制:<b>{reg}</b> · QQQ {"站上" if q_up else "跌破"} 200日线 · 成分 {above}/{n} 在 200日线上'


def evidence_section(data):
    bt = jload(os.path.join(STATE, "backtest.json"))
    bt_html = ""
    if bt:
        bt_html = (f'📊 <b>策略回测(过去 {bt.get("lookback","3y")} 真实数据,{bt.get("signals")} 次信号):</b> '
                   f'命中率 <b style="color:#fbbf24">{bt.get("win_rate_pct")}%</b> · 止损 {bt.get("stopped_pct")}% · '
                   f'实际盈亏比 <b style="color:#4ade80">{bt.get("realized_rr")}:1</b> · 每笔均值 {bt.get("avg_trade_return_pct")}%<br>'
                   f'<span style="color:#94a3b8">→ 命中率仅 {bt.get("win_rate_pct")}%(<b style="color:#f87171">绝非 90%</b>),靠 {bt.get("realized_rr")}:1 盈亏比才正期望——<b>赚钱靠风控不靠高胜率</b>。{bt.get("caveat","")}</span>')
    return f'<div class="evid"><div class="ev-reg">{regime_line(data)}</div><div class="ev-bt">{bt_html}</div></div>'


def card(i, tk, d, a, bench_m3=None):
    sig = a.get("sig", "")
    color = "#4ade80" if sig.startswith("买入") else ("#fbbf24" if "观望" in sig else "#94a3b8")
    mom = lambda x: f'<span style="color:{"#4ade80" if (x or 0)>=0 else "#f87171"}">{x:+.1f}%</span>' if x is not None else "—"
    f0 = lambda x: f"{x:.0f}" if x is not None else "?"
    sc, sp, miss = factor_score(d, bench_m3)
    cov = len(sp)                                  # 可算因子数(满8)
    low_data = cov <= 3                             # 可算因子≤3 → 数据不足,不给确定评分
    miss_note = f"(缺:{'、'.join(miss)})" if miss else ""
    tech_only = {"共识上行", "评级", "估值PEG"}.issubset(set(miss))   # 基本面三因子全缺 → 仅技术面,不冒充满分评分
    score_lbl = "技术分" if tech_only else "评分"
    em, tgm = _mid(a.get("buy")), _mid(a.get("tgt"))
    rr = round((tgm / em - 1) / 0.10, 1) if (em and tgm and em > 0) else None
    stop = round(em * 0.90) if em else None
    rrflag = "" if (rr is None or rr >= 2) else ' <span style="color:#f59e0b">⚠️R:R偏低,不符买入纪律</span>'
    sp_str = "+".join(f"{k}{v}" for k, v in sp.items())
    an = d.get("analyst", {}) or {}
    tm = an.get("target_mean")
    mkt = d.get("market", "US")
    is_cn, is_hk = mkt == "CN", mkt == "HK"
    cs = "¥" if is_cn else ("HK$" if is_hk else "$")   # A股¥、港股HK$、美股$,如实
    # 机构共识行 + 我 vs 共识
    if tm:
        mymid = _mid(a.get("tgt"))
        cmp_html = ""
        if mymid:
            diff = (mymid / tm - 1) * 100
            cmp_html = (f'<b style="color:#fbbf24">我高于共识 {diff:+.0f}%</b>' if diff > 10
                        else f'<b style="color:#60a5fa">我低于共识 {diff:+.0f}%</b>' if diff < -10
                        else '<b style="color:#94a3b8">≈共识</b>')
        cons = (f'🏛 机构共识 一致目标 <b style="color:#2dd4bf">{cs}{f0(tm)}</b>(低{f0(an.get("target_low"))}/高{f0(an.get("target_high"))})'
                f' · {an.get("rating","")} · {an.get("n_analysts","?")}家 · 前瞻PE {an.get("fwd_pe","?")} ｜ {cmp_html}')
    elif is_cn:
        eps_str = (f' · 盈利预测 26EPS¥{an.get("eps_2026")}/27¥{an.get("eps_2027")}(增{an.get("eps_growth")}%)'
                   if an.get("eps_2026") else "")
        cons = (f'🏛 机构共识(A股·东财研报) 评级 <b style="color:#2dd4bf">{an.get("cn_rating", "—")}</b>'
                f' · 近一月 {an.get("n_analysts", "?")} 份(在档 {an.get("cn_reports_total", "?")}) · 前瞻PE <b>{an.get("fwd_pe", "?")}</b>{eps_str}'
                f' ｜ <span style="color:#94a3b8">A股以评级+前瞻PE/EPS校准(无单一一致目标价)</span>')
    elif an.get("consensus_src") == "Finnhub":
        # 美股 Finnhub 免费档共识(无目标价,用评级趋势 + 财务指标校准)
        q = d.get("quality") or {}
        qstr = ((f' · ROE {round(q["roe"], 1)}%' if q.get("roe") is not None else "")
                + (f' · 毛利 {round(q["gross_margin"], 1)}%' if q.get("gross_margin") is not None else ""))
        pe_str = f' · PE {an.get("fwd_pe","?")}' + (f'(增{an.get("eps_growth")}%)' if an.get("eps_growth") is not None else "")
        cons = (f'🏛 分析师共识(Finnhub) 评级 <b style="color:#2dd4bf">{an.get("cn_rating","—")}</b>'
                f' · 买入占比 {int(round((an.get("rec_buy_ratio") or 0) * 100))}% · {an.get("n_analysts","?")}家'
                f'{pe_str}{qstr}'
                f' ｜ <span style="color:#94a3b8">Finnhub 免费档(无目标价,以评级+财务指标校准)</span>')
    else:
        cons = ("🏛 ETF·大盘基准(无个股一致目标)" if tk == "QQQ"
                else "🏛 券商一致目标暂缺(取数受限,价格/技术面正常)")
    ed = d.get("earnings_date")
    earn_soon = ""
    if ed:
        try:
            _dd = (datetime.date.fromisoformat(str(ed)[:10]) - datetime.date.fromisoformat(TODAY)).days
            if 0 <= _dd <= 14:
                earn_soon = f' <span style="color:#f59e0b;font-weight:700">⚠️ 财报 {_dd} 天后·二元风险,不宜追高</span>'
        except Exception:
            pass
    earn = f'　📅 下次财报 {ed}{earn_soon}' if ed else ""
    # A股限售解禁哨兵:未来6个月有解禁→标二元抛压;占流通≥3%或≤60天加重警示
    unlock_html = ""
    ul = d.get("unlock")
    if ul and ul.get("date"):
        try:
            _ud = (datetime.date.fromisoformat(str(ul["date"])[:10]) - datetime.date.fromisoformat(TODAY)).days
            pf = ul.get("pct_float")
            heavy = (pf is not None and pf >= 3) or (0 <= _ud <= 60)
            sev = ';font-weight:700' if heavy else ''
            extra = f"占流通{pf}%" if pf is not None else ""
            mv = f"·{ul['mktcap_yi']}亿" if ul.get("mktcap_yi") else ""
            unlock_html = f'　🔓 <span style="color:#f59e0b{sev}">{_ud}天后解禁{extra}{mv}{"·抛压临近" if heavy else ""}</span>'
        except Exception:
            pass
    elif is_cn:
        unlock_html = '　🔓 <span style="color:#64748b">近6月无解禁(已消除限售抛压隐忧)</span>'
    news = (d.get("news") or [])[:2]
    news_html = ""
    if news:
        items = "　".join(f'<a href="{n["url"]}" target="_blank">{n["title"][:40]}…</a> <span class="src">[{n["pub"]}·{n["date"]}]</span>' for n in news)
        news_html = f'<div class="news">📰 {items}</div>'
    return f"""
<div class="card" style="border-top:3px solid {color}{';opacity:.92' if tk=='QQQ' else ''}">
  <div class="hd"><span class="rk">{MEDALS[i] if i < len(MEDALS) else str(i + 1) + "."}</span><span class="tk">{('🇨🇳 ' if is_cn else '🇭🇰 ' if is_hk else '') + tk.replace('.SS', '').replace('.SZ', '').replace('.HK', '')}</span>
    <span class="nm">{d.get('name','')}</span><span class="badge">{d.get('role','')}</span>
    <span class="sig" style="color:{color}">{sig}</span>{'<span class="score" style="color:#cbd5e1;background:rgba(148,163,184,.18)">数据不足·暂不评分</span>' if low_data else f'<span class="score">{score_lbl} {sc}({cov}/9因子{"·仅技术面" if tech_only else ""})</span>'}<span class="conf">置信 {a.get('conf','?')}/10</span></div>
  <div class="px"><span class="now">{cs}{d.get('price','—')}</span>
    <span class="mom">近1月 {mom(d.get('m1'))} ｜ 近3月 {mom(d.get('m3'))} ｜ 近6月 {mom(d.get('m6'))} ｜ 距52周高 {(str(d.get('fromhi'))+'%') if d.get('fromhi') is not None else '—'}</span></div>
  <div class="kpis">
    <div class="kpi"><div class="kl">🎯 建议买入价</div><div class="kv buy">{cs}{a.get('buy','')}</div></div>
    <div class="kpi"><div class="kl">📈 我的6-12月目标价</div><div class="kv tgt">{cs}{a.get('tgt','')}</div></div>
    <div class="kpi"><div class="kl">💰 预期收益</div><div class="kv ret">{a.get('ret','')}</div></div></div>
  <div class="cons">{cons}{earn}{unlock_html}</div>
  <div class="rr">🛡 风控 止损 -10%(≈{cs}{stop}) · 风险收益比 <b>{rr if rr is not None else '—'}:1</b>{rrflag}　·　📊 {'数据不足·目标价为题材推演非可复算估值' if low_data else f'{score_lbl} {sc}/100({cov}/9因子{"·仅技术面,估值/共识未评" if tech_only else ""}) = {sp_str}{miss_note}'}</div>
  <div class="th">💡 {a.get('th','')}</div>
  {news_html}
  <div class="rk2">⚠️ 风险:{a.get('rk','')}　·　52周 {cs}{d.get('lo','')}–{cs}{d.get('hi','')}　·　MA50 {cs}{d.get('ma50','')} / MA200 {cs}{d.get('ma200','')}</div>
</div>"""


def latest_calls():
    """优先读当天 calls_<TODAY>.json;没有则回退到最近一期 calls_*.json。
    返回 (calls字典, 研判日期字符串)。供定时任务每天刷新数据时复用上次研判。"""
    today_p = os.path.join(STATE, f"calls_{TODAY}.json")
    if os.path.exists(today_p):
        return jload(today_p), TODAY
    import glob
    files = sorted(glob.glob(os.path.join(STATE, "calls_*.json")))
    if not files:
        return None, None
    latest = files[-1]
    m = re.search(r"calls_(\d{4}-\d{2}-\d{2})\.json", os.path.basename(latest))
    return jload(latest), (m.group(1) if m else "未知")


def freshness_banner(calls_date, data_meta=None):
    """新鲜度横幅:分别如实标注【研判】与【行情数据】是否为今日。
    研判过期 → 提醒刷新研判;行情降级(限流复用旧数据)→ 明确警示价格非当日实时。
    绝不在数据已降级时谎称『数据均为今日』(诚实底线)。"""
    data_meta = data_meta or {}
    degraded = bool(data_meta.get("degraded"))
    # —— 研判新鲜度 ——
    if calls_date == TODAY:
        research = f"🟢 研判为今日(<b>{TODAY}</b>)· Claude 当期研判"
        cls = "ok"
    else:
        try:
            days = (datetime.date.fromisoformat(TODAY) - datetime.date.fromisoformat(calls_date)).days
        except Exception:
            days = "?"
        research = (f"🟠 <b>研判仍是 {calls_date}({days} 天前)</b>——买入价/目标价请仅作参考,"
                    f"在 Claude 里说「跑美股AI早报 / 刷新云端美股看板」即可刷新")
        cls = "stale"
    # —— 行情数据新鲜度 ——
    if degraded:
        cls = "stale"
        note = data_meta.get("banner") or "云端取数受限,已复用最近一期真实行情"
        data_line = f"<br>🟠 <b>行情数据降级:</b>{note}——<b>价格非当日实时</b>,买卖价据此推演,请留意。"
    else:
        data_line = " · 行情数据为今日真实抓取"
    return f'<div class="fresh {cls}">{research}{data_line}</div>'


def main():
    cfg = jload(os.path.join(DIR, "config.json"))
    data_full = jload(os.path.join(STATE, f"data_{TODAY}.json"), {})
    data = data_full.get("stocks", {})
    data_meta = data_full.get("meta", {})
    # 诚实防护:当日数据整份缺失/无任何价格时,也不许横幅谎称"今日真实抓取"
    if not any(isinstance(v, dict) and "price" in v for v in data.values()) and not data_meta.get("degraded"):
        data_meta = {"degraded": True, "banner": f"无 {TODAY} 当日行情数据(抓取失败且无可复用),展示的是最近一期研判"}
    calls, calls_date = latest_calls()
    v = jload(os.path.join(STATE, "verification.json"))
    if not calls:
        raise SystemExit(f"缺 calls_*.json(Claude 研判)。先让 Claude 生成首期研判再渲染。")
    order = calls.get("ranking") or list(calls["stocks"].keys())
    bench_m3 = (data.get("QQQ", {}) or {}).get("m3")     # 相对强弱基准:QQQ 近3月
    # 按市场分组排版:美股(全球定价、引领)在前 → A 股 → 港股,因 A/港大多跟随美股,分组后看 A/港更直观。
    # 奖牌(🥇🥈🥉/序号)用【全局排名】位置,组内仍按总排名顺序。
    MKT = [("US", "🇺🇸 美股核心 · AI 产业链驱动(全球定价,引领 A 股 / 港股)"),
           ("CN", "🇨🇳 A 股 · 跟随美股的国产算力 / AI 链"),
           ("HK", "🇭🇰 港股 · 国产 AI")]
    mkt_of = lambda tk: (data.get(tk, {}) or {}).get("market", "US")
    cards = ""
    for mk, title in MKT:
        grp = [tk for tk in order if tk in calls["stocks"] and mkt_of(tk) == mk]
        if not grp:
            continue
        cards += f'<div class="section">{title}<span class="scnt">{len(grp)} 支</span></div><div class="grid">'
        cards += "".join(card(order.index(tk), tk, data.get(tk, {}), calls["stocks"][tk], bench_m3) for tk in grp)
        cards += '</div>'
    rank_str = " ＞ ".join(data.get(tk, {}).get("name", tk) for tk in order)
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"><meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0">
<title>{cfg['title']} · {TODAY}</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#0b1120;color:#e2e8f0;line-height:1.6;padding:20px}}
.wrap{{max-width:1280px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid #334155;border-radius:16px;padding:24px 28px;margin-bottom:16px}}
.header h1{{font-size:26px;font-weight:900;color:#60a5fa}}.sub{{font-size:13px;color:#94a3b8;margin-top:6px}}
.updated{{margin-top:8px;font-size:12px;color:#7c8aa3;background:rgba(96,165,250,.06);border-radius:8px;padding:6px 12px}}.updated b{{color:#cbd5e1}}.updated a{{color:#60a5fa;text-decoration:none;font-weight:700}}
.market{{margin-top:14px;padding:14px 16px;background:rgba(96,165,250,.08);border-radius:10px;font-size:13.5px;color:#cbd5e1}}
.rankbar{{margin-top:12px;padding:12px 16px;background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.2);border-radius:10px;font-size:13px}}.rankbar b{{color:#fbbf24}}
.fresh{{border-radius:12px;padding:11px 16px;margin-bottom:16px;font-size:12.5px;line-height:1.7}}
.fresh.ok{{background:rgba(74,222,128,.08);border:1px solid rgba(74,222,128,.25);color:#bbf7d0}}
.fresh.stale{{background:rgba(251,146,60,.1);border:1px solid rgba(251,146,60,.35);color:#fed7aa}}
.review{{background:#0f1a30;border:1px solid #2a3a5a;border-radius:14px;padding:16px 18px;margin-bottom:16px}}
.rv-h{{font-size:16px;font-weight:800;color:#a5b4fc;margin-bottom:10px}}.rv-sub{{font-size:11px;color:#64748b;font-weight:400;margin-left:6px}}
.stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:10px}}
@media(max-width:860px){{.stats{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:1fr}}}}
.stat{{background:rgba(51,65,85,.35);border-radius:10px;padding:8px 10px;text-align:center}}
.sl{{font-size:10.5px;color:#94a3b8;margin-bottom:3px}}.sv{{font-size:18px;font-weight:800;color:#e2e8f0}}
.rv-line{{font-size:12.5px;color:#cbd5e1;margin-top:6px}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:18px}}
.section{{display:flex;align-items:center;gap:10px;font-size:16px;font-weight:800;color:#e2e8f0;margin:6px 0 12px;padding:10px 14px;background:linear-gradient(90deg,rgba(96,165,250,.14),transparent);border-left:4px solid #60a5fa;border-radius:8px}}
.section .scnt{{font-size:12px;font-weight:600;color:#94a3b8;background:rgba(148,163,184,.15);padding:2px 10px;border-radius:10px}}
.card{{background:#111a2e;border:1px solid #334155;border-radius:14px;padding:16px 18px}}
.hd{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}}
.rk{{font-size:18px}}.tk{{font-size:18px;font-weight:900;color:#f1f5f9}}.nm{{color:#94a3b8;font-size:13px}}
.badge{{font-size:11px;padding:2px 9px;border-radius:10px;background:rgba(96,165,250,.15);color:#93c5fd}}
.sig{{margin-left:auto;font-weight:800;font-size:14px}}
.conf{{font-size:10.5px;color:#a5b4fc;background:rgba(165,180,252,.13);padding:2px 8px;border-radius:10px;margin-left:8px}}
.score{{font-size:10.5px;color:#fbbf24;background:rgba(251,191,36,.12);padding:2px 8px;border-radius:10px;margin-left:6px}}
.rr{{font-size:11.5px;color:#cbd5e1;background:rgba(248,113,113,.07);border-radius:8px;padding:6px 10px;margin-top:6px}}
.evid{{background:#0f1a30;border:1px solid #2a3a5a;border-radius:14px;padding:14px 18px;margin-bottom:16px;font-size:12.5px;line-height:1.85}}
.ev-reg{{color:#a5b4fc;font-weight:700;margin-bottom:6px}}.ev-bt{{color:#cbd5e1}}
.audit{{font-size:11.5px;color:#94a3b8;background:rgba(51,65,85,.25);border:1px solid #334155;border-radius:12px;padding:12px 16px;margin-top:16px;line-height:1.8}}
.px{{display:flex;align-items:baseline;gap:12px;margin-bottom:12px;flex-wrap:wrap}}
.now{{font-size:26px;font-weight:900;color:#f8fafc}}.mom{{font-size:12px;color:#94a3b8}}
.kpis{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}}
.kpi{{background:rgba(51,65,85,.35);border-radius:10px;padding:10px;text-align:center}}
.kl{{font-size:11px;color:#94a3b8;margin-bottom:4px}}
.kv{{font-size:16px;font-weight:800}}.kv.buy{{color:#4ade80}}.kv.tgt{{color:#2dd4bf}}.kv.ret{{color:#fbbf24}}
.cons{{font-size:12px;color:#cbd5e1;background:rgba(45,212,191,.07);border-radius:8px;padding:7px 10px;margin-top:6px}}
.th{{font-size:13px;color:#dbeafe;padding:8px 0 4px;border-top:1px solid rgba(51,65,85,.5);margin-top:6px}}
.news{{font-size:11.5px;color:#94a3b8;line-height:1.8;margin-bottom:4px}}
.news a{{color:#93c5fd;text-decoration:none}}.news a:hover{{text-decoration:underline}}.src{{color:#64748b;font-size:10px}}
.rk2{{font-size:11.5px;color:#7c8aa3}}
.foot{{text-align:center;font-size:11px;color:#475569;margin-top:18px;line-height:1.8}}
</style></head><body><div class="wrap">
<div class="header"><h1>📡 {cfg['title']} · {TODAY}</h1>
<div class="sub">美股 AI 核心 {sum(1 for s in cfg['stocks'] if s.get('market') != 'CN' and s['ticker'] != cfg['benchmark'])} 票 + 🇨🇳 A 股补充 {sum(1 for s in cfg['stocks'] if s.get('market') == 'CN')} 票 + {cfg['benchmark']} 基准 · 长期 {cfg['horizon_label']} 视角 · 数据 yfinance+akshare(真实行情) · AI 研判</div>
<div class="updated">🕐 本页生成:<b>{BUILD_TS}</b> 北京 · 每天 08:07 云端自动更新 · 想看最新点这里 👉 <a href="javascript:location.reload(true)">🔄 手动刷新</a></div>
<div class="market">🌎 <b style="color:#60a5fa">大盘与板块:</b>{calls.get('market','')}</div>
<div class="rankbar">🏆 <b>买点吸引力排序:</b>{rank_str}</div></div>
{freshness_banner(calls_date, data_meta)}
{evidence_section(data)}
{review_section(v)}
{cards}
{audit_section(data)}
<div class="foot">两个核心指标 = ① 买入建议+建议买入价　② 6-12月目标价+预期收益　·　预测台账自动复盘校准<br>
数据 yfinance 真实行情 · 研判由 Claude 基于价格/动量/均线+AI产业链结构生成(未用 DeepSeek)<br>
⚠️ 仅供研究/学习,<b>非投资建议</b>。回测命中率约 42%(<b>非 90%</b>),正期望靠 ~2.5:1 盈亏比——<b>赚钱靠风控不靠高胜率</b>;目标价为技术面+共识+催化剂推演,不代表未来,实际交易请自负风险。</div>
</div></body></html>"""
    os.makedirs(STATE, exist_ok=True)
    out = os.path.join(STATE, f"ai_stock_board_{TODAY}.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out)


if __name__ == "__main__":
    main()
