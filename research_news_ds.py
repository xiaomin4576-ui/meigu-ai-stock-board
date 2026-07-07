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

PROMPT = """你是华尔街宏观+科技双栖分析师,为「全球市场头条」看板从候选新闻里筛编今日头条。读者是跟踪美股AI产业链+A股算力链的交易者,传导逻辑:国际局势→美股→A股。
【任务】从下面候选新闻中筛选并输出 JSON 对象:{"items":[...]},共 10-15 条,分两档:
- cat="macro":宏观/地缘档 5-8 条——美联储/利率/通胀、关税/贸易、地缘冲突、油价/大宗、重大政策选举,凡影响美股整体的。
- cat="tech":科技/AI 产业档 5-8 条——大厂财报/指引、芯片与出口管制、AI 监管、算力产业链大事,凡影响科技板块的。
【每条字段】{"cat":"macro/tech","title":"中文标题≤30字","brief":"两句内中文摘要≤80字","chain":"传导链:事件→对美股的含义→映射到A股哪条链,≤70字","impact":1-10整数(市场影响力),"source":"来源名","url":"原文链接原样保留","ts":"时间原样保留"}
【硬纪律】① 只能基于候选列表改写,绝不虚构事件/数字;标题摘要忠于原文。② 同一事件多条只留最重要一条。③ 按 impact 降序。④ url/source/ts 原样带回,禁改。⑤ 候选里够不出某档 5 条就少给,直说,不凑数。
【候选新闻】
"""


def ds_call(prompt):
    import time
    for i in range(3):
        try:
            r = requests.post(BASE + "/chat/completions",
                headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                      "response_format": {"type": "json_object"}, "temperature": 0.3, "max_tokens": 3000},
                timeout=150)
            if r.status_code == 200:
                j = r.json()
                usage = j.get("usage", {})
                return json.loads(j["choices"][0]["message"]["content"]), usage
            # 非200要留痕(不打印key):首次CI失败被静默吞了88秒,毫无线索——诊断输出是止损的一半
            print(f"  尝试{i+1}: HTTP {r.status_code} {r.text[:150]}")
        except Exception as e:
            print(f"  尝试{i+1}: 异常 {repr(e)[:150]}")
        time.sleep(5)
    return None, None


def log_usage(usage, purpose):
    """token 用量落账(幂等追加),运营看板据此统计 DeepSeek 消耗。"""
    if not usage:
        return
    rec = {"ts": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"),
           "engine": "deepseek-chat", "purpose": purpose,
           "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
           "total_tokens": usage.get("total_tokens")}
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
    lines = []
    for i, c in enumerate(cands[:70]):
        lines.append(f"{i+1}. [{c.get('source','')}|{c.get('ts','')}] {c.get('title','')} — {c.get('summary','')[:120]} URL={c.get('url','')}")
    result, usage = ds_call(PROMPT + "\n".join(lines))
    log_usage(usage, "news")
    if not result or not isinstance(result.get("items"), list) or not result["items"]:
        print("❌ DeepSeek 未返回有效头条,保留最近一期")
        return
    # url 白名单兜底:「原样带回」不能只靠提示词,不在候选集内的链接一律置空(渲染层降级为纯来源名)
    valid_urls = {c.get("url") for c in cands if c.get("url")}
    CAT_ALIAS = {"macro": "macro", "宏观": "macro", "tech": "tech", "科技": "tech"}
    items = []
    for it in result["items"][:15]:
        cat = CAT_ALIAS.get(str(it.get("cat", "")).strip().lower()) or CAT_ALIAS.get(str(it.get("cat", "")).strip())
        if not cat or not it.get("title"):
            continue
        it["cat"] = cat
        if it.get("url") and it["url"] not in valid_urls:
            it["url"] = ""
        items.append({k: it.get(k) for k in ("cat", "title", "brief", "chain", "impact", "source", "url", "ts")})
    # 空结果绝不落盘——否则会顶掉最近一期有效头条、还被渲染层误标"今日"(审查已复现,与容错设计矛盾)
    if not items:
        print("❌ 筛编后 0 条有效头条,不落盘,保留最近一期")
        return
    out = {"asof": raw.get("asof", TODAY), "generated_by": "deepseek-chat",
           "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="minutes"),
           "items": items}
    path = os.path.join(STATE, f"news_{TODAY}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    macro_n = sum(1 for i in items if i["cat"] == "macro")
    print(f"✅ 头条 {len(items)} 条(宏观{macro_n}/科技{len(items)-macro_n})→ {path}")


if __name__ == "__main__":
    main()
