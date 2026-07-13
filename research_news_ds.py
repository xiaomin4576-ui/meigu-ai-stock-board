#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全球头条研判(DeepSeek):读 state/news_raw_<date>.json 候选 → 双档筛选+传导链注解 → state/news_<date>.json。
双档结构(用户确认):🌍宏观/地缘 5-8 条 + 🤖科技/AI 产业 5-8 条,总量 10-15 条,按市场影响力排序。
每条给「传导链」:事件 → 对美股意味着什么 → 映射到 A股哪条链(本板块区别于普通新闻聚合的灵魂)。
无 DEEPSEEK_API_KEY 时优雅跳过(保留最近一期 news_*.json,渲染层自动复用+标新鲜度)。
每次调用的 token 用量落 state/usage.jsonl(运营看板消耗统计用)。"""
import os, json, glob, datetime
import requests

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
KEY = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
BASE = (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()

PROMPT = """你是华尔街宏观+科技+能源三栖分析师,为「全球市场头条」看板从候选新闻里筛编今日头条。读者两类:①跟踪美股AI产业链+A股算力链的交易者(传导:国际局势→美股→A股);②在莫桑比克经营油气/能源业务的联合能源Union公司(传导:全球油气市场→莫桑比克/东非经营)。
【任务】从下面候选新闻中筛选并输出 JSON 对象:{"items":[...]},共 15-21 条,分三档:
- cat="macro":宏观/地缘档 5-7 条——美联储/利率/通胀、关税/贸易、地缘冲突、重大政策选举,凡影响美股整体的。**要人表态(美联储主席/美财长/各国央行行长级)与官方数据发布(非农/CPI/FOMC)优先入选且 impact 上浮**;宏观档传导链尽量走三层:事件→市场即时反应→政策意图/博弈含义→对美股与A股。
- cat="oil":全球石油/能源档 5-7 条——OPEC+产量与油价(Brent/WTI)、天然气/LNG市场、能源巨头动向(道达尔/埃克森等)、供应链与航运(霍尔木兹/苏伊士)、非洲尤其莫桑比克/东非油气项目(Rovuma、Cabo Delgado LNG 等),凡影响全球油气市场的。
- cat="tech":科技/AI 产业档 5-7 条——大厂财报/指引、芯片与出口管制、AI 监管、算力产业链大事,凡影响科技板块的。
【每条字段】{"cat":"macro/oil/tech","idx":候选编号整数(必给,链接与来源由系统按编号回填,你不用抄url),"title":"中文标题≤30字","brief":"两句内中文摘要≤80字","chain":"传导链≤70字——macro/tech档:事件→对美股的含义→映射A股哪条链;oil档:事件→油价/LNG走向→对莫桑比克·东非能源经营的含义","impact":1-10整数(市场影响力)}
【硬纪律】① 只能基于候选列表改写,绝不虚构事件/数字;标题摘要忠于原文。② 同一事件多条只留最重要一条;地缘事件若同时影响油市(如海峡遇袭),macro 与 oil 只入一档、按主要影响归档。③ 各档内按 impact 降序。④ idx 必须是候选列表里的真实编号。⑤ 候选里够不出某档 5 条就少给,直说,不凑数。⑥ 输出保持紧凑,别加多余字段。⑦ 跨档查重:同一事件全篇只允许出现一次(曾出现美联储报告同时占宏观#1与科技#5——禁止)。⑧ 传导链一致性自检:同一标的(黄金/利率/油价等)在多条传导链中的方向判断必须一致,确有分歧要用"短期/中期"限定语区分,不许同页互相打架。
【候选新闻】
"""


def ds_call(prompt):
    """每次拿到响应就落账 usage(成功/截断/解析失败都计费)——体检发现截断事故三天漏记约80次真实调用。"""
    import time
    for i in range(3):
        try:
            r = requests.post(BASE + "/chat/completions",
                headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                      # max_tokens 曾设3000:CI候选144条时输出被掐断→JSONDecodeError循环失败、头条卡旧3天。
                      # 现输出只含idx不抄url(瘦40%)+上限放到6000,双保险根治截断。
                      "response_format": {"type": "json_object"}, "temperature": 0.3, "max_tokens": 6000},
                timeout=180)
            if r.status_code != 200:
                # 非200要留痕(不打印key):首次CI失败被静默吞了88秒,毫无线索——诊断输出是止损的一半
                print(f"  尝试{i+1}: HTTP {r.status_code} {r.text[:150]}")
                time.sleep(5)
                continue
            j = r.json()
            usage = j.get("usage", {})
            fin = (j.get("choices") or [{}])[0].get("finish_reason")
            if fin == "length":
                log_usage(usage, "news", note="truncated")
                print(f"  尝试{i+1}: 输出被截断(finish_reason=length),重试")
                time.sleep(5)
                continue
            try:
                content = json.loads(j["choices"][0]["message"]["content"])
            except Exception as e:
                log_usage(usage, "news", note="parse_fail")
                print(f"  尝试{i+1}: 解析失败 {repr(e)[:120]}")
                time.sleep(5)
                continue
            log_usage(usage, "news")
            return content
        except Exception as e:
            print(f"  尝试{i+1}: 异常 {repr(e)[:150]}")
            time.sleep(5)
    return None


def log_usage(usage, purpose, note=None):
    """token 用量落账(追加),运营看板据此统计 DeepSeek 消耗。note 标注失败形态(truncated/parse_fail)。"""
    if not usage:
        return
    rec = {"ts": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"),
           "engine": "deepseek-chat", "purpose": purpose,
           "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
           "total_tokens": usage.get("total_tokens")}
    if note:
        rec["note"] = note
    with open(os.path.join(STATE, "usage.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    raw_p = os.path.join(STATE, f"news_raw_{TODAY}.json")
    if not os.path.exists(raw_p):
        files = sorted(glob.glob(os.path.join(STATE, "news_raw_*.json")))
        if not files:
            print("⚠️ 无候选新闻,跳过")
            return
        raw_p = files[-1]
    raw = json.load(open(raw_p, encoding="utf-8"))
    cands = raw.get("candidates", [])
    if not cands:
        print("⚠️ 候选为空,跳过")
        return
    if not KEY:
        print("ℹ️ 无 DEEPSEEK_API_KEY,保留最近一期头条(渲染层自动复用)")
        return
    pool = cands[:70]
    lines = []
    for i, c in enumerate(pool):
        # 喂给模型的候选行不带URL(模型只回 idx,链接由下面按编号回填)——URL又长又占输出,曾把回答撑爆截断
        lines.append(f"{i+1}. [{c.get('source','')}|{c.get('ts','')}] {c.get('title','')} — {c.get('summary','')[:100]}")
    result = ds_call(PROMPT + "\n".join(lines))
    if not result or not isinstance(result.get("items"), list) or not result["items"]:
        print("❌ DeepSeek 未返回有效头条,保留最近一期")
        return
    CAT_ALIAS = {"macro": "macro", "宏观": "macro", "tech": "tech", "科技": "tech",
                 "oil": "oil", "石油": "oil", "能源": "oil", "energy": "oil"}
    items = []
    for it in result["items"][:21]:
        cat = CAT_ALIAS.get(str(it.get("cat", "")).strip().lower()) or CAT_ALIAS.get(str(it.get("cat", "")).strip())
        if not cat or not it.get("title"):
            continue
        # 按 idx 从候选原样回填 url/source/ts:链接100%保真(模型从不经手),也不再需要白名单兜底
        src_c = {}
        try:
            k = int(it.get("idx")) - 1
            if 0 <= k < len(pool):
                src_c = pool[k]
        except Exception:
            pass
        items.append({"cat": cat, "title": it.get("title"), "brief": it.get("brief"),
                      "chain": it.get("chain"), "impact": it.get("impact"),
                      "source": src_c.get("source", ""), "url": src_c.get("url", ""), "ts": src_c.get("ts", "")})
    # 空结果绝不落盘——否则会顶掉最近一期有效头条、还被渲染层误标"今日"(审查已复现,与容错设计矛盾)
    if not items:
        print("❌ 筛编后 0 条有效头条,不落盘,保留最近一期")
        return
    out = {"asof": raw.get("asof", TODAY), "generated_by": "deepseek-chat",
           "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="minutes"),
           "items": items}
    path = os.path.join(STATE, f"news_{TODAY}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = lambda c: sum(1 for i in items if i["cat"] == c)
    print(f"✅ 头条 {len(items)} 条(宏观{n('macro')}/石油{n('oil')}/科技{n('tech')})→ {path}")


if __name__ == "__main__":
    main()
