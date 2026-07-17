#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""云端研判引擎(DeepSeek):读 state/data_<date>.json → 对每只按策略框架研判 → 写 state/calls_<date>.json。
引擎=DeepSeek(用户选定;非 Claude)。env 需 DEEPSEEK_API_KEY(可选 DEEPSEEK_BASE_URL,默认 https://api.deepseek.com/v1)。
仅在"手动点更新/工作流 dispatch"时跑,不做定时自动。严守诚实底线:禁幽灵共识、买入 R:R≥2、目标不画饼。"""
import os, sys, json, glob, re, datetime
from concurrent.futures import ThreadPoolExecutor
import requests

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
KEY = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
BASE = (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()

FRAME = """你是华尔街二级市场交易员+buy-side分析师,为「美股AI科技股早报」看板做这一只标的的【长期6-12个月】研判。
两个核心交付:①买入建议=买入/观望/回避+建议买入价(区间) ②6-12月目标价(区间)+预期收益%(买入中值→目标中值)。
【策略框架】1)趋势:价vs MA20/MA50/MA200;2)动量:近1/3/6月,过热/抛物线/远离均线→降"观望"不追,但已明显回调(距高-15%以上或近1月负)接近支撑则可转积极;3)买点=回踩【现价下方最近的有效结构支撑】(锚均线/前期平台,绝不用"现价减X%"定义,否则价涨买区跟涨=追涨):按现价相对均线位置择锚——价>MA20→锚MA20一线(强势浅回调,最易触及);MA50<价≤MA20(已跌破短均)→锚MA50一线;价≤MA50(破位)→锚MA200或前低深回调。【硬约束:买区上沿必须≤现价】,高于现价=追涨违规。自检:把现价换成任意值,买区若移动=追涨违规;4)R:R纪律:给"买入"须R:R≥2=(目标中值-买入中值)/(买入中值×档位止损%),档位止损=强势档跌破MA20约-6%、破位档-10%;并须算【从现价看真实收益】=(目标中值-现价)/现价,若≤+8%=伪信号(只赚回假设回撤)不给买入;5)共识校准:美股Finnhub评级(rating_mean 1强买~5强卖、买入占比)+前瞻PE/ROE,A股东财评级+EPS预测+前瞻PE;6)催化剂:earnings_date(<14天→⚠️财报临近二元风险不追高)、利空新闻(跌停/减持/风险提示)必须纳入;7)估值:PEG=PE÷EPS增速,高PEG(>8)透支→压制评级。
【诚实底线·写死】①禁幽灵共识:target_mean为null时th绝不编造"券商一致$X/X家";美股只说"Finnhub评级X/买入占比X%",A股说"东财评级X"。②买区可达+锚结构:买入中值不低于现价×0.82(最深-18%,除非已实打实破MA50且有支撑);买上沿距现价折让强势档≤10%/温和≤15%/破位≤25%;价在MA50上方却把买区砸到MA50下方=非法深锚,禁止(封纳芯微式脱锚)。③目标须【相对现价】成立(不只对买入中值):目标下沿必须>现价且≥买入上沿、目标中值≥现价×1.15;若最乐观目标仍≤现价×1.05→无中期上行论据,sig至少降观望、buy与tgt给"—"、th注明"目标不高于现价、无上行空间";目标隐含涨幅≤+60%不画饼。④可交易票禁留空+【观望≠留空】:凡price与MA50非空且非stale,无论"买入"还是"观望"都必须给出 buy(等回踩现价下方最近支撑)+tgt(回补前高hi/压力位,通常在现价上方故有空间),th标"技术面目标·无券商一致";"观望"意为"等回踩到买区再介入",不是"没观点/不给数字"。仅当(a)前高hi≤现价×1.05[已在高位真无上行空间] 或 (b)可算评分因子≤3[数据不足] 才可给"—"并在th注明原因。同板块同形态标的须同规则,不许一只给买点另一只留空(封东山式漏判)。⑤反过拟合护栏:单日/单半日走势只作参考、不改研判激进度——不因某日板块回调就把观望批量改回避或加做空;过热惩罚强度维持不变(板块beta与个股过热单日无法解耦,别把板块普跌误记为过热因子有效),调参须≥5期复盘。⑥绝不承诺收益,命中率现实50-65%。
只输出JSON对象:{"sig":"买入/观望/回避","conf":1-10整数,"buy":"区间如188-196","tgt":"区间如240-270","ret":"如+33%","th":"买入逻辑50-95字,引用催化剂/对标共识/给买点理由","rk":"主要风险50-95字"}。th/rk用简体中文。"""

_USAGE = []  # 各线程调用的 token 用量(GIL 下 append 安全),main 末尾汇总落账供运营看板统计

def ds_call(prompt, retries=3):
    for i in range(retries):
        try:
            r = requests.post(BASE + "/chat/completions",
                headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                      "response_format": {"type": "json_object"}, "temperature": 0.4, "max_tokens": 700},
                timeout=60)
            if r.status_code != 200:
                # 审计F10:失败路径必须留痕(不打印key)——静默吞错曾让事故藏了三天(数据完整性规则12)
                print(f"  ds_call 尝试{i+1}: HTTP {r.status_code} {r.text[:120]}")
                continue
            j = r.json()
            _USAGE.append(j.get("usage") or {})   # 拿到响应即计费:截断/解析失败也真实消耗了 token,先落账
            fin = (j.get("choices") or [{}])[0].get("finish_reason")
            if fin == "length":
                print(f"  ds_call 尝试{i+1}: 输出被截断(finish_reason=length)")
                continue
            return json.loads(j["choices"][0]["message"]["content"])
        except Exception as e:
            print(f"  ds_call 尝试{i+1}: 异常 {repr(e)[:120]}")
    return None

def clean_range(s):
    s = re.sub(r"[\$¥]|HK\$", "", str(s)); s = re.sub(r"[（(].*", "", s).strip()
    return s.replace("-", "–").replace("—", "–")
def clean_ret(s):
    # 审计F17:正则必须吃小数百分比——旧 r"[+\-]?\d+%" 对 "+20.6%" 只截到 "6%"、"-7.5%" 丢成 "5%"(连符号一起丢),
    # 系统性污染旗舰指标"预期收益"(DeepSeek 常输出小数收益)。补 (?:\.\d+)? 捕获小数部分。
    m = re.search(r"[+\-]?\d+(?:\.\d+)?%", str(s)); return m.group(0) if m else str(s)

def _nums(s):
    return re.findall(r"\d+(?:\.\d+)?", str(s or ""))
def _mid(s):
    n = _nums(s); return (float(n[0]) + float(n[-1])) / 2 if n else None
def _top(s):
    n = _nums(s); return float(n[-1]) if n else None
def _bot(s):
    n = _nums(s); return float(n[0]) if n else None

def validate_call(tk, c, s):
    """确定性护栏(体检确诊:FRAME 六规则靠单次LLM自觉,违规率26%)——落账前核不变量,
    违规则【安全降级】为观望+留空+注明(不冒险自动改数字),堵'买在现价上方/目标≤现价/
    风险补偿不足'这类低级错直穿台账。返回(修正后call, 违规原因或None)。"""
    px = s.get("price")
    if not px or c.get("sig") not in ("买入", "观望"):
        return c, None
    if c.get("buy") in (None, "—", "无", "-", "–"):
        return c, None
    bt, tl, tm = _top(c.get("buy")), _bot(c.get("tgt")), _mid(c.get("tgt"))
    viol = None
    if bt and bt / px - 1 > 0.005:
        viol = "买区上沿高于现价(追涨)"
    elif tl and tl <= px:
        viol = "目标下沿≤现价(无上行空间)"
    elif tm and tm < px * 1.10:
        viol = "目标中值不足现价+10%(风险补偿不够)"
    if viol:
        c = dict(c)
        c.update({"sig": "观望", "buy": "—", "tgt": "—", "ret": "—",
                  "th": f"[护栏降级·{viol}] " + str(c.get("th", ""))[:70]})
    return c, viol

def judge_one(tk, s, bench, macro_line="", hint="", score=None):
    if tk == "QQQ":
        return tk, {"sig": "观望", "conf": 5, "buy": "—", "tgt": "—", "ret": "—",
                    "th": "纳指100 ETF·大盘基准,反映美股科技整体风险偏好,是成分股研判的顺势背景。",
                    "rk": "系统性风险锚,非个股买卖标的;大盘转弱则全组目标下修。"}
    a = s.get("analyst", {}) or {}; q = s.get("quality", {}) or {}
    cur = "$" if s.get("market", "US") == "US" else ("HK$" if s.get("market") == "HK" else "¥")
    cons = (f"Finnhub评级{a.get('rating_mean')}(1强买~5强卖)/买入占比{a.get('rec_buy_ratio')}"
            if a.get("consensus_src") == "Finnhub" else (f"东财评级{a.get('cn_rating')}" if a.get("cn_rating") else "无共识"))
    data = (f"{s.get('name')} {tk} | {s.get('role')} | 市场{s.get('market','US')} | 币种{cur}\n"
            f"现价{s.get('price')} 近1/3/6月{s.get('m1')}/{s.get('m3')}/{s.get('m6')}% 距52周高{s.get('fromhi')}% 52周{s.get('lo')}–{s.get('hi')}\n"
            f"MA20 {s.get('ma20')}/MA50 {s.get('ma50')}/MA200 {s.get('ma200')} 年化波动{s.get('vol')}% 9因子评分{score if score is not None else s.get('score','?')}(第二意见,与你研判冲突时须解释)\n"
            f"共识:{cons} target_mean={a.get('target_mean')}\n"
            f"前瞻PE {a.get('fwd_pe')} EPS增速{a.get('eps_growth')}% EPS26/27 {a.get('eps_2026')}/{a.get('eps_2027')} ROE {q.get('roe')} 经营现金流/股{q.get('ocf_ps')}\n"
            f"财报日{s.get('earnings_date')} 解禁{json.dumps(s.get('unlock'),ensure_ascii=False)} QQQ近3月{bench}% "
            f"新闻{json.dumps([n.get('title','')[:34] for n in (s.get('news') or [])[:2]],ensure_ascii=False)} "
            f"{'⚠️数据复用历史(非当日),保守' if s.get('stale') else '当日真值'}")
    v = ds_call(f"{FRAME}{macro_line}{hint}\n\n【真实数据({TODAY})】\n{data}")
    if not v or not v.get("sig"):
        return tk, {"sig": "观望", "conf": 3, "buy": "—", "tgt": "—", "ret": "—",
                    "th": "本期研判引擎未返回有效结果,暂按观望;数据见卡片行情/评分。", "rk": "研判缺失,请刷新重试或人工复核。"}
    return tk, {"sig": v.get("sig", "观望"), "conf": int(v.get("conf", 5) or 5),
                "buy": clean_range(v.get("buy", "—")), "tgt": clean_range(v.get("tgt", "—")),
                "ret": clean_ret(v.get("ret", "—")), "th": v.get("th", ""), "rk": v.get("rk", "")}

def main():
    if not KEY:
        print("❌ 未配 DEEPSEEK_API_KEY,跳过研判(保留现有 calls)"); return
    f = sorted(glob.glob(os.path.join(STATE, "data_2026-*.json")))[-1]
    data = json.load(open(f, encoding="utf-8")); stocks = data["stocks"]; asof = data.get("asof", TODAY)
    bench = (stocks.get("QQQ", {}) or {}).get("m3")
    # 宏观环境注入(2026-07 补齐的研判维度;曾被CI回写的-s ours回滚过一次,已根治重上):
    # BLS非农/失业率/CPI(实际vs前值)+中美利差+黄金原油——成长股估值对利率/通胀极敏感,
    # 此前引擎对宏观全盲,回调期易把"利率驱动的体制转换"误读成"健康回踩"。不改9因子数学。
    macro_line = ""
    mfiles = [x for x in sorted(glob.glob(os.path.join(STATE, "macro_*.json")))
              if re.search(r"macro_\d{4}-\d{2}-\d{2}\.json$", x)]
    if mfiles:
        try:
            mj = json.load(open(mfiles[-1], encoding="utf-8"))
            macro_line = ("\n【宏观环境(真实数据,研判时纳入:通胀/利率方向影响成长股估值,数据用'实际vs前值'看边际)】"
                          + json.dumps(mj.get("blocks", {}), ensure_ascii=False)[:900])
        except Exception:
            pass
    # 校准闭环接通(体检确诊命脉:此前 verification.json 算了却没人读、"越用越准"空转):
    # ①9因子评分作"第二意见"喂进研判 ②读上期复盘→全局校准纪律+逐票"买区挂不上/方向做反"提示注入。
    calib_line, hint_map, score_map = "", {}, {}
    try:
        from build_board import factor_score
        for tk, s in stocks.items():
            if tk == "QQQ":
                continue
            try:
                score_map[tk] = factor_score(s, bench)[0]
            except Exception:
                pass
    except Exception:
        pass
    try:
        vj = json.load(open(os.path.join(STATE, "verification.json"), encoding="utf-8"))
        if vj.get("calibration"):
            calib_line = "\n【全局校准纪律(上期复盘,据此微调别重犯)】" + vj["calibration"]
        feas = vj.get("feasibility", {})
        latest_rev = {}
        for x in vj.get("review", []):
            latest_rev[x["ticker"]] = x          # review 累积,末次覆盖=最近一期
        for tk in stocks:
            parts = []
            fz = feas.get(tk)
            if fz and fz.get("buy_reachable") is False:
                parts.append(f"上期买区挂不上({str(fz.get('note',''))[:40]})→本期按现价重锚更近结构支撑、收窄折让")
            rv = latest_rev.get(tk)
            if rv:
                if rv.get("signal") == "买入" and rv.get("entry_hit") is False:
                    parts.append("上期'买入'但买区未触及(没入场)→买区偏深,收窄")
                if rv.get("direction_ok") is False:
                    parts.append("上期方向做反→复核趋势别硬扛")
            if parts:
                hint_map[tk] = "\n【本票上期复盘·据此纠偏】" + " ; ".join(parts)
    except Exception:
        pass
    print(f"DeepSeek 研判 {len(stocks)} 只(asof {asof}{',含宏观' if macro_line else ''}{',接校准闭环' if calib_line else ''})…")
    items = list(stocks.items())
    calls = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for tk, c in ex.map(lambda kv: judge_one(kv[0], kv[1], bench, macro_line + calib_line,
                                                  hint_map.get(kv[0], ""), score_map.get(kv[0])), items):
            calls[tk] = c
    # 确定性护栏:落账前核 FRAME 不变量,违规安全降级(体检:此前违规率26%直穿台账)
    n_viol = 0
    for tk in list(calls):
        if tk == "QQQ":
            continue
        calls[tk], viol = validate_call(tk, calls[tk], stocks.get(tk, {}))
        if viol:
            n_viol += 1
    if n_viol:
        print(f"🛡 护栏拦截并降级 {n_viol} 条违规研判(买在现价上方/目标≤现价类)")
    # 排序:买入>观望>回避,组内 conf 降序再评分降序;QQQ 插买入组后
    SR = {"买入": 0, "观望": 1, "回避": 2}
    # 审计修复:原 tiebreak 读 stocks['score'] —— data json 无此字段,恒取默认 0,"评分降序"是死代码(评分从不影响排序)。
    # 改用上文已算好的 score_map(9 因子总分),让评分真正参与同信号同置信度时的排序。
    sc = lambda tk: score_map.get(tk, 0) or 0
    order = sorted([t for t in calls if t != "QQQ"], key=lambda t: (SR.get(calls[t]["sig"], 1), -calls[t]["conf"], -sc(t)))
    ins = sum(1 for t in order if calls[t]["sig"] == "买入")
    order.insert(ins, "QQQ")
    nbuy = sum(1 for t in calls if calls[t]["sig"] == "买入")
    nwatch = sum(1 for t in calls if calls[t]["sig"] == "观望")
    navoid = sum(1 for t in calls if calls[t]["sig"] == "回避")
    market = (f"<b>DeepSeek 引擎研判({asof})。</b>本期 买入{nbuy} / 观望{nwatch} / 回避{navoid}。"
              "买入=回调到位且 R:R≥2 的纪律买点;观望=趋势好但位置/估值偏高,等回踩 MA50;回避=抛物线顶+估值透支。"
              "研判对标 Finnhub/东财评级,禁幽灵共识,利空新闻已纳入。仅研究示范,非投资建议。")
    out = {"asof": asof, "market": market, "ranking": order, "stocks": calls}
    json.dump(out, open(os.path.join(STATE, f"calls_{asof}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 写 calls_{asof}.json | 买入{nbuy}/观望{nwatch}/回避{navoid}")
    # token 用量汇总落账(一期一条,供运营看板统计 DeepSeek 消耗)
    if _USAGE:
        rec = {"ts": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"),
               "engine": "deepseek-chat", "purpose": "research", "calls": len(_USAGE),
               "prompt_tokens": sum(u.get("prompt_tokens") or 0 for u in _USAGE),
               "completion_tokens": sum(u.get("completion_tokens") or 0 for u in _USAGE),
               "total_tokens": sum(u.get("total_tokens") or 0 for u in _USAGE)}
        with open(os.path.join(STATE, "usage.jsonl"), "a", encoding="utf-8") as fu:
            fu.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"📒 usage 落账:{rec['total_tokens']:,} tokens / {rec['calls']} 次调用")

if __name__ == "__main__":
    main()
