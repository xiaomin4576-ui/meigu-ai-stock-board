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

PROMPT = """你是华尔街宏观+地缘+能源+科技四栖分析师,为「全球市场头条」看板从候选新闻里筛编今日头条。读者两类:①跟踪美股AI产业链+A股算力链的交易者(传导:国际局势→美股→A股);②在莫桑比克经营油气/能源业务的联合能源Union公司(传导:全球油气市场→莫桑比克/东非经营)。
【任务】从下面候选新闻中筛选并输出 JSON 对象:{"items":[...]},共 15-24 条,分六档,每档 2-5 条(够不出就少给,不凑数):
- cat="macro":宏观档——美联储/利率/通胀/就业、关税/贸易政策、财政/央行政策、官方数据发布(非农/CPI/PMI/FOMC)。**要人表态(美联储主席/美财长/央行行长级)与官方硬数据优先入选且 impact 上浮**。
- cat="geo":地缘档——地缘冲突/战争、大国博弈/制裁、重大选举、地区局势(中东/俄乌/台海/南海等),凡以地缘政治为主要驱动的。
- cat="oil":石油档——OPEC+产量与配额、原油价格(Brent/WTI)、石油巨头(埃克森/雪佛龙/道达尔等)、炼油与原油航运(霍尔木兹/苏伊士)。
- cat="gas":天然气档——LNG/天然气市场与价格(Henry Hub/TTF)、非洲尤其莫桑比克/东非天然气项目(Rovuma、Cabo Delgado LNG、坦桑LNG 等)、气源供应与航运,凡影响全球天然气/LNG市场的。
- cat="tech":科技档——大厂财报/指引、半导体/芯片与出口管制、硬件与消费电子、云与企业软件等非纯AI的科技产业大事。
- cat="ai":AI档——AI模型发布/能力、AI监管/治理、算力与AI基础设施、AI产业投融资与落地,凡以人工智能为主要驱动的。
【每条字段】{"cat":"macro/geo/oil/gas/tech/ai","idx":候选编号整数(必给,链接与来源由系统按编号回填,你不用抄url),"title":"中文标题≤30字","brief":"两句内中文摘要≤80字","chain":"传导链≤70字——macro/geo/tech/ai档:事件→对美股的含义→映射A股哪条链;oil/gas档:事件→油价或气价/LNG走向→对莫桑比克·东非能源经营的含义","impact":1-10整数(市场影响力)}
【硬纪律】① 只能基于候选列表改写,绝不虚构事件/数字;标题摘要忠于原文。② 同一事件多条只留最重要一条;一事跨多档(如海峡遇袭同时属地缘与石油)按【主要驱动】只归一档,不重复。③ 各档内按 impact 降序。④ idx 必须是候选列表里的真实编号。⑤ 够不出某档就少给或留空,直说,不凑数。⑥ 输出保持紧凑,别加多余字段。⑦ 跨档查重:同一事件全篇只允许出现一次。⑧ 传导链一致性自检:同一标的(黄金/利率/油价/气价等)在多条传导链中的方向判断必须一致,有分歧用"短期/中期"限定语区分,不许同页互相打架。⑨ 石油与天然气是并列的能源子档、别混为一档;宏观与地缘、科技与AI 亦按主要驱动各归其档。⑩【事件簇上限·硬约束】:同一【核心事件】的不同侧面/后续/各方反应(如"美伊冲突/霍尔木兹"的军事·油价·外交·市场反应)算【一个事件簇】,判定按【核心实体+主题】而非标题字面;**同一事件簇全篇(跨所有档合计)最多保留 2 条**(取影响力最高的一体两面),绝不许一个事件簇霸占近半版面挤掉俄乌/台海/OPEC基本面/其它地区。先把候选按事件簇归并,再每簇选代表,保证版面主题多样。
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
    # 审计F21:按来源配额建候选池,不做整体 cands[:70] 硬截断——能源专项 RSS(OilPrice/Offshore Energy/
    # 莫桑东非聚合等)在 fetch 去重序里排在 finnhub/东财之后,整体截断会把 oil 档信源饿死、专用能源覆盖沦为摆设。
    # 行只含 idx+title(已瘦身)、max_tokens=6000,池容量放到 ~85 仍安全。
    by_origin = {}
    for c in cands:
        by_origin.setdefault(c.get("origin", "rss"), []).append(c)
    pool = (by_origin.get("finnhub", [])[:28] + by_origin.get("em", [])[:27] + by_origin.get("rss", [])[:30])
    if not pool:                      # 兜底:万一无 origin 字段,退回原整体截断
        pool = cands[:70]
    lines = []
    for i, c in enumerate(pool):
        # 喂给模型的候选行不带URL(模型只回 idx,链接由下面按编号回填)——URL又长又占输出,曾把回答撑爆截断
        lines.append(f"{i+1}. [{c.get('source','')}|{c.get('ts','')}] {c.get('title','')} — {c.get('summary','')[:100]}")
    result = ds_call(PROMPT + "\n".join(lines))
    if not result or not isinstance(result.get("items"), list) or not result["items"]:
        print("❌ DeepSeek 未返回有效头条,保留最近一期")
        return
    CAT_ALIAS = {"macro": "macro", "宏观": "macro",
                 "geo": "geo", "地缘": "geo", "geopolitics": "geo", "geopolitical": "geo",
                 "oil": "oil", "石油": "oil", "原油": "oil", "crude": "oil",
                 "gas": "gas", "天然气": "gas", "lng": "gas", "naturalgas": "gas",
                 "tech": "tech", "科技": "tech",
                 "ai": "ai", "人工智能": "ai", "energy": "oil", "能源": "oil"}
    items, seen_idx, seen_ttl = [], set(), set()
    for it in result["items"][:21]:
        cat = CAT_ALIAS.get(str(it.get("cat", "")).strip().lower()) or CAT_ALIAS.get(str(it.get("cat", "")).strip())
        if not cat or not it.get("title"):
            continue
        # 审计F11:跨档查重程序化护栏——"同一事件只出现一次"此前只是 prompt 纪律,
        # 模型重复回同一候选 idx / 同一标题时会重复上页,这里按 idx+归一化标题双键去重(先到保留)。
        # F22 回归修正:标题键用【完整归一化标题】,不再截前24字符——同主题重日(如伊朗冲突衍生多条)
        # 前缀高度相同,截断键会误杀不同事件;完整标题只对真正逐字相同的才碰撞。
        ttl_key = "".join(ch for ch in str(it.get("title", "")).lower() if ch.isalnum())
        try:
            idx_key = int(it.get("idx"))
        except Exception:
            idx_key = None
        if (idx_key is not None and idx_key in seen_idx) or (ttl_key and ttl_key in seen_ttl):
            continue
        if idx_key is not None:
            seen_idx.add(idx_key)
        if ttl_key:
            seen_ttl.add(ttl_key)
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
    print(f"✅ 头条 {len(items)} 条(宏观{n('macro')}/地缘{n('geo')}/石油{n('oil')}/天然气{n('gas')}/科技{n('tech')}/AI{n('ai')})→ {path}")


if __name__ == "__main__":
    main()
