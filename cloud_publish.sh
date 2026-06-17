#!/bin/bash
# 云端手动刷新「发布」环节:落台账 → 提交 → 推送(触发云端 Actions 重建+部署 Pages+飞书)。
# 前提:Claude 已写好 state/calls_<北京日期>.json。用法:bash cloud_publish.sh
set -e
cd "$(dirname "$0")"
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
[ -x "$PY" ] || PY=python3
BJ=$($PY -c "import datetime;print(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date())")
if [ ! -f "state/calls_${BJ}.json" ]; then
  echo "❌ 缺 state/calls_${BJ}.json —— Claude 还没写本期研判,中止"; exit 1
fi
echo "① 落台账…"; $PY log_today.py
echo "② 提交并推送 main(触发云端 Actions)…"
TOKEN=$(printf "host=github.com\nprotocol=https\n\n" | git credential-osxkeychain get 2>/dev/null | grep '^password=' | cut -d= -f2)
git add state/
if git diff --cached --quiet; then echo "(state 无变化,跳过)"; exit 0; fi
git commit -q -m "chore: 美股 AI 早报研判 ${BJ}(本地手动刷新)"
git push -q "https://xiaomin4576-ui:${TOKEN}@github.com/xiaomin4576-ui/meigu-ai-stock-board.git" HEAD:main
echo "✅ 已推送。云端 GitHub Actions 将自动:重建看板 → 部署 Pages → 推飞书。"
echo "   线上看板:https://xiaomin4576-ui.github.io/meigu-ai-stock-board/"
