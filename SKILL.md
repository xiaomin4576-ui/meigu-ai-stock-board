---
name: ai-stock-board
description: 美股 AI 科技股早报。以二级市场交易员/buy-side 视角,长期(6-12月)跟踪「美股 AI 产业链上下游核心十票 + QQQ」(英伟达、博通、台积电、超微、美光、迈威尔、Arista、Credo、相干、Vertiv + QQQ),每支给两个核心指标:①买入建议(买入/观望/回避+建议买入价)②6-12月目标价+预期收益。内置"预测台账→自动复盘→校准"闭环,让买入价/目标价越用越准。引擎是 Claude 本人(不用 DeepSeek),数据用 yfinance 真实行情。当用户说"跑美股AI早报/AI股票早报/科技股早报/英伟达们今天怎么看/ai-stock-board"或需要定时盯这组票时使用(本地出看板)。另:说"刷新云端美股看板/把美股早报推到线上/跑美股AI早报云端版/更新线上美股看板"时,走【云端手动刷新】——Claude 亲自研判一期并 push 到云端仓库,触发线上 Pages 重建+飞书推送。
---

# 美股 AI 科技股早报(ai-stock-board)

以**华尔街二级市场交易员 + buy-side 分析师**视角,**长期 6-12 个月**跟踪美股 AI 产业链上下游核心标的,给可执行的买点与目标价,并自带验证-校准闭环。

## 核心定位
- **引擎 = Claude(本人)**。研判(买入建议、买入价、目标价、预期收益)由 Claude 亲自做,**不调 DeepSeek/vibe-trading 的 LLM**。
- **数据全部真实抓取(yfinance,绝不编造)**,四层:① 行情/技术(价格/动量/MA/52周)② **券商分析师一致数据**(一致目标价 targetMean、评级 recommendationKey、覆盖家数、前瞻PE)——机构共识锚 ③ **下次财报日期** ④ **实时新闻催化剂(带来源链接)**——同光式信源层,补 Claude 知识盲区。
- **时间框架**:长期 **6-12 个月**(目标价、预期收益都按此周期)。
- **两个核心指标**(每支必给,具体数字):
  1. **买入建议** = 买入 / 观望 / 回避 + **建议买入价**(区间)
  2. **买入后预期价格** = **6-12月目标价**(区间) + **预期收益%**(买入价中值→目标价中值)
- **股票池**:AI 产业链上下游核心 10 票 + **QQQ 基准**(见 `config.json`)。**前十随大市场动态变化**——每次跑时 Claude 评估是否按市值/AI相关度/热度换标的,改 `config.json` 的 `stocks` 即可。
- ⚠️ **仅研究/学习用途,非投资建议**;目标价为技术面+板块结构推演,并对标券商一致校准。

## 策略框架(研判依据,明确写清)
研判**不基于任何单一机构的私有模型**,而是几类公认策略思想的融合,且**用真实机构数据 + 催化剂背书**:
1. **趋势跟踪**:价格相对 MA50/MA200 判多空(全在 200 日线上=趋势完好)。
2. **动量**:近 1/3/6 月涨幅;过热(抛物线、远离均线)则降级为"观望"。
3. **均值回归 / 回调买入**:买点优先给"回踩支撑"而非追高;超买不追。
4. **板块相对强弱**:组内谁回调更到位 / 性价比更好,排前。
5. **风险收益比 + 仓位纪律**:买入 / 观望 / 回避三档。
6. **机构共识校准(关键)**:目标价**对标 yfinance 的券商一致目标价(targetMean)**——我的目标显著高于共识须标注"偏乐观"、显著低于则上调;若**共识目标价已 ≤ 现价**(街上无上行空间),个股一律降级观望。
7. **催化剂锚定**:结合**当前**财报日 / 评级变动 / 行业新闻(带来源链接)判断,不靠 Claude 旧知识。
8. **风险收益比 + 止损纪律(真 edge,审稿人最看重)**:每支给止损/失效位(默认 -10% 或破关键均线),算 R:R=(目标-入场)/(入场-止损);**买入须 R:R≥2**,否则降级/标黄。看板每卡显示。
9. **透明多因子评分(0-100)**:趋势+共识上行+回调健康+动量(惩罚过热)+券商评级 加权,信号由分数+R:R推导、可复现(看板显示评分明细)——回答"基于什么算的"。
10. **历史回测背书(`backtest.py`,用证据代替承诺)**:真实 3 年数据测核心规则,给真实命中率/盈亏比(当前 ~42% / 2.5:1,**绝非 90%**),并诚实标注牛市/幸存者偏差。
11. **市场体制**:QQQ vs MA200 + 成分宽度 → 顺势/中性/逆风,据此调整预期。

> **诚实底线(写死,不许违反)**:方向命中率现实约 50-65%(回测 42% 已被牛市美化),**正期望靠 R:R 不靠高胜率;绝不承诺 90% 或"比专业更准"**;复盘记分卡持续如实记录真实表现。

## 信息完整度与诚实化规则(2026-06 顶尖专家自检确立,写死不许违反)

**总原则**:目标价/预期收益/评分的质量 = 喂给它的信息完整度。**凡是能影响定价的信息(券商共识、催化剂新闻、盈利预期、财报日、解禁…)一个都不能放过;信息缺失时一律如实标注,绝不静默补分或编造。**

1. **禁止"幽灵共识"(最高约束)**:当 `data` 里某支 `analyst.target_mean` 为 null、或来自非当日的 stale 值时,研判文本 `th` **禁止**出现任何"券商一致 \$X / X家 / 某投行上调 / 具体财报日"字样,只能写"券商一致暂缺"。目标价**只能对标当日真实存在的 data 字段**,不靠旧记忆、不引用 data 里不存在的数字。
2. **评分诚实化**:`factor_score` 对**数据缺失的因子标"不可计算"(记入 miss),绝不静默计 0 / 白送保底分混入排序**。卡片显示"评分 X(N/5因子)";当 ≥3 个因子不可算 → 显示"**数据不足·暂不评分**",目标价标"题材推演非可复算估值"(亏损/次新/无锚港股如壁仞)。
3. **覆盖如实披露**:数据审计区按真实覆盖率显示;券商一致覆盖偏低时标"**目标价未经共识校准**",不得假称"已用 X 顶上"。
4. **各市场数据源**:美股 = Twelve Data 价格/技术(云端稳,需 secret TD_API_KEY)+ yfinance 尽力补券商一致/新闻/财报日;A股 = akshare(行情+东财评级+研报覆盖数+前瞻PE+新闻 + 业绩预约财报日 `stock_yysj_em`,禁代理直连);港股 = yfinance/akshare(常受限,best-effort)。云端受限 → 逐支回退复用本地推的真值,stale 如实标。
5. **财报临近度**:距下次财报 <10–15 天 → 降置信、卡片标"⚠️ 财报临近·二元风险",不在财报前给追高买点。
6. **R:R≥2 硬纪律**:给"买入"信号的标的必须 R:R≥2,否则降级观望。
7. **可复现**:目标价应可被复算(注明锚定的当日数字 + 估值方法)。

### 待补强因子 roadmap(逐步接入评分,均属"影响定价不可放过"):
- **A股 EPS 派生目标价**:akshare 研报含 2026/27/28 三年 EPS 预测+行业 → 目标价 = 前瞻EPS × 板块合理PE(共识缺失时唯一可复现的估值桥);A股"共识上行"按此与美股同口径,恢复"隐含目标≤现价→降级观望"量化闸。
- **盈利预期修正**(近1月 vs 近3月 EPS 预测中位之差,buy-side 最强 alpha 之一)。
- **相对强弱**(个股−QQQ/板块,SKILL 第4条要求但未实现)、**质量**(ROE/毛利/现金流)、**估值分位**(PE 历史/同业百分位,解决寒武纪PE130 vs 中天PE10.6 失真)、**波动率**(高波动扣分)、**A股解禁**(`stock_restricted_release_queue_em`)、**评级/目标价变动事件**。
- **评分模型重构**:现5因子里价格动量重复计3遍(趋势+回调+动量=52)、独立维度仅2个;重构为≤6个低相关大类、组内分位标准化后加权。
- **云端共识根治**:接 Finnhub/FMP 免费档(price-target + recommendation + earnings,云端 IP 可达、非 Yahoo 黑名单)补回美股共识/财报日,需 1 个免费 key。

## 文件结构
```
~/.claude/skills/ai-stock-board/
├── SKILL.md            本文件
├── config.json         股票池 / 周期 / 阈值(可改)
├── fetch_data.py       ① 数据层:yfinance 拉真实行情 → state/data_<date>.json
├── verify.py           ④ 验证+校准:读台账+真实价 → state/verification.json
├── log_today.py        ③ 落账:Claude 研判 → state/predictions.jsonl
├── build_board.py      ⑤ 渲染:含置信度徽章+机构共识+催化剂链接+数据审计区
├── build_archive.py    ⑥ 历史归档:阅读库式索引 + 复盘记分卡 → state/index.html
├── backtest.py         ⑦ 历史回测(定期跑,如每周):真实3年数据测规则 → state/backtest.json
└── state/
    ├── data_<date>.json         当日真实行情(行情+券商一致+财报日+新闻)
    ├── calls_<date>.json        当日 Claude 研判(★由 Claude 生成,含 conf 置信度)
    ├── predictions.jsonl        预测台账(复盘依据,逐日累积)
    ├── verification.json        复盘+校准结果
    ├── ai_stock_board_<date>.html  当日看板
    └── index.html               历史归档看板(翻历史+复盘记分卡)
```

> **web 信源层(item 待 web 工具恢复启用)**:理想流程里 Step 3 前 Claude 应对每支跑 `web_search` 抓更深的近期催化剂 + 分析师评级变动事件(带来源链接)。当前 web_search/web_fetch 工具不可用,暂用 yfinance 的真实新闻+券商一致+财报日顶上(已覆盖"有据可依、带链接、不靠旧记忆"的核心);web 工具恢复后在 Step 3 加 web_search 即可深化。

## 用户手动触发时怎么做(按顺序)
当用户要"跑美股AI早报/今天这组票怎么看"等:

1. **拉数据**:`python3 ~/.claude/skills/ai-stock-board/fetch_data.py`(yfinance 真实行情)。
2. **跑验证**:`python3 ~/.claude/skills/ai-stock-board/verify.py`(对历史台账复盘 + 对上期做即时可达性校验,产出记分卡与**校准建议**)。
3. **Claude 亲自研判**(核心):读 `state/data_<date>.json`(含行情+**券商一致数据**+财报日+**新闻催化剂**)+ `state/verification.json`,按上面【策略框架】对每支给出 `sig/buy/tgt/ret/th/rk`。硬性要求:
   - **目标价对标 data 里的 `analyst.target_mean` 校准**:显著偏离须在 `th` 标注(如"我高于共识X%"/"街上一致已≤现价→降级观望")。
   - **`th` 必须引用当前催化剂**(data 的 `news`/`earnings_date`),不靠旧知识;过往复盘校准建议也纳入。
   - 评估前十是否按市值/热度换标的(改 `config.json`)。
   把结果写成 `state/calls_<date>.json`(schema 见下)。
4. **落台账**:`python3 .../log_today.py`(把当期研判+现价记入 predictions.jsonl,幂等)。
5. **渲染**:`python3 .../build_board.py`(看板含置信度徽章+🏛机构共识+我vs共识+财报日+📰催化剂链接+数据审计区)→ `python3 .../build_archive.py`(更新历史归档 index.html)。
6. **呈现**:用 `show_widget` 或浏览器把看板给用户看,口述 Top 排序 + 每支两指标 + 复盘校准要点;**务必附"仅研究示范、非投资建议"**。
7. **(可选)推飞书**:复用 morning-board 的 webhook(`~/.vibe-trading/feishu_webhook.txt`)。

### calls_<date>.json schema(Claude 输出)
```json
{
  "asof": "YYYY-MM-DD",
  "market": "一段大盘与板块判断(可含 <b> 高亮)",
  "ranking": ["AVGO","NVDA", ...],   // 按买点吸引力从高到低
  "stocks": {
    "NVDA": {"sig":"买入/观望/回避","conf":9,"buy":"195–208","tgt":"265–300","ret":"+40%",
             "th":"一句话买入逻辑(须引用催化剂+对标共识)","rk":"一句话主要风险"}
    // conf=置信度 0-10(数据/共识支撑强度);th 须引用 data 的催化剂、对标 analyst.target_mean
  }
}
```

## 验证 + 优化闭环(本 skill 的灵魂)
- **验证**:① 即时可达性——用真实近 20 日成交区间核对"建议买入价"是否挂得上、目标隐含涨幅是否过激(>阈值标黄);② 历史复盘——对台账里旧预测算 买入区间触及率 / 方向胜率 / 目标完成度% / 到期实际收益vs预测。
- **优化**:Claude 出新建议前读记分卡校准买入价/目标价;满 `min_periods_for_calibration` 期后给量化校准系数。看板「🔍 复盘与校准」板块展示。

## 每日自动(已上线·混合架构)
**关键现实**:本机 headless `claude -p` 在本环境**无法认证**(认证令牌是宿主进程托管、会自动刷新的短期令牌,新起的 `claude` 子进程拿不到有效凭证 → `401 Invalid bearer token`,launchd 干净环境与带完整环境都一样)。所以"定时让 Claude 当引擎跑研判"在本地物理上跑不通。故采用**混合方案**:

- **每日自动(已上线)**:launchd 任务 `com.xiaomin.ai-stock-board` 每天**本机 17:00 PDT ≈ 北京 08:00** 跑 `run_daily.sh`(**纯 Python,无需认证**):① fetch_data 拉真实行情/券商一致/财报/新闻 → ② verify 复盘校准 → ③ build_board 渲染看板(**自动复用最近一期 Claude 研判**,顶部显示「研判新鲜度」横幅)→ ④ build_archive 归档。日志 `state/cron.log`。
- **研判按需刷新**:买入价/目标价由 **Claude 本人**做。需要最新研判时,在 Claude 里说「跑美股AI早报」,Claude 走完整 6 步重写 `calls_<date>.json`。看板会自动从橙色「研判 X 天前」变回绿色「今日研判」。
- **改时间**:编辑 plist 的 `Hour` 后 `launchctl bootout gui/$(id -u) <plist>` 再 `bootstrap`。
- **要真·每天自动 Claude 研判** → 升级到 **云端 Routine**(像同光那样:把脚本进 GitHub 仓 + Actions 跑 yfinance + claude.ai 建 Routine 每天云端研判推飞书/上 Pages),不依赖本机、绕开本地认证限制。需用户在 claude.ai 建 Routine(账号级操作)。

## 云端手动刷新(说"刷新云端美股看板/把美股早报推到线上"时走这里)
云端版仓库 `xiaomin4576-ui/meigu-ai-stock-board`,本地构建副本在 `~/Desktop/meigu-ai-stock-board-routine/`,线上看板 `https://xiaomin4576-ui.github.io/meigu-ai-stock-board/`。云端每天 08:07 自动刷新「数据+看板+部署+飞书」,但**研判**要么靠用户的 claude.ai Routine,要么靠这里手动。当用户要"在这儿跑一期推到线上",按顺序:
1. **准备**:`bash ~/Desktop/meigu-ai-stock-board-routine/cloud_prep.sh` —— 它会 `git pull`(拉最新含 Routine 已推研判)→ `fetch_data.py` 抓真实行情 → `verify.py` 复盘。
2. **Claude 亲自研判**:读 `~/Desktop/meigu-ai-stock-board-routine/state/data_<北京日期>.json` + `verification.json`,按上面【策略框架】研判 11 支,写 `~/Desktop/meigu-ai-stock-board-routine/state/calls_<北京日期>.json`(schema 同上:asof/market/ranking/stocks{sig,conf,buy,tgt,ret,th,rk};对标 analyst.target_mean、引用催化剂、买入须 R:R≥2)。**价格全部来自 cloud_prep 抓取的真实数据,绝不编造。**
3. **发布**:`bash ~/Desktop/meigu-ai-stock-board-routine/cloud_publish.sh` —— 它会 `log_today.py` 落台账 → commit → push main(用 keychain 令牌),**触发云端 Actions 自动重建看板+部署 Pages+推飞书**。
4. 跑完用一句话报告:线上 URL + 本期买点 Top3。**附"仅研究示范、非投资建议"**。
> 与本地版区别:本地版出 `~/.claude/skills/ai-stock-board/state/` 的看板(只在本机);云端手动刷新出的是**线上 Pages + 飞书**(操作的是 `~/Desktop/meigu-ai-stock-board-routine/`)。两套 state 独立,互不串。

## 依赖
- `yfinance`(已装,免 token,只拉真实行情)。
- Claude 本人做研判(本 skill 不需要 DeepSeek/vibe-trading)。
- 飞书推送(可选):`~/.vibe-trading/feishu_webhook.txt`。

## 维护
- 改股票池/动态换标的 → 编辑 `config.json` 的 `stocks`。
- 改持仓周期/激进阈值/校准期数 → 改 `config.json` 的 `horizon_*` / `target_aggressive_pct` / `min_periods_for_calibration`。
- 区别于 `morning-board`(A股/港股四票·2月·DeepSeek 引擎):本 skill 是**美股 AI 十票·长期·Claude 引擎·带复盘校准**。
