#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 落账:把 Claude 当期研判(state/calls_<date>.json)+ 真实现价(state/data_<date>.json)
写入预测台账 state/predictions.jsonl。台账是复盘与校准的依据。
幂等口径(2026-07-11 体检后改为【替换式】):同日重跑研判时,该日全部行按最新 calls 重写——
此前"跳过式"幂等在 07-09 双跑时把台账留在旧版,与看板 4/19 票信号错位(高危)。"""
import json, os, re, datetime

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
LEDGER = os.path.join(STATE, "predictions.jsonl")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()  # 北京时间


def rng(s):
    nums = re.findall(r"\d+(?:\.\d+)?", s or "")
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if len(nums) == 1:
        return float(nums[0]), float(nums[0])
    return None, None


def main():
    cfg = json.load(open(os.path.join(DIR, "config.json"), encoding="utf-8"))
    calls = json.load(open(os.path.join(STATE, f"calls_{TODAY}.json"), encoding="utf-8"))
    data = json.load(open(os.path.join(STATE, f"data_{TODAY}.json"), encoding="utf-8"))["stocks"]
    # 读入既有台账,剔除"今天"的旧行(同日重跑=看板被新研判覆盖,台账必须跟着换,保证账板一致)
    kept, replaced = [], 0
    if os.path.exists(LEDGER):
        for ln in open(LEDGER, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
                if r.get("date") == TODAY:
                    replaced += 1
                    continue
            except Exception:
                pass
            kept.append(ln)
    eval_date = (datetime.date.fromisoformat(TODAY) + datetime.timedelta(days=cfg["horizon_days"])).isoformat()
    n = 0
    for tk, a in calls["stocks"].items():
        bl, bh = rng(a.get("buy")); tl, th = rng(a.get("tgt"))
        kept.append(json.dumps({
            "date": TODAY, "ticker": tk,
            "price_at_call": data.get(tk, {}).get("price"),
            "signal": a.get("sig"), "buy_low": bl, "buy_high": bh,
            "target_low": tl, "target_high": th, "exp_return": a.get("ret"),
            "eval_date": eval_date,
        }, ensure_ascii=False))
        n += 1
    with open(LEDGER, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")
    print(f"✅ 台账写入 {n} 条(date={TODAY},到期复盘 {eval_date}"
          + (f";替换同日旧行 {replaced} 条,账板一致" if replaced else "") + ")")


if __name__ == "__main__":
    main()
