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
【策略框架】1)趋势:价vs MA50/MA200;2)动量:近1/3/6月,过热/抛物线/远离均线→降"观望"不追,但已明显回调(距高-15%以上或近1月负)接近MA50则可转积极;3)均值回归:买点优先"回踩支撑MA50一线";4)R:R纪律:给"买入"必须风险收益比≥2=(目标中值-买入中值)/(买入中值×0.1),否则降"观望";5)共识校准:美股有Finnhub评级(rating_mean 1强买~5强卖、买入占比)+前瞻PE/ROE,A股有东财评级+EPS预测+前瞻PE,对标这些;6)催化剂:earnings_date(<14天→⚠️财报临近二元风险不追高)、利空新闻(跌停/减持/风险提示)必须纳入;7)估值:PEG=PE÷EPS增速,高PEG(>8)透支→压制评级。
【诚实底线·写死】①禁幽灵共识:target_mean为null时th绝不编造"券商一致$X/X家";美股只说"Finnhub评级买入/买入占比X%",A股说"东财评级X"。②buy必须落在可达区间(现价-8%~-25%或MA50一线,不脱离盘面)。③目标隐含涨幅(自买入中值)一般≤+60%,除非基本面极强,不画饼。④绝不承诺收益,命中率现实50-65%。
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
            if r.status_code == 200:
                j = r.json()
                _USAGE.append(j.get("usage") or {})
                return json.loads(j["choices"][0]["message"]["content"])
        except Exception:
            pass
    return None

def clean_range(s):
    s = re.sub(r"[\$¥]|HK\$", "", str(s)); s = re.sub(r"[（(].*", "", s).strip()
    return s.replace("-", "–").replace("—", "–")
def clean_ret(s):
    m = re.search(r"[+\-]?\d+%", str(s)); return m.group(0) if m else str(s)

def judge_one(tk, s, bench, macro_line=""):
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
            f"MA50 {s.get('ma50')}/MA200 {s.get('ma200')} 年化波动{s.get('vol')}% 9因子评分{s.get('score','?')}\n"
            f"共识:{cons} target_mean={a.get('target_mean')}\n"
            f"前瞻PE {a.get('fwd_pe')} EPS增速{a.get('eps_growth')}% EPS26/27 {a.get('eps_2026')}/{a.get('eps_2027')} ROE {q.get('roe')} 经营现金流/股{q.get('ocf_ps')}\n"
            f"财报日{s.get('earnings_date')} 解禁{json.dumps(s.get('unlock'),ensure_ascii=False)} QQQ近3月{bench}% "
            f"新闻{json.dumps([n.get('title','')[:34] for n in (s.get('news') or [])[:2]],ensure_ascii=False)} "
            f"{'⚠️数据复用历史(非当日),保守' if s.get('stale') else '当日真值'}")
    v = ds_call(f"{FRAME}{macro_line}\n\n【真实数据({TODAY})】\n{data}")
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
    print(f"DeepSeek 研判 {len(stocks)} 只(asof {asof}{',含宏观环境' if macro_line else ''})…")
    items = list(stocks.items())
    calls = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for tk, c in ex.map(lambda kv: judge_one(kv[0], kv[1], bench, macro_line), items):
            calls[tk] = c
    # 排序:买入>观望>回避,组内 conf 降序再评分降序;QQQ 插买入组后
    SR = {"买入": 0, "观望": 1, "回避": 2}
    sc = lambda tk: stocks.get(tk, {}).get("score", 0) or 0
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
