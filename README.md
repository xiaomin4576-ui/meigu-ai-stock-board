# 美股 AI 科技股早报 · 混合云端架构(meigu-ai-stock-board)

以**华尔街二级市场交易员 + buy-side 分析师**视角,**长期 6-12 个月**跟踪美股 AI 产业链上下游核心 **10 票 + QQQ 基准**(英伟达 NVDA、博通 AVGO、台积电 TSM、超微 AMD、美光 MU、迈威尔 MRVL、Arista ANET、Credo CRDO、相干 COHR、Vertiv VRT + QQQ),每支给两个核心指标:① 买入建议(买入/观望/回避 + 建议买入价)② 6-12 月目标价 + 预期收益。内置「预测台账 → 自动复盘 → 校准」闭环。

> ⚠️ **仅供研究/学习,非投资建议。** 价格全部来自 yfinance 真实抓取;目标价为技术面 + 券商一致 + 催化剂推演,不代表未来。回测命中率约 42%(**绝非 90%**),正期望靠 ~2.5:1 盈亏比——**赚钱靠风控不靠高胜率**。实际交易请自负风险。

---

## 🚀 上线前必做清单(按顺序,缺一不可)

1. **首推必须带真实种子**:`state/` 下首推必须包含 `calls_<日期>.json`、`data_<日期>.json`、`verification.json`、`backtest.json`、`predictions.jsonl` 以及对应的 `ai_stock_board_<日期>.html`。否则 `build_board.py` 因缺 calls 直接 `SystemExit`,首次 Actions 构建会红、Pages 永远空白。
2. **Settings → Pages → Source 选「GitHub Actions」**(建仓后第一件事人工点),否则 `deploy-pages` 报 Not Found。
3. **配 repo secret `FEISHU_WEBHOOK`**(Settings → Secrets and variables → Actions → New repository secret)。未配则飞书 job 静默跳过,不报错。
4. **(可选,要研判每日新鲜)** 在 claude.ai 建 Routine(北京 07:30)并把本仓加进 Claude GitHub App 可访问列表。

---

## 一、混合云端架构(为什么这么设计)

本系统把「**数据/看板/部署**」与「**Claude 研判**」拆成两条云端轨道,**完全不依赖用户本机开机**:

- **轨道 B/C(GitHub Actions,纯自动,不需用户在场):** 每天 cron(北京 08:07,美股盘后)无人值守地——拉最新真实行情、跑复盘校准、渲染看板与归档、组织进 `docs/`、部署 Pages、推飞书。**用户电脑关机也照常更新。**
- **轨道 A(Claude 研判,云端 Routine):** 买入价/目标价/信号这类**需要判断力**的研判由 **Claude 本人**做(不调 DeepSeek)。claude.ai Routine 每天云端 pull→跑数据→按策略框架研判→写 `calls_<日期>.json`→push;push 又触发轨道 B/C。

> ⚠️ **重要事实**:headless `claude -p` 在 Actions/cron 子进程拿不到令牌(401),所以**新鲜研判只能靠 claude.ai Routine**,不能靠 Actions。若某天 Routine 没跑,`build_board.py` 的 `latest_calls()` 会**复用最近一期研判**,看板顶部显示**研判新鲜度横幅**(🟢同日 / 🟠过期 N 天),诚实标注,不拿旧研判冒充新研判。

---

## 二、目录结构(仓库根布局)

```
meigu-ai-stock-board/
├── README.md
├── requirements.txt              yfinance / pandas / requests
├── .gitignore                    排除 cron.log / __pycache__ / 任何 webhook|secret 文件
├── config.json                   股票池(11 支)+ horizon/阈值
├── fetch_data.py                 ① yfinance 拉行情+券商一致+财报日+新闻(CI 容错版)
├── verify.py                     ④ 复盘校准 → state/verification.json
├── log_today.py                  ③ 研判落台账 → state/predictions.jsonl(幂等)
├── build_board.py                ⑤ 渲染看板 → state/ai_stock_board_<日期>.html(latest_calls 复用 + freshness_banner)
├── build_archive.py              ⑥ 归档 → state/index.html
├── backtest.py                   ⑦ 3 年回测 → state/backtest.json(手动/低频跑,不进每日 cron)
├── .github/workflows/
│   └── daily-board.yml           轨道 B+C:fetch→verify→build→archive→组织 docs→部署 Pages→飞书
├── state/                        产物/数据(由 Routine + Actions 共同写入,入库累积以支撑复盘)
│   ├── data_<日期>.json
│   ├── calls_<日期>.json         ★研判核心
│   ├── predictions.jsonl         预测台账(逐日累积,幂等)
│   ├── verification.json
│   ├── backtest.json
│   └── ai_stock_board_<日期>.html / index.html(归档)
└── docs/                         GitHub Pages 发布目录(workflow 每次重建,不入库)
    └── .nojekyll                 (workflow 运行时再生成 index.html / archive.html / 各期副本)
```

> **日期一律北京时间**:脚本里 `datetime.now(timezone(timedelta(hours=8))).date()`。

### docs/ 怎么从 state/ 组织出来

workflow 跑完脚本后:`state/ai_stock_board_*.html` 全部拷进 `docs/` → 最新一期复制为 `docs/index.html`(落地页)→ `state/index.html` 复制为 `docs/archive.html` → 生成 `docs/.nojekyll` → 在**落地页**顶部 `<div class="wrap">` 后注入「📚 历史归档」入口(只改 docs 副本,不动 state 原文件、不动 archive.html)。归档页用相对链接 `ai_stock_board_<日期>.html`,故这些文件必须与 archive.html 同目录。

---

## 三、维护

- **改股票池**:编辑 `config.json` 的 `stocks` 数组(QQQ 固定作基准)。改完 push,下次 Routine + Actions 自动按新池跑。
- **改运行时间**:Actions cron 在 `daily-board.yml` 的 `schedule`(用 UTC,北京 08:07 = `7 0 * * *`);Claude Routine 在 claude.ai 改,建议北京 07:30(早于 cron)。
- **改周期/阈值**:`config.json` 的 `horizon_days` / `target_aggressive_pct` / `min_periods_for_calibration`。
- **飞书 webhook**:只配为 repo secret `FEISHU_WEBHOOK`,**代码里永不出现明文**。
- **回测刷新**:`backtest.py` 较重(拉 3 年数据),不进每日 cron,手动或每周单独跑一次刷新 `state/backtest.json`。

---

## 四、免责声明

本项目**仅供研究与学习**,**不构成任何投资建议、要约或承诺**。所有价格、券商一致目标价、财报日、新闻均由 `yfinance` **真实抓取**,系统**绝不编造价格**。买入价/目标价/预期收益是 Claude 基于公开数据 + 公认策略思想的推演,**不代表未来**。历史回测命中率约 **42%**(**绝非 90%**),正期望来自约 2.5:1 盈亏比纪律——**赚钱靠风控不靠高胜率**。据此操作产生的任何盈亏由使用者自行承担。投资有风险,入市需谨慎。
