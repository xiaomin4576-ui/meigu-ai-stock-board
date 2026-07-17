#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门户注入:① __MACRO_STRIP__ → 最新宏观快线一行(公开数据:金/油/美10Y/CPI,过期标注日期);
② __SRC_N__ → 同光信源池真值(读 $TG_ROOT/sources.json 的 _meta.totalSources;读不到降级为不带数字的文案)。
取不到数据则清空/降级占位符,绝不留占位符上线。CI 在同光镜像(/tmp/tg)就位后调用(home 随后加密)。
(独立成脚本而非 workflow 内 heredoc:YAML 块里的 heredoc Python 必带缩进 → IndentationError,已知坑。)"""
import os, json, glob, re, sys, datetime

TARGET = sys.argv[1] if len(sys.argv) > 1 else "docs/home.html"
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
strip = ""
fs = [f for f in sorted(glob.glob("state/macro_*.json")) if re.search(r"macro_\d{4}-\d{2}-\d{2}\.json$", f)]
if fs:
    try:
        mj = json.load(open(fs[-1], encoding="utf-8"))
        b = mj.get("blocks", {})
        bits = []
        # 联邦基金利率放最前(进站一眼看利率环境;成长股估值锚)
        fed = b.get("美联储政策", {})
        if "error" not in fed and fed.get("EFFR%") is not None:
            bits.append(f"联邦基金 <b>{fed['EFFR%']}%</b>")
        c = b.get("大宗实时", {})
        for name, lbl in (("纽约黄金", "金"), ("纽约原油", "油"), ("美天然气", "气")):
            v = c.get(name) if "error" not in c else None
            if v:
                bits.append(f"{lbl} <b>{v['价']}</b>")
        r = b.get("中美利率", {})
        if "error" not in r and r.get("美10Y%"):
            bits.append(f"美10Y <b>{r['美10Y%']}%</b>")
        us = b.get("美国宏观", {})
        v = us.get("CPI同比%") if "error" not in us else None
        if v:
            # 审计F23:CPI 自带约两月发布滞后(7月中页面上是5月数据),门户不标月份读者会误当上月——
            # 补数据月份(与头条页 build_news 的逐格"期"标注同口径),缺"期"则不加括注
            per = f"<span style='font-size:10px'>({v.get('期')})</span>" if v.get("期") else ""
            bits.append(f"CPI同比 <b>{v['值']}%</b>{per}")
        if bits:
            # 审计F12:board/news 的宏观条过期都标日期,门户此前不标——同口径补齐,复用旧数据不许伪装新鲜
            asof = mj.get("asof")
            stale_note = f"(数据 {asof})" if (asof and asof != TODAY) else ""
            strip = "📅 " + " · ".join(bits) + stale_note + " <span style='font-size:10px'>(纽约联储 / BLS / 中债美债 / 腾讯外盘)</span>"
    except Exception:
        pass
# 信源池数动态化(审计F12):去硬编码 181,读 sources.json 真值;读不到绝不谎报数字
src_label = "全球信源聚合"
try:
    tg_root = os.environ.get("TG_ROOT") or "/tmp/tg"
    _n = (json.load(open(os.path.join(tg_root, "sources.json"), encoding="utf-8")).get("_meta") or {}).get("totalSources")
    if _n:
        src_label = f"{_n} 信源池"
except Exception:
    pass
# 股票池标的数动态化(审计F24):去硬编码"19 只核心标的",读 config.json 剔基准算真值;读不到降级为不带数字文案
ticker_label = "核心标的"
try:
    _cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
    _bench = _cfg.get("benchmark")
    _n2 = len([s for s in _cfg.get("stocks", []) if s.get("ticker") != _bench])
    if _n2:
        ticker_label = f"{_n2} 只核心标的"
except Exception:
    pass
h = (open(TARGET, encoding="utf-8").read()
     .replace("__MACRO_STRIP__", strip).replace("__SRC_N__", src_label).replace("__TICKER_N__", ticker_label))
open(TARGET, "w", encoding="utf-8").write(h)
print("门户注入:", ("宏观已注入" if strip else "宏观本期无数据已清空"), "·", f"信源标签={src_label}", "·", f"标的标签={ticker_label}")
