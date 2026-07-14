#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门户宏观条注入:把 __MACRO_STRIP__ 占位符替换为最新宏观快线一行(公开数据:金/油/美10Y/CPI)。
取不到数据则清空占位符,绝不留占位符上线。CI 在 cp portal.html → docs/home.html 后调用(home 随后加密,由光之门 index.html 解密直出)。
(独立成脚本而非 workflow 内 heredoc:YAML 块里的 heredoc Python 必带缩进 → IndentationError,已知坑。)"""
import json, glob, re, sys

TARGET = sys.argv[1] if len(sys.argv) > 1 else "docs/home.html"
strip = ""
fs = [f for f in sorted(glob.glob("state/macro_*.json")) if re.search(r"macro_\d{4}-\d{2}-\d{2}\.json$", f)]
if fs:
    try:
        b = json.load(open(fs[-1], encoding="utf-8")).get("blocks", {})
        bits = []
        c = b.get("大宗实时", {})
        for name, lbl in (("纽约黄金", "金"), ("纽约原油", "油")):
            v = c.get(name) if "error" not in c else None
            if v:
                bits.append(f"{lbl} <b>{v['价']}</b>")
        r = b.get("中美利率", {})
        if "error" not in r and r.get("美10Y%"):
            bits.append(f"美10Y <b>{r['美10Y%']}%</b>")
        us = b.get("美国宏观", {})
        v = us.get("CPI同比%") if "error" not in us else None
        if v:
            bits.append(f"CPI同比 <b>{v['值']}%</b>")
        if bits:
            strip = "📅 " + " · ".join(bits) + " <span style='font-size:10px'>(BLS / 中债美债 / 腾讯外盘)</span>"
    except Exception:
        pass
h = open(TARGET, encoding="utf-8").read().replace("__MACRO_STRIP__", strip)
open(TARGET, "w", encoding="utf-8").write(h)
print("门户宏观条:", "已注入" if strip else "本期无数据,已清空占位")
