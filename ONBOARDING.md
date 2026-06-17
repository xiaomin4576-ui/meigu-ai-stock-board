# 🚀 两步上线闭环清单(照着点完即彻底自动)

> 现状:**数据/看板/部署/飞书** 每天 08:07 已云端全自动(不依赖你开机)。还差**每日自动研判**这一环——只需下面两步账号级操作(我替不了)。全程约 5 分钟。

---

## ✅ 第 1 步:授权 Claude GitHub App 访问新仓(约 1 分钟)

让云端 Claude 能读写你的仓库。

1. 打开 👉 https://github.com/settings/installations
2. 在已安装列表里点 **Claude**(Anthropic 的 App)→ 右侧 **Configure**
3. 找到 **Repository access**:
   - 若选的是「**Only select repositories**」→ 点 **Select repositories** → 搜 `meigu-ai-stock-board` → 勾选 → 拉到底 **Save**
   - 若选的是「**All repositories**」→ 已自动包含,**跳过**即可
4. **自检**:Configure 页的 Repository access 列表里能看到 `meigu-ai-stock-board` ✅

---

## ✅ 第 2 步:在 claude.ai 建每日研判 Routine(约 3 分钟)

1. 登录 👉 https://claude.ai
2. 找 **Routines / Automations** 入口(若没看到:头像 → **Settings** 里找 Routines / Scheduled tasks 开关并开启)→ **New Routine**
3. **连接仓库**:选 `xiaomin4576-ui/meigu-ai-stock-board`,分支 `main`
   - ⚠️ 列表里搜不到这个仓 → 回**第 1 步**没授权好
4. **设触发时间**:每天 **北京 07:30**
   - 界面若用 UTC → 填 **23:30**(对应次日北京 07:30);或把时区切到 **Asia/Shanghai** 再填 07:30
   - ⚠️ 必须早于 08:07(那是 Actions 的 cron,先有新研判、Actions 再用最新研判重建)
5. **粘贴指令**:打开同目录的 [`ROUTINE_PROMPT.md`](ROUTINE_PROMPT.md),把里面 ``` 代码块整段复制进 Routine 的 Prompt 框(无需改任何占位符)
6. **Save** → 点 **Run now** 手动试跑一次

### 第 2 步做完的自检(Run now 后逐条核对)
1. **Routine 日志**里能看到:`git pull` → `pip install` → `python3 fetch_data.py` → 写 `calls_<日期>.json` → `git push`
2. **GitHub Actions** 被 push 触发并跑绿 👉 https://github.com/xiaomin4576-ui/meigu-ai-stock-board/actions
3. **飞书群**收到一张「📡 美股AI科技股早报」卡片
4. 打开**线上看板** 👉 https://xiaomin4576-ui.github.io/meigu-ai-stock-board/ → 顶部新鲜度横幅变 🟢「研判为今日」

---

## 🎯 两步做完后会发生什么

- **每天北京 07:30**:云端 Claude 自动研判 → push;**08:07**:Actions 自动重建看板 + 部署 Pages + 推飞书。**你电脑关机也照常跑。**
- **跑满 5 个交易日**:看板「🔍 复盘与校准」区会从"积累中"变成**真实的量化校准系数**(买入价/目标价"越用越准"从承诺态变实测态)。
- 想临时手动刷一期:在 Claude 里说 **「刷新云端美股看板」**,我立刻研判一期推上去。

---

## 🆘 排错速查

| 症状 | 原因 / 解法 |
|---|---|
| Routine 里搜不到仓库 | 回第 1 步,把 `meigu-ai-stock-board` 加进 Claude GitHub App |
| Actions 没被触发 | 确认 Routine 真的 `git push` 到了 `main`(看 Routine 日志) |
| 飞书没收到卡片 | 仓库 Settings → Secrets → Actions 确认有 `FEISHU_WEBHOOK`(已配,一般无需动) |
| 看板顶部一直橙色「行情数据降级」 | yfinance 当天被 Yahoo 限流(数据中心 IP 常见),已诚实复用最近真实行情;次日通常自动恢复 |
| 看板顶部橙色「研判 N 天前」 | 当天 Routine 没成功跑 → 看 Routine 日志排错,或在 Claude 说「刷新云端美股看板」手动补 |

---

> ⚠️ 仅供研究/学习,非投资建议。命中率现实约 50-65%(回测 42%,绝非 90%),正期望靠风控不靠高胜率。
