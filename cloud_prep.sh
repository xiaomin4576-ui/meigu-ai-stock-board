#!/bin/bash
# 云端手动刷新「准备」环节:拉最新(含 Routine 的研判)→ 抓真实行情 → 复盘校准。
# 跑完后由 Claude 读 state/data_<北京日期>.json + verification.json 亲自研判,写 calls。
set -e
cd "$(dirname "$0")"
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
[ -x "$PY" ] || PY=python3
echo "① 拉取云端最新(含 Routine 可能已推的研判)…"
# data/verification 等会被本脚本重新生成,本地已跟踪改动可安全丢弃,确保 rebase pull 不被脏工作区卡住
git checkout -- . 2>/dev/null || true
git pull origin main --rebase 2>/dev/null || git pull origin main || echo "(pull 跳过)"
echo "② 抓真实行情/券商一致/财报/新闻…"
$PY fetch_data.py
echo "③ 复盘校准…"
$PY verify.py
BJ=$($PY -c "import datetime;print(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date())")
echo "✅ 准备完成。现在由 Claude 读 state/data_${BJ}.json + state/verification.json 研判,写 state/calls_${BJ}.json,再跑 cloud_publish.sh"
