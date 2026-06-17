#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 云端研判引擎(全自动):读 state/data_<date>.json(真实行情)+ verification.json(复盘校准),
按【策略框架】调 LLM(Anthropic Messages API 兼容)生成当期研判,写 state/calls_<date>.json。

为什么需要它:claude.ai Routine 打不开、本地 headless claude 在本环境 401,
故把"研判"这步放到 GitHub Actions 云端,用一把稳定 API 密钥直接调模型——实现每日全自动。

引擎 = 由 secret 配置的模型:
  - RESEARCH_API_KEY      Anthropic API key(走 x-api-key,正牌 Claude:RESEARCH_MODEL 填 claude-*)
  - RESEARCH_AUTH_TOKEN   Bearer 令牌(中转/relay 用;引擎=该 relay 实际服务的模型)
  - RESEARCH_BASE_URL     默认 https://api.anthropic.com
  - RESEARCH_MODEL        默认 claude-sonnet-4-5(正牌 Claude);relay 按其支持的模型名填

诚实底线:价格全部来自 data 文件真实抓取,prompt 硬性锚定、绝不许编造;
失败(无密钥/调用错/解析错/校验不过)一律【不覆盖】已有 calls,exit 0,
由 build_board 的 latest_calls() 复用最近一期 + 顶部橙色"研判 N 天前"如实标注。"""
import json, os, re, time, datetime
import requests

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()  # 北京时间

# 注:GitHub secret 未配置时会以空串传入(而非缺失),故用 `or 默认值` 兜底,空串也回落默认
API_KEY = (os.environ.get("RESEARCH_API_KEY") or "").strip()
AUTH_TOKEN = (os.environ.get("RESEARCH_AUTH_TOKEN") or "").strip()
BASE_URL = ((os.environ.get("RESEARCH_BASE_URL") or "https://api.anthropic.com").strip().rstrip("/"))
MODEL = (os.environ.get("RESEARCH_MODEL") or "claude-sonnet-4-6").strip()

SYSTEM = """你是华尔街二级市场交易员 + buy-side 分析师,做美股 AI 产业链长期(6-12 个月)研判。
严格依据下面的【策略框架】,对给定的 11 支标的各给:① 买入建议(买入/观望/回避)+ 建议买入价区间 ② 6-12 月目标价区间 + 预期收益%。

【策略框架】
1. 趋势跟踪:价相对 MA50/MA200(全在 200 日线上=趋势完好)。
2. 动量:近 1/3/6 月涨幅;过热(抛物线、远离均线)降级观望,不追高。
3. 均值回归/回调买入:买点优先"回踩支撑"而非追高。
4. 板块相对强弱:组内谁回调更到位/性价比更好,排前(ranking)。
5. 机构共识校准(关键):目标价对标数据里的 analyst.target_mean。我的目标显著高于共识(>10%)须在 th 标注"偏乐观";显著低于(<-10%)则说明保守理由;★若 analyst.target_mean 已 ≤ 现价(街上无上行空间),该股一律降级"观望"。
6. 催化剂锚定:th 必须引用数据里【当前】的催化剂(earnings_date、news 标题),不靠旧知识。
7. 风险收益比:每支默认止损 -10%,R:R=(目标中值-买入中值)/(买入中值-止损);给"买入"的标的 R:R 必须 ≥ 2,不满足就降级观望。
8. 市场体制:看 QQQ vs MA200 + 成分宽度判顺势/中性/逆风,写进 market。

【诚实底线,违反即失败】
- 价格、涨跌幅、券商一致目标价、财报日只能用我给你的数据 JSON 里的真实值,★绝对禁止编造或凭记忆改任何数字★。
- 绝不承诺 90% 命中率、绝不声称比专业更准;命中率现实 50-65%,不确定就说不确定。
- 某支数据缺失(无 price),该支 sig 给"观望"、buy/tgt 给"—"、th 注明"数据缺失本期不给买点"。
- 仅研究/学习用途,非投资建议。

【输出格式】只输出一个 JSON 对象(不要 markdown 代码围栏、不要任何解释文字),schema:
{"asof":"<北京日期>","market":"<一句话大盘与板块体制,可含<b>高亮>","ranking":["<按买点吸引力从高到低的 11 个 ticker>"],
 "stocks":{"<TICKER>":{"sig":"买入/观望/回避","conf":<0-10整数>,"buy":"<区间如 195–208 或 —>","tgt":"<区间如 265–300 或 —>","ret":"<如 +40% 或 —>","th":"<论点:趋势/动量+对标共识(引 target_mean)+引当前催化剂>","rk":"<主要风险>"}}}
ranking 与 stocks 必须恰好覆盖我给的全部 ticker。buy/tgt 用 – 连接区间。"""


def build_user_prompt(cfg, data, verification):
    tickers = [s["ticker"] for s in cfg["stocks"]]
    lines = [f"【北京日期】{TODAY}", f"【标的池(必须全覆盖,共 {len(tickers)} 支)】{tickers}", "", "【真实行情数据(只能用这些数字,禁止编造)】"]
    for tk in tickers:
        d = data.get(tk, {})
        if "price" not in d:
            lines.append(f"- {tk} {d.get('name','')}: ❌ 数据缺失(本期该支给观望、买点—)")
            continue
        a = d.get("analyst", {}) or {}
        nw = (d.get("news") or [])
        news = (" | 催化剂:" + nw[0].get("title", "")[:60]) if nw else ""
        lines.append(
            f"- {tk} {d.get('name','')}[{d.get('role','')}]: 价${d.get('price')} | 1月{d.get('m1')}% 3月{d.get('m3')}% 6月{d.get('m6')}% | "
            f"距52周高{d.get('fromhi')}% | MA50${d.get('ma50')} MA200${d.get('ma200')} | 52周${d.get('lo')}-${d.get('hi')} | "
            f"券商一致${a.get('target_mean')}(低${a.get('target_low')}/高${a.get('target_high')}) {a.get('rating')} {a.get('n_analysts')}家 fwdPE{a.get('fwd_pe')} | "
            f"下次财报{d.get('earnings_date')}{news}")
    meta = data.get("meta", {})
    if meta.get("degraded"):
        lines.append(f"\n⚠️ 注意:本期行情为降级数据({meta.get('banner','')}),在 market 字段如实说明。")
    cal = (verification or {}).get("calibration")
    if cal:
        lines.append(f"\n【上期复盘校准建议】{cal}")
    lines.append("\n现在输出研判 JSON(只输出 JSON 本身):")
    return "\n".join(lines)


def call_llm(system, user):
    headers = {"anthropic-version": "2023-06-01", "content-type": "application/json"}
    if API_KEY:
        headers["x-api-key"] = API_KEY
    if AUTH_TOKEN:
        headers["authorization"] = f"Bearer {AUTH_TOKEN}"
    payload = {"model": MODEL, "max_tokens": 4000, "system": system,
               "messages": [{"role": "user", "content": user}]}
    last = None
    for i in range(3):
        try:
            r = requests.post(f"{BASE_URL}/v1/messages", headers=headers, json=payload, timeout=120)
            if r.status_code == 200:
                blocks = r.json().get("content", [])
                txt = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                if txt.strip():
                    return txt
                last = "返回空文本"
            else:
                last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last = str(e)[:200]
        if i < 2:
            time.sleep(3 * (2 ** i))
    raise RuntimeError(f"LLM 调用失败(重试3次): {last}")


def extract_json(txt):
    """从模型输出里抠出 JSON(容忍 ```json 围栏、前后多余文字)。"""
    t = txt.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e != -1 and e > s:
        return json.loads(t[s:e + 1])
    raise ValueError("输出中找不到合法 JSON")


def validate(calls, cfg, data):
    """校验 schema + 反编造:ticker 必须与 config 一致、不得凭空多/少。"""
    want = {s["ticker"] for s in cfg["stocks"]}
    got = set(calls.get("stocks", {}).keys())
    if got != want:
        raise ValueError(f"ticker 不匹配:缺 {want - got} 多 {got - want}")
    for tk, a in calls["stocks"].items():
        for k in ("sig", "buy", "tgt", "ret", "th", "rk"):
            if k not in a:
                raise ValueError(f"{tk} 缺字段 {k}")
    if not calls.get("ranking") or set(calls["ranking"]) != want:
        calls["ranking"] = list(calls["stocks"].keys())  # 兜底:ranking 不全就用 stocks 顺序
    calls["asof"] = TODAY
    return calls


def main():
    if not API_KEY and not AUTH_TOKEN:
        print("ℹ️ 未配置 RESEARCH_API_KEY / RESEARCH_AUTH_TOKEN,跳过云端研判(将沿用最近一期研判)。")
        return
    cfg = json.load(open(os.path.join(DIR, "config.json"), encoding="utf-8"))
    data_path = os.path.join(STATE, f"data_{TODAY}.json")
    if not os.path.exists(data_path):
        print(f"ℹ️ 无 {data_path}(fetch 未产出),跳过研判,沿用最近一期。")
        return
    data_full = json.load(open(data_path, encoding="utf-8"))
    data = data_full.get("stocks", {})
    verification = None
    vp = os.path.join(STATE, "verification.json")
    if os.path.exists(vp):
        verification = json.load(open(vp, encoding="utf-8"))

    user = build_user_prompt(cfg, data, verification)
    out_path = os.path.join(STATE, f"calls_{TODAY}.json")
    try:
        txt = call_llm(SYSTEM, user)
        calls = validate(extract_json(txt), cfg, data)
    except Exception as e:
        # 失败绝不覆盖已有研判;由 build_board 复用最近一期 + 橙色"研判过期"如实标注
        print(f"⚠️ 云端研判失败({str(e)[:160]}),不覆盖既有 calls,沿用最近一期研判。")
        return
    json.dump(calls, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    top = [tk for tk in calls.get("ranking", []) if calls["stocks"].get(tk, {}).get("sig", "").startswith("买入")][:3]
    print(f"✅ 云端研判完成({MODEL}) → {out_path};买点 Top: {top}")


if __name__ == "__main__":
    main()
