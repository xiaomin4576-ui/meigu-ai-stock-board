#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全球头条研判(DeepSeek):读 state/news_raw_<date>.json 候选 → 六档筛选+传导链注解 → state/news_<date>.json。
六档:宏观/地缘/石油/天然气/科技/AI,总量 15-24 条,按市场影响力排序。
每条给「传导链」:事件 → 对美股意味着什么 → 映射到 A股哪条链(本板块区别于普通新闻聚合的灵魂)。
无 DEEPSEEK_API_KEY 时优雅跳过(保留最近一期 news_*.json,渲染层自动复用+标新鲜度)。
每次调用的 token 用量落 state/usage.jsonl(运营看板消耗统计用)。

2026-07-19 加【程序化事件簇护栏】:prompt 纪律⑩(同簇≤2)DeepSeek 屡不严守——07-13 美伊占 47%,
prompt 强化后 07-19 战争升级日仍 11/21 条,其中 4 对是同 URL 文章换标题重复上页。与股票研判同一
结论:LLM 自觉不可靠,硬约束必须代码强制(仿 validate_call)。四层:
  ① 同页 URL 硬去重(同一篇文章只上一次,零误伤)
  ② 跨天 7 日 URL 压制(同一原文七天窗口只推荐一次——工程规则第 4 条程序化)
  ③ 实体聚类每簇硬上限 2(1 条事件本身 + 1 条市场传导)
  ④ 裁后不足 15 条时二轮回补其它主题(把版面真正让给别的事件,而非只裁短)
黄金/贵金属按 2026-07-19 四专家评审全票结论【归宏观档显式抬升、不另设档】,配专属传导链规则⑪。"""
import os, re, json, glob, datetime
import requests

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
KEY = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
BASE = (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()

PROMPT = """你是华尔街宏观+地缘+能源+科技四栖分析师,为「全球市场头条」看板从候选新闻里筛编今日头条。读者两类:①跟踪美股AI产业链+A股算力链的交易者(传导:国际局势→美股→A股);②在莫桑比克经营油气/能源业务的联合能源Union公司(传导:全球油气市场→莫桑比克/东非经营)。
【任务】从下面候选新闻中筛选并输出 JSON 对象:{"items":[...]},共 15-24 条,分六档,每档 2-5 条(够不出就少给,不凑数):
- cat="macro":宏观档——美联储/利率/通胀/就业、关税/贸易政策、财政/央行政策、官方数据发布(非农/CPI/PMI/FOMC)、黄金/贵金属(避险·实际利率·央行购金/去美元化的宏观风向标,归本档、不另设档)。**要人表态(美联储主席/美财长/央行行长级)与官方硬数据优先入选且 impact 上浮**。
- cat="geo":地缘档——地缘冲突/战争、大国博弈/制裁、重大选举、地区局势(中东/俄乌/台海/南海等),凡以地缘政治为主要驱动的。
- cat="oil":石油档——OPEC+产量与配额、原油价格(Brent/WTI)、石油巨头(埃克森/雪佛龙/道达尔等)、炼油与原油航运(霍尔木兹/苏伊士)。
- cat="gas":天然气档——LNG/天然气市场与价格(Henry Hub/TTF)、非洲尤其莫桑比克/东非天然气项目(Rovuma、Cabo Delgado LNG、坦桑LNG 等)、气源供应与航运,凡影响全球天然气/LNG市场的。
- cat="tech":科技档——大厂财报/指引、半导体/芯片与出口管制、硬件与消费电子、云与企业软件等非纯AI的科技产业大事。
- cat="ai":AI档——AI模型发布/能力、AI监管/治理、算力与AI基础设施、AI产业投融资与落地,凡以人工智能为主要驱动的。
【每条字段】{"cat":"macro/geo/oil/gas/tech/ai","idx":候选编号整数(必给,链接与来源由系统按编号回填,你不用抄url),"title":"中文标题≤30字","brief":"两句内中文摘要≤80字","chain":"传导链≤70字——macro/geo/tech/ai档:事件→对美股的含义→映射A股哪条链;oil/gas档:事件→油价或气价/LNG走向→对莫桑比克·东非能源经营的含义","impact":1-10整数(市场影响力)}
【硬纪律】① 只能基于候选列表改写,绝不虚构事件/数字;标题摘要忠于原文。② 同一事件多条只留最重要一条;一事跨多档(如海峡遇袭同时属地缘与石油)按【主要驱动】只归一档,不重复。③ 各档内按 impact 降序。④ idx 必须是候选列表里的真实编号。⑤ 够不出某档就少给或留空,直说,不凑数。⑥ 输出保持紧凑,别加多余字段。⑦ 跨档查重:同一事件全篇只允许出现一次。⑧ 传导链一致性自检:同一标的(黄金/利率/油价/气价等)在多条传导链中的方向判断必须一致,有分歧用"短期/中期"限定语区分,不许同页互相打架。⑨ 石油与天然气是并列的能源子档、别混为一档;宏观与地缘、科技与AI 亦按主要驱动各归其档。⑩【事件簇上限·硬约束·最优先执行】:同一【核心事件】的所有侧面/后续/各方反应(如"美伊冲突/霍尔木兹"的军事打击·油价·航运·各国表态·外交)算【一个事件簇】,判定按【核心实体+主题】而非标题字面。**任何一个事件簇,即便是当日头号大事,全站(跨所有六档合计)【硬上限2条】**:1条讲事件本身(归地缘/宏观)、最多再1条讲其最关键的市场传导(归石油/天然气),【其余同簇侧面(军事细节/第N次打击/各方谴责/单船事故/航运警告…)一律删,不给任何档】,把版面让给俄乌/台海/OPEC基本面/亚非拉/科技AI 等其它主题。若某簇候选特别多——那恰说明当日该主题过热、更要克制。**做法:先按事件簇把全部候选归并,数出每簇候选数,每簇只放行 ≤2 条最高影响力的,再填充其它簇,确保 15-24 条覆盖尽量多的不同事件簇而非同一件事的车轮战。**自检:输出后数一下最大事件簇占了几条,>2 就是违规,删到 2。系统另有程序化护栏兜底强制此上限,超出部分会被自动裁撤——省下的名额请主动分给其它事件簇。⑪【黄金/贵金属传导链专属写法】(2026-07 经济学家评审定,不套「事件→美股→A股算力链」通用模板):黄金=实际利率+美元+避险情绪的镜像,是 AI 成长股估值贴现的反向温度计——chain 写「金价异动的主导驱动(避险还是利率)→对美股 AI 高久期票估值分母/风险偏好的含义→A股算力链情绪传导」;央行购金/去美元化/实际利率拐点类结构性信号优先于"金价测试某点位"式行情复盘;黄金与莫桑比克油气经营无直接传导,不硬编经营含义。
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


CAT_ALIAS = {"macro": "macro", "宏观": "macro",
             "geo": "geo", "地缘": "geo", "geopolitics": "geo", "geopolitical": "geo",
             "oil": "oil", "石油": "oil", "原油": "oil", "crude": "oil",
             "gas": "gas", "天然气": "gas", "lng": "gas", "naturalgas": "gas",
             "tech": "tech", "科技": "tech",
             "ai": "ai", "人工智能": "ai", "energy": "oil", "能源": "oil"}

# ══ 程序化事件簇护栏 ═══════════════════════════════════════════════════════════
# 设计(保守优先,宁放过不误杀;已在 07-13~07-19 五天真实头条上回放验证):
#   实体只认【专名】(泛词"油价/市场/美股"不作聚类证据);标题实体=主角 prim,标题+摘要=全量 pooled。
#   成簇边:①pooled 共享≥2 ②prim 共享≥1 且双方冲突语境 ③prim 共享咽喉强实体(霍尔木兹/红海/苏伊士)
#         ④标题+摘要 bigram 包含度≥0.62(同文改写)
#   并查集成簇后做【同战区卫星吸收】:冲突语境的单条,标题实体属同一战区、且触及簇的冻结标题实体集
#   才并入——冻结集不随吸收外扩,防"俄外长评美伊停火"这类配角实体把俄乌战线桥进美伊簇(07-18 实测);
#   衍生政治条目(如"参议院因伊朗战争阻国防法案",标题无战区实体)不吸收,保差异化视角。
#   每簇硬上限 2:留最高 impact(事件本身)+ 不同档最高 impact(市场传导);裁撤逐条留痕进 guard 元数据。

_ENT_ALIASES = {
    "伊朗": ("伊朗", "美伊", "以伊", "伊核", "革命卫队", "德黑兰", "iran"),
    "以色列": ("以色列", "以军", "以哈", "内塔尼亚胡", "israel"),
    "加沙": ("加沙", "哈马斯", "gaza", "hamas"),
    "黎巴嫩": ("黎巴嫩", "真主党", "贝鲁特", "hezbollah"),
    "胡塞": ("胡塞", "houthi", "houthis"),
    "也门": ("也门", "亚丁", "yemen", "aden"),
    "红海": ("红海", "red sea"),
    "霍尔木兹": ("霍尔木兹", "hormuz"),
    "苏伊士": ("苏伊士", "suez"),
    "巴林": ("巴林", "bahrain"),
    "卡塔尔": ("卡塔尔", "多哈", "qatar"),
    "约旦": ("约旦", "安曼", "亚喀巴", "jordan", "aqaba"),
    "沙特": ("沙特", "利雅得", "saudi"),
    "阿联酋": ("阿联酋", "迪拜", "阿布扎比", "uae"),
    "伊拉克": ("伊拉克", "巴格达", "iraq"),
    "叙利亚": ("叙利亚", "大马士革", "syria"),
    "海湾": ("海湾", "波斯湾"),
    "中东": ("中东", "mideast"),
    "俄罗斯": ("俄罗斯", "俄乌", "俄军", "普京", "克里姆林", "莫斯科", "russia"),
    "乌克兰": ("乌克兰", "基辅", "泽连斯基", "ukraine"),
    "朝鲜": ("朝鲜", "平壤", "金正恩"),
    "台海": ("台海", "台湾", "台北"),
    "南海": ("南海",),
    "印巴": ("印巴", "克什米尔"),
    "委内瑞拉": ("委内瑞拉", "马杜罗", "venezuela"),
    "OPEC": ("opec", "欧佩克"),
    "美联储": ("美联储", "fomc", "warsh", "沃什", "鲍威尔", "哈玛克", "威廉姆斯"),
    "欧央行": ("欧央行", "拉加德"),
    "英伟达": ("英伟达", "nvidia"),
    "苹果": ("苹果", "apple", "库克"),
    "台积电": ("台积电", "tsmc"),
    "ASML": ("asml", "阿斯麦"),
    "OpenAI": ("openai", "奥特曼", "altman"),
    "Anthropic": ("anthropic",),
    "Meta": ("meta", "扎克伯格"),
    "微软": ("微软", "microsoft"),
    "谷歌": ("谷歌", "google", "alphabet"),
    "特斯拉": ("特斯拉", "tesla", "马斯克"),
    "阿里": ("阿里", "千问", "qwen", "alibaba"),
    "波音": ("波音", "boeing"),
    "三星": ("三星", "samsung"),
    "海力士": ("海力士", "hynix"),
    "英特尔": ("英特尔", "intel"),
    "美光": ("美光", "micron"),
    "软银": ("软银", "softbank"),
}
# 咽喉强实体:两条同日新闻共提同一咽喉要道,近乎必属同一storyline(通行量/封锁/遇袭都是同事件侧面)
_STRONG_ENTS = {"霍尔木兹", "红海", "苏伊士"}
# 战区分组:卫星吸收只允许同战区(防跨战线桥接)
_THEATERS = (
    {"伊朗", "以色列", "加沙", "黎巴嫩", "胡塞", "也门", "红海", "霍尔木兹", "苏伊士",
     "巴林", "卡塔尔", "约旦", "沙特", "阿联酋", "伊拉克", "叙利亚", "海湾", "中东"},
    {"俄罗斯", "乌克兰"},
    {"台海", "朝鲜", "南海"},
)
_THEATER_ALL = set().union(*_THEATERS)
# 机构/公司主角集(审计必修A):这些实体当标题主角时,条目只因捎带战区词(如"美联储报告:关税、
# 伊朗战争和AI推高通胀"/"波音无视伊朗战争维持预测")不得被卷进战争簇——独立机构动作≠战争侧面
_INSTITUTIONAL = {"美联储", "欧央行", "OPEC", "英伟达", "苹果", "台积电", "ASML", "OpenAI",
                  "Anthropic", "Meta", "微软", "谷歌", "特斯拉", "阿里", "波音", "三星",
                  "海力士", "英特尔", "美光", "软银"}
# 市场传导词(审计必修B):事件簇保留的第二席必须是"真传导"条目——含这些词才算讲市场影响
_TRANSMIT = ("油价", "气价", "汽油", "金价", "价格", "运费", "运价", "保费", "期货", "库存",
             "供应", "出口", "进口", "需求", "收益率", "美股", "欧股", "股价", "股市", "汇率",
             "美元", "日元", "航运", "海运", "航线", "船只", "油轮", "运输", "通行", "通胀",
             "成本", "lng", "LNG")
# 冲突语境词(刻意不含"威胁/紧张/升级/关闭"——它们常见于贸易战/行情语言,会误伤;CJK 子串匹配,拉丁按词)
_CONFLICT_CJK = ("打击", "空袭", "袭击", "遇袭", "遭袭", "攻击", "开火", "交火", "停火", "冲突",
                 "战争", "开战", "战火", "军事", "军方", "美军", "以军", "俄军", "导弹", "无人机",
                 "防空", "警报", "疏散", "撤离", "撤侨", "封锁", "制裁", "劫持", "扣押", "击落",
                 "击沉", "爆炸", "报复", "伤亡", "身亡", "阵亡", "遇难")
_CONFLICT_LAT = {"strike", "strikes", "attack", "attacks", "war", "missile", "drone", "ceasefire"}


def _txt_feats(txt):
    """返回 (实体集, 冲突语境?, bigram集)。拉丁别名按整词匹配(防 metal→Meta、warsh→war 类误击)。"""
    low = str(txt or "").lower()
    words = set(re.findall(r"[a-z][a-z0-9\-]+", low))
    ents = set()
    for ent, aliases in _ENT_ALIASES.items():
        for a in aliases:
            if a.isascii() and " " not in a:
                if a in words:
                    ents.add(ent)
                    break
            elif a in low:
                ents.add(ent)
                break
    confl = any(w in low for w in _CONFLICT_CJK) or bool(words & _CONFLICT_LAT)
    grams = set()
    for run in re.findall(r"[一-鿿]+", low):
        for i in range(len(run) - 1):
            grams.add(run[i:i + 2])
    grams |= words
    return ents, confl, grams


def _theater_of(ents):
    return {i for i, t in enumerate(_THEATERS) if ents & t}


def cluster_guard(items, cap=2):
    """事件簇护栏:返回 (保留列表, 裁撤明细, 簇调试信息)。"""
    n = len(items)
    prim, pooled, confl, grams, digs = [], [], [], [], []
    for it in items:
        pe, _, _ = _txt_feats(it.get("title"))
        full = str(it.get("title") or "") + " " + str(it.get("brief") or "")
        ae, cf, gr = _txt_feats(full)
        prim.append(pe)
        pooled.append(ae)
        confl.append(cf)
        grams.append(gr)
        # 数字签名只取【标题】——brief 常共享年份(2026)等背景数字,会让互斥否决失效
        digs.append(set(re.findall(r"\d+", str(it.get("title") or ""))))
    parent = list(range(n))

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            ps = prim[i] & prim[j]
            # 边②机构主角否决(审计必修A):共享实体全是战区词 且 任一方主角是机构/公司时,
            # 边②不成立(pooled≥2/咽喉强实体/文本近似不受影响)——防美联储报告/波音预测被误卷
            rule2 = bool(ps and confl[i] and confl[j])
            if rule2 and ps <= _THEATER_ALL and ((prim[i] & _INSTITUTIONAL) or (prim[j] & _INSTITUTIONAL)):
                rule2 = False
            same = (len(pooled[i] & pooled[j]) >= 2
                    or rule2
                    or bool(ps & _STRONG_ENTS))
            if not same and grams[i] and grams[j]:
                inter = len(grams[i] & grams[j])
                if inter / max(1, min(len(grams[i]), len(grams[j]))) >= 0.62:
                    # 数字互斥否决:模板化标题(如两家公司"预计上半年净利润增长X%-Y%")文本高度
                    # 相似但数字完全不同=不同事件,不并簇(07-07 瑞芯微/光库回放实测)
                    same = not (digs[i] and digs[j] and digs[i].isdisjoint(digs[j]))
            if same:
                _union(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(_find(i), []).append(i)
    # 同战区卫星吸收(冻结集=既有成员标题实体并集,吸收不外扩)
    multi = {r: list(m) for r, m in groups.items() if len(m) >= 2}
    frozen, conflmaj = {}, {}
    for r, m in multi.items():
        fs = set()
        for k in m:
            fs |= prim[k]
        frozen[r] = fs
        conflmaj[r] = sum(1 for k in m if confl[k]) * 2 >= len(m)
    single_roots = [r for r, m in groups.items() if len(m) == 1]
    for r0 in single_roots:
        i = groups[r0][0]
        if not confl[i]:
            continue
        if prim[i] & _INSTITUTIONAL:
            continue                      # 机构主角条目不吸收(审计必修A同源,防边②否决被吸收绕过)
        ti = _theater_of(prim[i])
        if not ti:
            continue
        best, best_size = None, 0
        for r, m in multi.items():
            if not conflmaj[r]:
                continue
            if not (_theater_of(frozen[r]) & ti):
                continue
            if (pooled[i] & frozen[r]) and len(m) > best_size:
                best, best_size = r, len(m)
        if best is not None:
            groups[best].append(i)
            groups.pop(r0, None)
    # 每簇 cap:留最高 impact(事件本身)+ 不同档最高 impact(市场传导)
    keep = set(range(n))
    dropped, clusters_dbg = [], []
    for r, m in groups.items():
        ents_lbl = set()
        for k in m:
            ents_lbl |= prim[k]
        if not ents_lbl:
            for k in m:
                ents_lbl |= pooled[k]
        ents_lbl = sorted(ents_lbl)
        capped = len(m) > cap
        clusters_dbg.append({"ents": ents_lbl[:4], "size": len(m), "capped": capped,
                             "titles": [str(items[k].get("title")) for k in m]})
        if not capped:
            continue
        order = sorted(m, key=lambda k: (-(items[k].get("impact") or 0), k))
        first = order[0]
        # 第二席=真市场传导(审计必修B):不同档 + 含传导词 + 与第一席文本差异大 + 实体签名不同构
        # (07-12 回放曾保留两条"霍尔木兹关闭"跨语种近重述)。簇内没有传导型候选就只留 1 条
        # (事件本身)——宁缺勿用同事件近重复稿凑数,cap 自动降 1。
        second = None
        for k in order[1:]:
            if items[k].get("cat") == items[first].get("cat"):
                continue
            ktxt = str(items[k].get("title") or "") + str(items[k].get("brief") or "")
            if not any(w in ktxt for w in _TRANSMIT):
                continue
            if prim[k] and prim[k] == prim[first]:
                continue
            ov = len(grams[k] & grams[first]) / max(1, min(len(grams[k]), len(grams[first])))
            if ov < 0.55:
                second = k
                break
        kept_pair = {first} if second is None else {first, second}
        label = "/".join(ents_lbl[:3]) or str(items[first].get("title"))[:16]
        for k in m:
            if k in kept_pair:
                continue
            keep.discard(k)
            dropped.append({"title": items[k].get("title"), "cat": items[k].get("cat"),
                            "impact": items[k].get("impact"), "cluster": label})
    kept = [items[i] for i in range(n) if i in keep]
    return kept, dropped, clusters_dbg


def _recent_urls(days=7):
    """近 N 天已上榜的原文 URL(不含今天)——落实"同一原文 URL 七天窗口只推荐一次"(工程规则第4条)。
    实测 07-17 的美伊互攻、07-18 的 CNBC 油轮文都曾在 07-19 原样重复上榜。"""
    urls = set()
    try:
        today = datetime.date.fromisoformat(TODAY)
    except Exception:
        return urls
    for f in glob.glob(os.path.join(STATE, "news_2*.json")):
        m = re.search(r"news_(\d{4}-\d{2}-\d{2})\.json$", f)
        if not m or m.group(1) >= TODAY:
            continue
        try:
            if (today - datetime.date.fromisoformat(m.group(1))).days > days:
                continue
            for it in json.load(open(f, encoding="utf-8")).get("items", []):
                u = (it.get("url") or "").strip()
                if u:
                    urls.add(u)
        except Exception:
            pass
    return urls


def _absorb(result, pool, items, seen_idx, seen_ttl, seen_url, cap_total=24):
    """把一轮 DeepSeek 返回吸收进 items:六档归一化、idx/标题/URL 三键去重、按 idx 回填链接。
    返回本轮因同页同 URL 被拒的条数(同文换标题重复上页,2026-07-19 实测一天 4 对)。"""
    url_dups = 0
    for it in (result.get("items") or []):
        if len(items) >= cap_total:
            break
        cat = CAT_ALIAS.get(str(it.get("cat", "")).strip().lower()) or CAT_ALIAS.get(str(it.get("cat", "")).strip())
        if not cat or not it.get("title"):
            continue
        # 审计F11/F22:idx+完整归一化标题双键去重(先到保留;截断键会误杀同前缀不同事件)
        ttl_key = "".join(ch for ch in str(it.get("title", "")).lower() if ch.isalnum())
        try:
            idx_key = int(it.get("idx"))
        except Exception:
            idx_key = None
        if (idx_key is not None and idx_key in seen_idx) or (ttl_key and ttl_key in seen_ttl):
            continue
        # 按 idx 从候选原样回填 url/source/ts:链接100%保真(模型从不经手)
        src_c = {}
        if idx_key is not None and 0 <= idx_key - 1 < len(pool):
            src_c = pool[idx_key - 1]
        url = (src_c.get("url") or "").strip()
        if url and url in seen_url:
            url_dups += 1
            continue
        if idx_key is not None:
            seen_idx.add(idx_key)
        if ttl_key:
            seen_ttl.add(ttl_key)
        if url:
            seen_url.add(url)
        items.append({"cat": cat, "title": it.get("title"), "brief": it.get("brief"),
                      "chain": it.get("chain"), "impact": it.get("impact"),
                      "source": src_c.get("source", ""), "url": url, "ts": src_c.get("ts", "")})
    return url_dups


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
    # 护栏②跨天压制:近7天已上过榜的原文不再进候选(空结果保护:全被压制时退回原池,宁可重复不可空版)
    recent = _recent_urls()
    n_suppressed = 0
    if recent:
        pool_fresh = [c for c in pool if (c.get("url") or "").strip() not in recent]
        if pool_fresh:
            n_suppressed = len(pool) - len(pool_fresh)
            pool = pool_fresh
            if n_suppressed:
                print(f"  🛡️ 跨天压制:{n_suppressed} 条近7天已上榜原文不进候选")
    lines = []
    for i, c in enumerate(pool):
        # 喂给模型的候选行不带URL(模型只回 idx,链接由代码按编号回填)——URL又长又占输出,曾把回答撑爆截断
        lines.append(f"{i+1}. [{c.get('source','')}|{c.get('ts','')}] {c.get('title','')} — {str(c.get('summary',''))[:100]}")
    result = ds_call(PROMPT + "\n".join(lines))
    if not result or not isinstance(result.get("items"), list) or not result["items"]:
        print("❌ DeepSeek 未返回有效头条,保留最近一期")
        return
    result["items"] = result["items"][:21]
    items, seen_idx, seen_ttl, seen_url = [], set(), set(), set()
    url_dups = _absorb(result, pool, items, seen_idx, seen_ttl, seen_url)
    # 护栏③事件簇 cap2(prompt 纪律⑩的代码强制层)
    items, dropped, _dbg = cluster_guard(items)
    for d in dropped:
        print(f"  🛡️ 事件簇超限裁撤[{d['cluster']}]({d['cat']}/imp{d['impact']}){d['title']}")
    # 护栏④回补:裁短不是目的,把版面让给其它真实事件才是
    backfilled = 0
    if dropped and len(items) < 15:
        label = dropped[0]["cluster"]
        capped_ents = set()
        for d in dropped:
            capped_ents |= set(str(d["cluster"]).split("/"))
        left = []
        for i, c in enumerate(pool):
            if (i + 1) in seen_idx:
                continue
            ce, _, _ = _txt_feats(str(c.get("title") or "") + " " + str(c.get("summary") or ""))
            if ce & capped_ents:
                continue                    # 同簇候选不再喂,防模型再选浪费一轮
            left.append((i, c))
        if left:
            supp_lines = []
            for i, c in left:
                supp_lines.append(f"{i+1}. [{c.get('source','')}|{c.get('ts','')}] {c.get('title','')} — {str(c.get('summary',''))[:100]}")
            need = min(16 - len(items), 8)
            kept_ttls = "；".join(str(x.get("title") or "") for x in items)
            supp_prompt = (PROMPT + "\n".join(supp_lines) +
                           f"\n\n【回补指令】此前所选头条中「{label}」事件簇超出硬上限2条,超出部分已被系统裁撤,现需回补版面。"
                           f"请从上面候选中再选最多 {need} 条,要求:与「{label}」事件簇无关、与下列已保留条目不是同一事件。"
                           f"已保留:{kept_ttls}。输出格式/字段/纪律同前,idx 沿用候选行开头编号,宁缺毋滥。")
            supp = ds_call(supp_prompt)
            if supp and isinstance(supp.get("items"), list) and supp["items"]:
                before = len(items)
                url_dups += _absorb(supp, pool, items, seen_idx, seen_ttl, seen_url)
                items, dropped2, _dbg2 = cluster_guard(items)   # 回补夹带同簇→再裁一遍
                for d in dropped2:
                    print(f"  🛡️ 回补夹带再裁[{d['cluster']}]{d['title']}")
                backfilled = max(0, len(items) - before)
                if backfilled:
                    print(f"  🛡️ 回补 {backfilled} 条其它主题")
    # 空结果绝不落盘——否则会顶掉最近一期有效头条、还被渲染层误标"今日"(审查已复现,与容错设计矛盾)
    if not items:
        print("❌ 筛编后 0 条有效头条,不落盘,保留最近一期")
        return
    out = {"asof": raw.get("asof", TODAY), "generated_by": "deepseek-chat",
           "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="minutes"),
           "guard": {"url_dups_dropped": url_dups,
                     "cross_day_suppressed": n_suppressed,
                     "cluster_label": (dropped[0]["cluster"] if dropped else ""),
                     "cluster_dropped": [str(d["title"] or "") for d in dropped],
                     "backfilled": backfilled},
           "items": items}
    path = os.path.join(STATE, f"news_{TODAY}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = lambda c: sum(1 for i in items if i["cat"] == c)
    print(f"✅ 头条 {len(items)} 条(宏观{n('macro')}/地缘{n('geo')}/石油{n('oil')}/天然气{n('gas')}/科技{n('tech')}/AI{n('ai')})→ {path}")
    if dropped or url_dups:
        print(f"🛡️ 护栏合计:同页URL去重{url_dups} · 事件簇裁撤{len(dropped)} · 回补{backfilled}")


if __name__ == "__main__":
    main()
