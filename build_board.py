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
    # 口径拆分:体检指出"行情19/19"把冻结复用也算进覆盖,掩盖了长飞冻结15期——当日真值与复用分开示人
    px_fresh = sum(1 for v in data.values() if v.get("price") is not None and not v.get("stale"))
    px_stale = [f"{tk}(复用自{v.get('stale_date','?')})" for tk, v in data.items()
                if v.get("price") is not None and v.get("stale")]
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
            f'行情 {px_fresh}/{n} 当日真值{f" + {len(px_stale)} 复用({chr(12289).join(px_stale)})" if px_stale else ""} · 券商一致 {cons}/{n}(QQQ为ETF无评级;取数受限标的如实缺) · 新闻催化剂 {news}/{n} · 财报日 {earn}/{n}'
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
  <div class="rr">🛡 风控 止损 -10%(≈{(cs + str(stop)) if stop is not None else '—'}) · 风险收益比 <b>{rr if rr is not None else '—'}:1</b>{rrflag}　·　📊 {'数据不足·目标价为题材推演非可复算估值' if low_data else f'{score_lbl} {sc}/100({cov}/9因子{"·仅技术面,估值/共识未评" if tech_only else ""}) = {sp_str}{miss_note}'}</div>
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


def qa_ctx(data, calls, calls_date, v):
    """给「盘势问答」组装紧凑语境:本期 19 票真实行情+研判+复盘记分卡。
    嵌进看板页,问答时与同光早报要闻一起喂给 DeepSeek——只答有据可依的,不编数字。"""
    sc = (v or {}).get("scorecard", {})
    stocks = {}
    for tk, a in calls["stocks"].items():
        d = data.get(tk, {})
        stocks[tk] = {
            "名": d.get("name", tk), "市场": d.get("market", "US"), "价": d.get("price"),
            "涨1月%": d.get("m1"), "涨3月%": d.get("m3"), "涨6月%": d.get("m6"),
            "距52周高%": d.get("fromhi"), "MA50": d.get("ma50"), "MA200": d.get("ma200"),
            "年化波动%": d.get("vol"), "财报": d.get("earnings_date"),
            "信号": a.get("sig"), "置信": a.get("conf"), "买入价": a.get("buy"),
            "目标价": a.get("tgt"), "预期收益": a.get("ret"),
            "逻辑": a.get("th"), "风险": a.get("rk"),
        }
    # 第三路语料:最新「全球市场头条」(宏观/地缘+科技双档,含传导链)——有则嵌入,无则如实缺席
    news_ctx = None
    import glob as _glob
    nfiles = [f for f in sorted(_glob.glob(os.path.join(STATE, "news_*.json")))
              if re.search(r"news_\d{4}-\d{2}-\d{2}\.json$", f)]
    if nfiles:
        try:
            nj = jload(nfiles[-1])
            _cat_zh = {"macro": "宏观", "oil": "石油", "tech": "科技"}
            news_ctx = {"date": nj.get("asof"),
                        "条目": [f"[{_cat_zh.get(it.get('cat'), '其他')}] {it.get('title')} | 传导:{it.get('chain')}"
                               for it in nj.get("items", [])[:15]]}
        except Exception:
            pass
    # 第四路语料:宏观快线(BLS官方/中美利率/大宗实时/社融)——蒸馏艾丽框架后补齐的宏观层
    macro_ctx = None
    mfiles = [f for f in sorted(_glob.glob(os.path.join(STATE, "macro_*.json")))
              if re.search(r"macro_\d{4}-\d{2}-\d{2}\.json$", f)]
    if mfiles:
        try:
            mj = jload(mfiles[-1])
            macro_ctx = {"date": mj.get("asof"), "数据": mj.get("blocks")}
        except Exception:
            pass
    return {
        "asof": calls_date,
        "宏观快线": macro_ctx,
        "大盘": re.sub(r"<[^>]+>", "", calls.get("market", "")),
        "复盘记分卡": {"入场触及率%": sc.get("entry_hit_rate"), "方向胜率%": sc.get("direction_win_rate"),
                  "平均目标完成度%": sc.get("avg_progress_to_target_pct"),
                  "口径": "仅统计买入信号且买入价真实触及的仓位"},
        "全球头条": news_ctx,
        "标的": stocks,
    }


# 「盘势问答」面板:纯前端直连 DeepSeek(已实测 api.deepseek.com 允许 andy4576.com 的浏览器 CORS)。
# 凭证走 __QA_KEY__ 占位符,与 __DISPATCH_TOKEN__ 同一套防泄露模式:CI 只注入 docs 加密版,不入库。
# 语料 = 页内嵌的本期看板语境(@QACTX@) + 按需同源拉取 /tongguang/data/index.json 的同光早报要闻。
QA_TMPL = """
<div class="qa" id="qa-panel">
 <div class="qa-h" onclick="qaToggle()"><span class="qa-ico">💬</span>盘势问答<span class="qa-new">AI</span><span class="qa-sub">问"这波下跌何时扭转"这类问题 · 基于本期研判+同光要闻+全球头条 · DeepSeek 引擎</span><span id="qa-arrow" style="margin-left:auto">▾</span></div>
 <div class="qa-body" id="qa-body">
  <div class="qa-basis" onclick="qaBasisToggle()">ℹ️ 回答依据(点开看问答基于什么逻辑、关联了哪些数据)</div>
  <div class="qa-basis-body hide" id="qa-basis-body">
   <b>每次回答喂给引擎三路语料 + 一套写死纪律:</b><br>
   ① <b>本期看板语境(页内嵌)</b>:19 票真实行情(价/动量/MA50/MA200/波动/财报日)+ 本期研判(信号/买入价/目标价/逻辑/风险)+ 复盘记分卡(入场触及率/方向胜率/目标完成度);<br>
   ② <b>同光AI早报要闻(实时拉取)</b>:Top5/Tier0/质量≥8 的最新 24 条,带「这意味着」决策洞察;<br>
   ③ <b>全球市场头条(页内嵌)</b>:宏观/石油/科技三档最新一期,带传导链;<br>
   ④ <b>实时行情工具(按需现抓)</b>:问最新价/市值/今日涨跌或质疑数据时,AI 自动实时抓取——A股/港股走腾讯行情、美股走 Finnhub,回答会同时给"实时 vs 看板快照"两套数字并解释差异;<br>
   ⑤ <b>宏观快线(页内嵌)</b>:BLS官方非农/失业率/CPI(实际vs前值)、中美10Y利差、黄金原油实时、社融——宏观问题的数据锚;<br>
   <b>纪律</b>:只答有据可依的、缺的直说"语料未覆盖"、"何时回转"必须转成【观察条件+信号+三情景时间量级】而非预测日期、绝不编造价格/券商目标价、末尾固定免责。每条回答下方会标注本次实际用到的语料。
  </div>
  <div class="qa-chips">
   <button class="chip" onclick="qaAsk('看板里A股这几只普遍在跌,这轮回调大概什么时候能企稳回转?给出要观察的价位信号、催化剂和乐观/中性/悲观三种情景。')">📉 A股何时企稳?</button>
   <button class="chip" onclick="qaAsk('寒武纪最近在往下掉,现在该怎么办?出现什么信号说明趋势扭转?')">🇨🇳 寒武纪怎么办?</button>
   <button class="chip" onclick="qaAsk('结合同光早报的AI行业最新动向,美股AI链现在优先配置谁,为什么?')">🇺🇸 美股AI链配谁?</button>
  </div>
  <div class="qa-log" id="qa-log"></div>
  <div class="qa-inrow">
   <textarea id="qa-in" rows="2" placeholder="问点什么…例如:这波下跌趋势大概什么时候可能扭转?(Enter 发送,Shift+Enter 换行)"></textarea>
   <button id="qa-send" onclick="qaSend()">发送</button>
  </div>
  <div class="qa-foot">⚠️ 回答由 AI 基于本页真实数据与同光早报生成,仅研究示范、<b>非投资建议</b>;未来无法被预测,"何时回转"只能给<b>条件与信号</b>,不是承诺。</div>
 </div>
</div>
<button id="qa-fab" onclick="qaFab()">💬 盘势问答</button>
<script>
const QK="__QA_KEY__";
const FHK="__FH_KEY__";
const QACTX=@QACTX@;
let QAHIST=[], QABUSY=false, TGCACHE=null;
// ===== 实时行情工具(function calling):A股/港股走腾讯行情(script注入,免key免CORS),美股走 Finnhub =====
const QATOOLS=[{type:"function",function:{name:"get_realtime_quote",
  description:"实时抓取标的当前行情:现价/涨跌%/今日高低/总市值(A股为亿元人民币,港股约亿港元,美股为百万美元)。凡用户问最新价格/市值/今天涨跌,或质疑看板数据、要求核实数字时,必须先调用本工具再回答。",
  parameters:{type:"object",properties:{symbols:{type:"array",items:{type:"string"},
    description:"标的代码,用看板写法:A股如 688256.SS / 001309.SZ,港股如 6869.HK,美股如 NVDA。最多8只。"}},required:["symbols"]}}}];
function tcode(s){
  if(/\\.SS$/.test(s))return "sh"+s.split(".")[0];
  if(/\\.SZ$/.test(s))return "sz"+s.split(".")[0];
  if(/\\.HK$/.test(s))return "hk"+s.split(".")[0].padStart(5,"0");
  return null;
}
async function toolQuote(symbols){
  const out={},codes=[],owners=[];
  (symbols||[]).slice(0,8).forEach(function(s){const c=tcode(s);if(c){codes.push(c);owners.push(s);}});
  if(codes.length){
    await new Promise(function(res){
      const sc=document.createElement("script");sc.charset="GBK";
      sc.src="https://qt.gtimg.cn/q="+codes.join(",")+"&_="+Date.now();
      sc.onload=res;sc.onerror=res;document.head.appendChild(sc);
    });
    codes.forEach(function(c,i){
      const v=window["v_"+c];
      if(v&&v.length>50){
        const f=v.split("~"),hk=c.indexOf("hk")===0;
        out[owners[i]]={名称:f[1],现价:f[3],昨收:f[4],今开:f[5],涨跌pct:f[32],今日最高:f[33],今日最低:f[34],
          总市值:(f[45]?(f[45]+(hk?"亿港元(约)":"亿元")):"未提供"),行情时间:f[30],来源:"腾讯实时行情"};
      }else out[owners[i]]={错误:"实时抓取失败,请以看板快照为准"};
    });
  }
  for(const s of (symbols||[]).slice(0,8)){
    if(tcode(s))continue;
    if(!FHK||FHK.indexOf("__FH_KEY")>=0){out[s]={错误:"美股实时凭证未配置,请以看板快照为准"};continue;}
    try{
      const q=await(await fetch("https://finnhub.io/api/v1/quote?symbol="+s+"&token="+FHK)).json();
      let mc=null;
      try{const p=await(await fetch("https://finnhub.io/api/v1/stock/profile2?symbol="+s+"&token="+FHK)).json();mc=p.marketCapitalization;}catch(e){}
      out[s]={现价:q.c,昨收:q.pc,今开:q.o,涨跌pct:q.dp,今日最高:q.h,今日最低:q.l,
        总市值:(mc?(Math.round(mc)+"百万美元"):"未提供"),来源:"Finnhub实时"};
    }catch(e){out[s]={错误:"实时抓取失败,请以看板快照为准"};}
  }
  return out;
}
function qel(i){return document.getElementById(i);}
function qaToggle(){const b=qel('qa-body');b.classList.toggle('hide');qel('qa-arrow').textContent=b.classList.contains('hide')?'▸':'▾';}
function qaBasisToggle(){qel('qa-basis-body').classList.toggle('hide');}
function qaFab(){
  const b=qel('qa-body');
  if(b.classList.contains('hide'))qaToggle();
  qel('qa-panel').scrollIntoView({behavior:'smooth',block:'start'});
  setTimeout(function(){qel('qa-in').focus();},450);
}
// 面板在视口内时收起悬浮球,避免重复入口
new IntersectionObserver(function(es){qel('qa-fab').style.display=es[0].isIntersecting?'none':'block';}).observe(qel('qa-panel'));
function qaEsc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function qaMd(s){
  let h=qaEsc(s).replace(/\\*\\*([^*]+)\\*\\*/g,'<b>$1</b>');
  return h.split('\\n').map(function(l){
    if(/^[-•] /.test(l))return '<div class="qa-li">• '+l.slice(2)+'</div>';
    if(/^#{1,4} /.test(l))return '<div class="qa-hd">'+l.replace(/^#{1,4} /,'')+'</div>';
    return l?('<div>'+l+'</div>'):'';
  }).join('');
}
async function tgNews(){
  if(TGCACHE!==null)return TGCACHE;
  try{
    const r=await fetch('tongguang/data/index.json');
    const j=await r.json();
    const arts=(j.articles||[]).slice().sort(function(a,b){return String(b.date).localeCompare(String(a.date));});
    const picked=[];
    for(const a of arts){
      if(picked.length>=24)break;
      if(a.is_top5||a.is_tier0||(a.quality_score||0)>=8)
        picked.push('['+a.date+'] '+a.title+(a.meaning?(' → 这意味着'+String(a.meaning)):''));
    }
    TGCACHE=picked.length?('同光企业AI早报要闻(AI行业前沿信号,最新在前,语料截至 '+(arts[0]?arts[0].date:'?')+'):\\n- '+picked.join('\\n- ')):'';
  }catch(e){TGCACHE='';}
  return TGCACHE;
}
function qaAsk(q){if(QABUSY)return;qel('qa-in').value=q;qaSend();}
function qaBubble(cls,html){
  const d=document.createElement('div');d.className='qa-m '+cls;d.innerHTML=html;
  qel('qa-log').appendChild(d);d.scrollIntoView({block:'nearest'});return d;
}
async function qaSend(){
  const q=qel('qa-in').value.trim();
  if(!q||QABUSY)return;
  if(!QK||QK.indexOf('__QA_KEY')>=0){qaBubble('qa-a','⚠️ 问答引擎未配置(本地预览版无凭证,线上 andy4576.com 输密码后可用)。');return;}
  QABUSY=true;qel('qa-send').disabled=true;qel('qa-in').value='';
  qaBubble('qa-u',qaEsc(q));
  const abox=qaBubble('qa-a','<span class="qa-wait">🤖 研判中…</span>');
  try{
    const tg=await tgNews();
    const sys='你是一名华尔街二级市场交易员+buy-side分析师,长期跟踪美股AI产业链与A股/港股算力链,现在回答看板主人的盘势问题。硬性纪律:\\n1) 你有一个 get_realtime_quote 工具能抓标的的实时行情/市值——凡用户问最新价格/市值/今天涨跌,或质疑看板数据、要求核实/扒最新数据时,【必须先调用工具】拿实时数再回答,并同时给出"实时(刚抓取,标注行情时间)"与"看板快照(asof日期)"两套数字、解释差异原因(如盘中涨跌)。\\n2) 其余信息只基于给到的【看板数据】(内含"全球头条"字段)与【同光早报要闻】;语料和工具都覆盖不到的直说"无法核实",绝不编造价格/日期/券商目标价。\\n3) 遇到"何时回转/何时企稳"类问题:未来无法预测——必须转化为【条件与信号】:关键价位(站回MA50/跌破MA200)、催化剂(财报日/头条宏观变量)、乐观/中性/悲观三情景时间量级,明说是情景推演不是预测。\\n4) 分析透镜(可用的推理方法,非事实):①宏观数据用"实际vs前值"对照并看边际变化(语境内含"宏观快线"字段:BLS非农/失业率/CPI、中美10Y利差、黄金原油实时、社融);②大事件按"事件本身→市场反应→政策意图"三层递进;③跨资产资金流视角(美元资产/黄金/加密的轮动);④要人表态(美联储主席/财长/央行)是高权重信号。\\n5) 结论先行、分点、简洁;引用数据注明出处与时点。\\n6) 末尾固定一句:仅研究示范,非投资建议。用中文回答。';
    const ctxblk='【看板数据(asof '+QACTX.asof+',为快照非实时;实时请调工具)】\\n'+JSON.stringify(QACTX)+(tg?('\\n\\n【'+tg+'】'):'\\n\\n(同光早报语料本次不可用)');
    const msgs=[{role:'system',content:sys}];
    QAHIST.slice(-3).forEach(function(h){msgs.push({role:'user',content:h.q});msgs.push({role:'assistant',content:h.a});});
    msgs.push({role:'user',content:ctxblk+'\\n\\n【问题】'+q});
    // ―― 第一轮:让引擎决定要不要抓实时数据(非流式,带工具) ――
    let liveNote='';
    const r1=await fetch('https://api.deepseek.com/v1/chat/completions',{method:'POST',
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+QK},
      body:JSON.stringify({model:'deepseek-chat',messages:msgs,tools:QATOOLS,temperature:0.3,max_tokens:1500})});
    if(!r1.ok){abox.innerHTML='❌ 引擎返回 '+r1.status+'(密钥失效或限流,稍后再试)';return;}
    const j1=await r1.json();
    const m1=j1.choices&&j1.choices[0]&&j1.choices[0].message;
    if(m1&&m1.tool_calls&&m1.tool_calls.length){
      msgs.push(m1);
      for(const tc of m1.tool_calls){
        let args={};try{args=JSON.parse(tc.function.arguments||'{}');}catch(e){}
        const syms=args.symbols||[];
        abox.innerHTML='<span class="qa-wait">🔧 正在实时抓取 '+syms.join('、')+' 行情…</span>';
        const res=await toolQuote(syms);
        liveNote=' · 实时行情✓('+syms.length+'只·刚抓取)';
        msgs.push({role:'tool',tool_call_id:tc.id,content:JSON.stringify(res)});
      }
      abox.innerHTML='<span class="qa-wait">🤖 已拿到实时数据,研判中…</span>';
    }else if(m1&&m1.content){
      // 引擎判断无需实时数据,第一轮已给出完整回答
      const ans1=m1.content;
      abox.innerHTML=qaMd(ans1)+'<div class="qa-src">📎 本次依据:看板研判('+QACTX.asof+'·19票+记分卡) · 同光要闻'+(tg?'✓':'✗')+' · 全球头条'+((QACTX['全球头条']&&QACTX['全球头条']['条目'])?'✓':'✗')+' · 未动用实时抓取</div>';
      QAHIST.push({q:q,a:ans1});if(QAHIST.length>6)QAHIST.shift();
      return;
    }
    // ―― 第二轮:携带实时数据流式作答 ――
    const resp=await fetch('https://api.deepseek.com/v1/chat/completions',{method:'POST',
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+QK},
      body:JSON.stringify({model:'deepseek-chat',messages:msgs,stream:true,temperature:0.3,max_tokens:1500})});
    if(!resp.ok){abox.innerHTML='❌ 引擎返回 '+resp.status+'(密钥失效或限流,稍后再试)';return;}
    const rd=resp.body.getReader(),dec=new TextDecoder();let buf='',ans='';
    while(true){
      const c=await rd.read();if(c.done)break;
      buf+=dec.decode(c.value,{stream:true});
      let i;
      while((i=buf.indexOf('\\n'))>=0){
        const line=buf.slice(0,i).trim();buf=buf.slice(i+1);
        if(line.indexOf('data:')!==0)continue;
        const dta=line.slice(5).trim();
        if(dta==='[DONE]')continue;
        try{
          const j=JSON.parse(dta);
          const t=j.choices&&j.choices[0]&&j.choices[0].delta&&j.choices[0].delta.content;
          if(t){ans+=t;abox.innerHTML=qaMd(ans);}
        }catch(e){}
      }
    }
    if(!ans){abox.innerHTML='❌ 未收到回答,请重试';}
    else{
      QAHIST.push({q:q,a:ans});if(QAHIST.length>6)QAHIST.shift();
      const nw=QACTX['全球头条'];
      abox.innerHTML+='<div class="qa-src">📎 本次依据:看板研判('+QACTX.asof+'·19票+记分卡) · 同光要闻'+(tg?'✓':'✗不可用')+' · 全球头条'+(nw&&nw['条目']&&nw['条目'].length?('✓('+nw.date+'·'+nw['条目'].length+'条)'):'✗暂无')+liveNote+'</div>';
      abox.scrollIntoView({block:'nearest'});
    }
  }catch(e){abox.innerHTML='❌ 网络出错:'+qaEsc(String(e));}
  finally{QABUSY=false;qel('qa-send').disabled=false;}
}
qel('qa-in').addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();qaSend();}});
</script>"""


def qa_block(data, calls, calls_date, v):
    import json as _json
    ctx = qa_ctx(data, calls, calls_date, v)
    # '</' 必须转义:th/rk 是逐日再生成的模型文本,一旦哪天出现字面量 '</script' 会提前终止内联脚本、
    # 研判数据裸露成乱码且 CI 拦不住(审查发现的潜在碎页风险,JSON 语义不变)
    payload = _json.dumps(ctx, ensure_ascii=False).replace("</", "<\\/")
    return QA_TMPL.replace("@QACTX@", payload)


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
    # 页脚引擎声明按当期实况动态生成(体检:此前写死"未用DeepSeek"与大盘区"DeepSeek引擎研判"同页互斥)
    engine_line = ("本期研判引擎:DeepSeek(云端自动/按钮触发)" if "DeepSeek" in (calls.get("market") or "")
                   else "本期研判引擎:Claude(亲研)")
    bench_m3 = (data.get("QQQ", {}) or {}).get("m3")     # 相对强弱基准:QQQ 近3月
    # 按市场分组排版:美股(全球定价、引领)在前 → A 股 → 港股,因 A/港大多跟随美股,分组后看 A/港更直观。
    # 奖牌(🥇🥈🥉/序号)用【全局排名】位置,组内仍按总排名顺序。
    MKT = [("US", "🇺🇸 美股核心 · AI 产业链驱动(全球定价,引领 A 股 / 港股)"),
           ("CN", "🇨🇳 A 股 · 跟随美股的国产算力 / AI 链"),
           ("HK", "🇭🇰 港股 · 国产 AI")]
    mkt_of = lambda tk: (data.get(tk, {}) or {}).get("market", "US")
    TAB_LABEL = {"US": "🇺🇸 美股", "CN": "🇨🇳 A 股", "HK": "🇭🇰 港股"}
    panes = ""
    tabbtns = '<button class="tab active" data-tab="all">📊 全部</button>'
    for mk, title in MKT:
        grp = [tk for tk in order if tk in calls["stocks"] and mkt_of(tk) == mk]
        if not grp:
            continue
        tabbtns += f'<button class="tab" data-tab="{mk}">{TAB_LABEL[mk]}<span class="tc">{len(grp)}</span></button>'
        panes += f'<div class="pane" data-mkt="{mk}"><div class="section">{title}<span class="scnt">{len(grp)} 支</span></div><div class="grid">'
        panes += "".join(card(order.index(tk), tk, data.get(tk, {}), calls["stocks"][tk], bench_m3) for tk in grp)
        panes += '</div></div>'
    cards = f'<div class="tabs">{tabbtns}</div>{panes}'
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
.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 16px;position:sticky;top:0;z-index:20;background:#0b1120;padding:10px 0}}
.tab{{font-size:14.5px;font-weight:800;color:#94a3b8;background:#111a2e;border:1px solid #334155;border-radius:11px;padding:9px 18px;cursor:pointer;transition:all .12s;font-family:inherit}}
.tab:hover{{color:#cbd5e1;border-color:#475569}}
.tab.active{{color:#fff;background:linear-gradient(135deg,#2563eb,#1d4ed8);border-color:#2563eb;box-shadow:0 2px 10px rgba(37,99,235,.35)}}
.tab .tc{{font-size:11px;background:rgba(255,255,255,.22);border-radius:8px;padding:1px 7px;margin-left:6px}}
.pane.hide{{display:none}}
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
.qa{{background:linear-gradient(135deg,rgba(200,165,98,.12),rgba(37,99,235,.06)),#101b33;border:1px solid rgba(200,165,98,.5);border-radius:14px;margin-bottom:16px;overflow:hidden;box-shadow:0 0 22px rgba(200,165,98,.10)}}
.qa-h{{display:flex;align-items:center;gap:10px;font-size:16.5px;font-weight:900;color:#efe0bd;padding:14px 18px;cursor:pointer;user-select:none}}
.qa-h:hover{{background:rgba(200,165,98,.08)}}
.qa-ico{{font-size:20px}}
.qa-new{{font-size:10px;font-weight:800;letter-spacing:1px;color:#0b1120;background:linear-gradient(120deg,#e5c987,#c8a562);border-radius:8px;padding:2px 8px}}
.qa-sub{{font-size:11px;font-weight:400;color:#9c8f72}}
#qa-fab{{position:fixed;right:22px;bottom:22px;z-index:60;display:none;border:none;cursor:pointer;font-family:inherit;
 font-size:14px;font-weight:800;color:#0b1120;background:linear-gradient(120deg,#e5c987,#c8a562);
 border-radius:999px;padding:13px 22px;box-shadow:0 6px 24px rgba(200,165,98,.45)}}
#qa-fab:hover{{transform:translateY(-2px);box-shadow:0 10px 30px rgba(200,165,98,.55)}}
.qa-body{{padding:0 18px 14px}}
.qa-body.hide{{display:none}}
.qa-chips{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}}
.chip{{font-size:12px;color:#93c5fd;background:rgba(96,165,250,.1);border:1px solid rgba(96,165,250,.3);border-radius:16px;padding:5px 12px;cursor:pointer;font-family:inherit}}
.chip:hover{{background:rgba(96,165,250,.2)}}
.qa-log{{display:flex;flex-direction:column;gap:8px;max-height:420px;overflow-y:auto;margin-bottom:10px}}
.qa-m{{font-size:13px;line-height:1.7;border-radius:12px;padding:9px 13px;max-width:88%}}
.qa-u{{align-self:flex-end;background:rgba(37,99,235,.25);color:#dbeafe;border:1px solid rgba(96,165,250,.3)}}
.qa-a{{align-self:flex-start;background:rgba(51,65,85,.35);color:#e2e8f0;border:1px solid #334155}}
.qa-li{{padding-left:6px}}
.qa-hd{{font-weight:800;color:#93c5fd;margin-top:4px}}
.qa-wait{{color:#94a3b8;font-size:12px}}
.qa-inrow{{display:flex;gap:8px;align-items:flex-end}}
.qa-inrow textarea{{flex:1;background:#111a2e;border:1px solid #334155;border-radius:10px;color:#e2e8f0;font-size:13px;font-family:inherit;padding:9px 12px;resize:vertical;line-height:1.5}}
.qa-inrow textarea:focus{{outline:none;border-color:#2563eb}}
#qa-send{{background:#2563eb;color:#fff;border:none;border-radius:10px;padding:9px 18px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit}}
#qa-send:disabled{{opacity:.5;cursor:default}}
.qa-foot{{font-size:10.5px;color:#64748b;margin-top:8px;line-height:1.6}}
.qa-basis{{font-size:11.5px;color:#93c5fd;cursor:pointer;margin-bottom:8px;user-select:none}}
.qa-basis:hover{{text-decoration:underline}}
.qa-basis-body{{font-size:11.5px;color:#94a3b8;background:rgba(51,65,85,.25);border:1px solid #334155;border-radius:10px;padding:10px 13px;margin-bottom:10px;line-height:1.8}}
.qa-basis-body.hide{{display:none}}
.qa-src{{font-size:10.5px;color:#64748b;border-top:1px dashed rgba(100,116,139,.4);margin-top:8px;padding-top:6px}}
</style></head><body><div class="wrap">
<div class="header"><div style="font-family:Georgia,serif;font-size:12px;letter-spacing:4px;color:#c8a562;margin-bottom:8px">LUMORA · 同光科技</div><h1>📡 {cfg['title']} · {TODAY}</h1>
<div class="sub">美股 AI 核心 {sum(1 for s in cfg['stocks'] if s.get('market') != 'CN' and s['ticker'] != cfg['benchmark'])} 票 + 🇨🇳 A 股补充 {sum(1 for s in cfg['stocks'] if s.get('market') == 'CN')} 票 + {cfg['benchmark']} 基准 · 长期 {cfg['horizon_label']} 视角 · 数据 yfinance+akshare(真实行情) · AI 研判</div>
<div class="updated">🕐 本页生成:<b>{BUILD_TS}</b> 北京 · <a href="news.html">🌍 全球头条</a> · <a href="ops.html">📊 运营看板</a> · <a href="javascript:void(0)" onclick="location.href='board.html?t='+Date.now()">🔄 手动刷新</a> · <button id="updbtn" onclick="triggerUpd()" style="background:#2563eb;color:#fff;border:none;border-radius:8px;padding:5px 13px;font-size:12px;font-weight:700;cursor:pointer">🔁 更新研判</button><span id="updmsg" style="color:#94a3b8;font-size:12px;margin-left:6px"></span></div>
<script>
const DT="__DISPATCH_TOKEN__";
async function triggerUpd(){{
  const m=document.getElementById('updmsg'),btn=document.getElementById('updbtn');
  if(!DT||DT.indexOf('__DISPATCH')>=0){{m.textContent='更新触发未配置';return;}}
  btn.disabled=true;btn.style.opacity=.5;m.textContent='触发中…';
  try{{
    const r=await fetch('https://api.github.com/repos/xiaomin4576-ui/meigu-ai-stock-board/actions/workflows/daily-board.yml/dispatches',{{method:'POST',headers:{{'Authorization':'Bearer '+DT,'Accept':'application/vnd.github+json'}},body:JSON.stringify({{ref:'main'}})}});
    if(r.status!==204){{m.textContent='❌ 触发失败('+r.status+')';btn.disabled=false;btn.style.opacity=1;return;}}
    m.textContent='✅ 已触发,云端构建中(一般5-15分钟,请勿重复点击)…';
    const t0=Date.now();
    // 用同一凭证轮询构建状态:完成后给"点此加载最新"(自带绕缓存),别再让用户瞎猜好没好
    const timer=setInterval(async function(){{
      try{{
        const rr=await fetch('https://api.github.com/repos/xiaomin4576-ui/meigu-ai-stock-board/actions/runs?event=workflow_dispatch&per_page=1',{{headers:{{'Authorization':'Bearer '+DT,'Accept':'application/vnd.github+json'}}}});
        const j=await rr.json();const run=j.workflow_runs&&j.workflow_runs[0];
        const mins=Math.max(1,Math.round((Date.now()-t0)/60000));
        if(run&&run.status==='completed'&&new Date(run.created_at).getTime()>t0-120000){{
          clearInterval(timer);btn.disabled=false;btn.style.opacity=1;
          if(run.conclusion==='success'){{m.innerHTML='🎉 新研判已上线!<a href="javascript:void(0)" onclick="location.href=\\'board.html?t=\\'+Date.now()" style="color:#4ade80;font-weight:800">点此加载最新看板</a>';}}
          else{{m.textContent='⚠️ 云端构建结束('+run.conclusion+'),稍等片刻再点一次';}}
        }}else{{m.textContent='⏳ 云端构建中… 已等 '+mins+' 分钟(一般5-15分钟,完成会在这里提示)';}}
      }}catch(e){{}}
    }},20000);
  }}catch(e){{m.textContent='❌ 网络出错';btn.disabled=false;btn.style.opacity=1;}}
}}
document.addEventListener('click',function(e){{
  var b=e.target.closest('.tab'); if(!b)return;
  document.querySelectorAll('.tab').forEach(function(x){{x.classList.remove('active');}});
  b.classList.add('active');
  var t=b.dataset.tab;
  document.querySelectorAll('.pane').forEach(function(p){{p.classList.toggle('hide', t!=='all' && p.dataset.mkt!==t);}});
}});
</script>
<div class="market">🌎 <b style="color:#60a5fa">大盘与板块:</b>{calls.get('market','')}</div>
<div class="rankbar">🏆 <b>买点吸引力排序:</b>{rank_str}</div></div>
{freshness_banner(calls_date, data_meta)}
{qa_block(data, calls, calls_date, v)}
{evidence_section(data)}
{review_section(v)}
{cards}
{audit_section(data)}
<div class="foot">两个核心指标 = ① 买入建议+建议买入价　② 6-12月目标价+预期收益　·　预测台账自动复盘校准<br>
数据 yfinance+akshare+腾讯行情(真实抓取) · {engine_line}<br>
⚠️ 仅供研究/学习,<b>非投资建议</b>。回测命中率约 42%(<b>非 90%</b>),正期望靠 ~2.5:1 盈亏比——<b>赚钱靠风控不靠高胜率</b>;目标价为技术面+共识+催化剂推演,不代表未来,实际交易请自负风险。</div>
</div></body></html>"""
    os.makedirs(STATE, exist_ok=True)
    out = os.path.join(STATE, f"ai_stock_board_{TODAY}.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out)


if __name__ == "__main__":
    main()
