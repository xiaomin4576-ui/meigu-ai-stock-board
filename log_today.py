#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 落账:把 Claude 当期研判(state/calls_<date>.json)+ 真实现价(state/data_<date>.json)
写入预测台账 state/predictions.jsonl(幂等:同一天只记一次)。台账是复盘与校准的依据。"""
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
    existing = set()
    if os.path.exists(LEDGER):
        for ln in open(LEDGER, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    r = json.loads(ln); existing.add((r["date"], r["ticker"]))
                except Exception:
                    pass
    eval_date = (datetime.date.fromisoformat(TODAY) + datetime.timedelta(days=cfg["horizon_days"])).isoformat()
    n = 0
    with open(LEDGER, "a", encoding="utf-8") as f:
        for tk, a in calls["stocks"].items():
            if (TODAY, tk) in existing:
                continue
            bl, bh = rng(a.get("buy")); tl, th = rng(a.get("tgt"))
            f.write(json.dumps({
                "date": TODAY, "ticker": tk,
                "price_at_call": data.get(tk, {}).get("price"),
                "signal": a.get("sig"), "buy_low": bl, "buy_high": bh,
                "target_low": tl, "target_high": th, "exp_return": a.get("ret"),
                "eval_date": eval_date,
            }, ensure_ascii=False) + "\n")
            n += 1
    print(f"✅ 台账写入 {n} 条(date={TODAY},到期复盘 {eval_date})")


if __name__ == "__main__":
    main()
