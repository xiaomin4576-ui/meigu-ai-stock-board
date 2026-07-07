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
2. **评分诚实化**:`factor_score` 对**数据缺失的因子标"不可计算"(记入 miss),绝不静默计 0 / 白送保底分混入排序**。卡片显示"评分 X(N/9因子)";当 ≥3 个因子不可算 → 显示"**数据不足·暂不评分**",目标价标"题材推演非可复算估值"(亏损/次新/无 EPS 估值锚的标的)。
3. **覆盖如实披露**:数据审计区按真实覆盖率显示;券商一致覆盖偏低时标"**目标价未经共识校准**",不得假称"已用 X 顶上"。
4. **各市场数据源**:美股 = Twelve Data 价格/技术(云端稳,需 secret TD_API_KEY)+ yfinance 尽力补券商一致/新闻/财报日;A股 = akshare(行情+东财评级+研报覆盖数+前瞻PE+新闻 + 业绩预约财报日 `stock_yysj_em`,禁代理直连);港股 = yfinance/akshare(常受限,best-effort)。云端受限 → 逐支回退复用本地推的真值,stale 如实标。
5. **财报临近度**:距下次财报 <10–15 天 → 降置信、卡片标"⚠️ 财报临近·二元风险",不在财报前给追高买点。
6. **R:R≥2 硬纪律**:给"买入"信号的标的必须 R:R≥2,否则降级观望。
7. **可复现**:目标价应可被复算(注明锚定的当日数字 + 估值方法)。

### 评分模型现状(2026-06 顶尖专家自检后升级到 9 因子)
**9 因子归一化加权**(`factor_score`,`FACTOR_W`):趋势16 + 共识上行18 + 回调健康10 + 动量10 + 评级10 + **估值PEG18** + **相对强弱10** + **波动率8** + **质量12**。各因子打 0-1 × 权重,**缺失因子不计入、按 present 权重重标到 /100**(`miss` 记录不可算因子;故绝对权重和不影响最终分)。卡片显示 `评分 N(cov/9因子)`。
- **估值PEG**=前瞻PE÷EPS增速(A股有 EPS 预测可算;PEG 低=好,正确区分寒武纪 vs 中天泡沫)。
- **相对强弱**=个股 m3 − QQQ m3(`main` 把 `bench_m3` 传入 `factor_score`);跑赢大盘=强。如 NVDA 落后 QQQ 得低分。
- **波动率**=年化日波动(`ann_vol`,已抓日线可算);低=好。次新/抛物线高波动(迈威尔159%/美光124%)被扣分,QQQ31% 得高分。
- **质量**=ROE + 经营现金流符号 + 毛利率(`cn_quality`,A股东财 `stock_financial_analysis_indicator`);**烧钱的次新股如实下调**——纳芯微(ROE负+现金流负)质量仅 2/12、寒武纪(ROE7.9+现金流正)质量 11/12。
- **美股共识(Finnhub)**=`us_finnhub`(env 设 `FINNHUB_KEY` 才启用):评级趋势(recommendation)→ rating_mean + 买入占比作"共识上行"代理(免费档无目标价)、财报日历(calendar/earnings)、财务指标(metric:roeTTM/grossMarginTTM/peTTM/epsGrowthTTMYoy)→ 质量+估值PEG。**配 key 后美股从技术分 5/9 升到完整 9/9**;卡片显示"🏛 分析师共识(Finnhub)"。不配 key 则 `us_finnhub` 返回 {},完全维持现状不影响。
- 基本面因子(共识/评级/估值PEG)全缺 → 卡片标"**技术分·仅技术面**"(美股**未配 Finnhub key** 时的现状);可算因子 ≤3 → "**数据不足·暂不评分**"。

**风险哨兵(不进评分、作卡片二元风险标记,避免扭曲跨市场归一化)**:
- **财报临近**<14 天 → ⚠️ 二元风险不宜追高。
- **A股限售解禁**(`cn_unlock_map`,东财 `stock_restricted_release_detail_em` 全市场未来6月)→ 🔓 标解禁日/占流通%/抛压临近(占流通≥3% 或 ≤60天加重);无解禁则标"已消除限售抛压隐忧"。

### 待补强因子 roadmap:
- ✅ 已做:A股 EPS+正确前瞻PE+估值PEG + 相对强弱 + 波动率 + 质量(ROE/现金流/毛利)+ 财报临近⚠️ + A股解禁哨兵 + 归一化模型 + 数据不足"暂不评分"。
- **盈利预期修正**(近1月 vs 近3月 EPS 预测中位之差,buy-side 最强 alpha;需逐日累积 EPS 快照,从现在起累积)。
- ✅ **云端共识(Finnhub)已接入代码**(`us_finnhub`):recommendation(评级)+ calendar/earnings(财报日)+ metric(ROE/毛利/PE/EPS增速)。**待用户操作**:① finnhub.io 注册拿免费 key ② 本地 env 加 `FINNHUB_KEY=xxx`、云端 `gh secret set FINNHUB_KEY`(workflow 的 fetch 步骤已可加该 env)③ 重抓 → 美股自动升到 9/9 完整评分。免费档**无 price-target(目标价)**,用评级趋势+财务指标校准(已用 mock 验证解析/9因子/渲染全通)。

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

## 盘势问答(云端专属,2026-07-07 上线)
看板页内「🤖 盘势问答」面板:输密码(8888)后可直接向看板提问(如"这波下跌何时可能扭转")。
- **架构**:纯前端直连 DeepSeek(api.deepseek.com 已实测允许 andy4576.com 浏览器 CORS,流式回答秒级出字,零后端)。
- **语料**:① 页内嵌 `QACTX`(本期 19 票真实行情+研判+复盘记分卡,build_board.py 的 `qa_ctx()` 构建)② 按需同源拉 `/tongguang/data/index.json` 取同光早报要闻(Top5/Tier0/质量≥8,最多24条,带「这意味着」洞察)。
- **凭证防泄露**:`__QA_KEY__` 占位符,与 `__DISPATCH_TOKEN__` 同模式;workflow 6c 步只在 `DEEPSEEK_API_KEY` 与 `BOARD_PASSWORD` 同时存在时注入(密文页专属),加密后还有"凭证明文泄露即中止"双保险检查(用 if grep -q 形式避免 set -e 误杀)。源码/state 只含占位符。
- **诚实纪律(写进 system prompt)**:只基于喂入语料回答、缺的直说"语料未覆盖"、"何时回转"必须转成【条件+信号+三情景时间量级】而非预测、末尾固定"仅研究示范,非投资建议"。
- **多轮**:保留最近 3 轮问答上下文;Enter 发送。本地预览版无凭证时面板显示"未配置"。

## 全球市场头条 + 运营看板(2026-07-07 上线)
**全球头条**(news.html,锁8888):三档 15-21 条(🌍宏观/地缘 5-7 + 🛢️石油/能源 5-7(莫桑比克联合能源Union视角:事件→油价/LNG→东非经营;信源加OilPrice/CNBC Energy) + 🤖科技/AI 5-7),每条带「事件→美股→A股」传导链。
- 管线:`fetch_news.py`(Finnhub general + 东财环球快讯(禁代理+60s守护线程限时) + 财经RSS,html.unescape+标题去重,0条不覆盖真值)→ `research_news_ds.py`(DeepSeek json_mode 筛编;cat别名兼容、url白名单兜底、空结果不落盘)→ `build_news.py`(渲染;新鲜度以内容asof为准;esc转义含引号)。CI 每天自动跑(与个股研判不同——头条不需手动触发)。
- 头条自动进「盘势问答」第三路语料(build_board.qa_ctx 嵌最新12条)。
**运营看板**(ops.html,锁8888):`build_ops.py` 构建时统计——看板数据资产/覆盖率/台账/归档、同光语料(TG_DIR=镜像目录)、Actions最近50次健康度(GITHUB_TOKEN)、DeepSeek消耗(state/usage.jsonl,research_ds+research_news_ds 双双落账)与余额。**state/ops.html 已 .gitignore(含余额,只进 docs 加密版,绝不入公开仓——审查抓的中危)**。诚实披露区写明做不了的:访问量(GoatCounter暂缓)/Claude token/问答全站汇总。
**门户四卡**:同光早报(公开)/股票看板🔒/全球头条🔒/运营看板🔒。

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
