#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宏观快线采集:为看板/头条/问答补「宏观数据+跨资产」层。
来源蒸馏自「艾丽的无废话财经」研判框架 gap 分析(2026-07):她的核心信息优势=宏观数据三点对照
(实际/预期/前值)+ 跨资产资金流观察,而我们底座此前只有个股行情/共识/新闻,缺宏观层——本脚本补齐。
【源选型(全部实测,按数据真实性规则)】
  ① 美国宏观 = BLS 官方 API(labor.gov 一手,免key;非农就业/失业率/CPI)——弃用了 akshare 金十镜像(已停更于2025-09)。
     注:市场"预期值"无免费可靠源,如实缺,只给 实际+前值+同比,不编。
  ② 中美国债收益率 = akshare bond_zh_u_rate(中债/美债官方口径,日频)。
  ③ 黄金/原油实时 = 腾讯外盘 hf_GC/hf_CL(免key)。
  ④ 中国社融 = akshare macro_china_shrzgm(金十镜像,常滞后1-2月,页面如实标注数据月份)。
逐项容错:任一源失败该项置空并留 error,绝不编造;输出 state/macro_<北京日期>.json。"""
import os, json, ssl, datetime, urllib.request

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def with_no_proxy(fn):
    keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
    saved = {k: os.environ.pop(k) for k in keys if k in os.environ}
    old_no = os.environ.get("NO_PROXY")
    os.environ["NO_PROXY"] = "*"
    try:
        return fn()
    finally:
        os.environ.pop("NO_PROXY", None)
        if old_no is not None:
            os.environ["NO_PROXY"] = old_no
        os.environ.update(saved)


def us_bls():
    """BLS 官方:非农就业(算环比新增)、失业率、CPI(算同比)。v1 免key,限额宽裕(日6跑够用)。"""
    yr = datetime.date.today().year
    body = json.dumps({"seriesid": ["CES0000000001", "LNS14000000", "CUSR0000SA0"],
                       "startyear": str(yr - 1), "endyear": str(yr)}).encode()
    req = urllib.request.Request("https://api.bls.gov/publicAPI/v1/timeseries/data/", data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": "macro-fetcher"})
    with urllib.request.urlopen(req, timeout=30, context=_ctx()) as r:
        d = json.loads(r.read())
    if d.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(str(d.get("message"))[:100])
    out = {}
    for s in d["Results"]["series"]:
        rows = [x for x in s["data"] if x.get("period", "").startswith("M")]
        rows.sort(key=lambda x: (x["year"], x["period"]), reverse=True)
        sid = s["seriesID"]
        if not rows:
            continue
        cur = rows[0]
        label = f"{cur['year']}-{cur['period'][1:]}"
        if sid == "CES0000000001" and len(rows) >= 2:
            add = int(float(cur["value"]) - float(rows[1]["value"]))
            prev_add = int(float(rows[1]["value"]) - float(rows[2]["value"])) if len(rows) >= 3 else None
            out["非农新增(千人)"] = {"值": add, "前值": prev_add, "期": label}
        elif sid == "LNS14000000":
            out["失业率%"] = {"值": float(cur["value"]),
                            "前值": float(rows[1]["value"]) if len(rows) >= 2 else None, "期": label}
        elif sid == "CUSR0000SA0" and len(rows) >= 13:
            yoy = round((float(cur["value"]) / float(rows[12]["value"]) - 1) * 100, 1)
            prev_yoy = round((float(rows[1]["value"]) / float(rows[13]["value"]) - 1) * 100, 1) if len(rows) >= 14 else None
            out["CPI同比%"] = {"值": yoy, "前值": prev_yoy, "期": label}
    out["源"] = "BLS官方(实际/前值;市场预期无免费可靠源,如实缺)"
    return out


def bond_rates():
    """中美10Y国债收益率与利差(中债/美债官方口径,akshare 日频)。"""
    import akshare as ak
    start = (datetime.date.today() - datetime.timedelta(days=20)).strftime("%Y%m%d")
    df = with_no_proxy(lambda: ak.bond_zh_us_rate(start_date=start))
    row = df.dropna(subset=["美国国债收益率10年"]).iloc[-1]
    return {"美10Y%": float(row["美国国债收益率10年"]), "中10Y%": float(row["中国国债收益率10年"]),
            "利差bp": round((float(row["美国国债收益率10年"]) - float(row["中国国债收益率10年"])) * 100),
            "日期": str(row["日期"]), "源": "中债/美债官方口径"}


def commodities():
    """黄金/原油/天然气实时(腾讯外盘,免key)。2026-07 加天然气 Henry Hub(hf_NG)——能源档/莫桑LNG视角。"""
    req = urllib.request.Request("https://qt.gtimg.cn/q=hf_GC,hf_CL,hf_NG",
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15, context=_ctx()) as r:
        txt = r.read().decode("gbk", "ignore")
    out = {}
    sym = {"hf_GC": "纽约黄金", "hf_CL": "纽约原油", "hf_NG": "美天然气"}
    for line in txt.split(";"):
        for code, name in sym.items():
            if code in line and "=" in line:
                f = line.split('"')[1].split(",")
                out[name] = {"价": float(f[0]), "涨跌%": float(f[1]), "时间": f[6] + " " + f[12]}
    if not out:
        raise RuntimeError("腾讯外盘无数据")
    out["源"] = "腾讯外盘实时(金/油/气)"
    return out


# 2026 年 FOMC 议息会议【决议日】(美联储预定日历,公开且提前一年公布,稳定;含"距下次约N天"作二元风险提示)
FOMC_2026 = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
             "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-16"]


def usa_fed():
    """美联储政策利率 = 纽约联储 EFFR(有效联邦基金利率,官方口径、免key、日更)+ 下次 FOMC 倒计时。
    利率是成长股(AI科技)估值的贴现率之锚,直接影响 PE 倍数——研判必须看它,而非只看市场端的10Y。"""
    req = urllib.request.Request("https://markets.newyorkfed.org/api/rates/unsecured/effr/last/2.json",
                                 headers={"User-Agent": "macro-fetcher"})
    with urllib.request.urlopen(req, timeout=20, context=_ctx()) as r:
        d = json.loads(r.read())
    rows = d.get("refRates", [])
    if not rows:
        raise RuntimeError("NY Fed EFFR 无数据")
    cur = rows[0]
    prev = rows[1] if len(rows) > 1 else {}
    out = {"EFFR%": cur.get("percentRate"), "前值%": prev.get("percentRate"),
           "日期": cur.get("effectiveDate"), "源": "纽约联储官方(EFFR,免key日更)"}
    # 下次 FOMC 决议倒计时(<14 天 → 二元风险不宜追高,与财报日同类哨兵)
    today = datetime.date.fromisoformat(TODAY)
    fut = [datetime.date.fromisoformat(x) for x in FOMC_2026 if datetime.date.fromisoformat(x) >= today]
    if fut:
        out["下次FOMC"] = fut[0].isoformat()
        out["距FOMC天"] = (fut[0] - today).days
    return out


def caixin_pmi():
    """财新制造业PMI(akshare index_pmi_man_cx,活源,月更)——统计局官方PMI的金十镜像已冻结于2025-08,
    故用财新(独立民间调查,更覆盖中小/出口企业,50荣枯线)作中国制造周期领先指标。禁代理直连。"""
    import akshare as ak
    df = with_no_proxy(lambda: ak.index_pmi_man_cx())
    df = df.dropna(subset=["制造业PMI"])
    if len(df) == 0:
        raise RuntimeError("财新PMI无数据")
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else {}
    val = float(last["制造业PMI"])
    pv = float(prev["制造业PMI"]) if len(df) >= 2 else None
    return {"财新制造业PMI": round(val, 1), "前值": round(pv, 1) if pv is not None else None,
            "荣枯": "扩张" if val >= 50 else "收缩", "数据月份": str(last["日期"])[:7],
            "源": "财新/标普(民间调查,月更;统计局官方PMI金十源已冻结故改用财新)"}


def cn_shrz():
    """中国社融增量(金十镜像,常滞后1-2月——数据月份如实标注,绝不冒充最新)。"""
    import akshare as ak
    df = with_no_proxy(lambda: ak.macro_china_shrzgm())
    row = df.iloc[-1]
    return {"社融增量(亿)": int(row["社会融资规模增量"]), "其中人民币贷款(亿)": int(row["其中-人民币贷款"]),
            "数据月份": str(row["月份"]), "源": "央行口径·金十镜像(注意滞后)"}


def main():
    os.makedirs(STATE, exist_ok=True)
    out = {"asof": TODAY,
           "fetched_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="minutes"),
           "blocks": {}}
    # 2026-07 扩:美联储政策(EFFR+FOMC)、财新制造业PMI——补齐"利率锚+中国制造周期"两个研判维度
    srcs = [("美国宏观", us_bls), ("美联储政策", usa_fed), ("中美利率", bond_rates),
            ("大宗实时", commodities), ("中国制造业", caixin_pmi), ("中国社融", cn_shrz)]
    for name, fn in srcs:
        try:
            out["blocks"][name] = fn()
            print(f"  {name} ✓")
        except Exception as e:
            out["blocks"][name] = {"error": f"{repr(e)[:90]}"}
            print(f"  {name} ✗ {repr(e)[:80]}")
    ok = sum(1 for v in out["blocks"].values() if "error" not in v)
    path = os.path.join(STATE, f"macro_{TODAY}.json")
    # 诚实防护:全部失败时不落盘,渲染层自动复用最近一期(带日期)
    if ok == 0 and not os.path.exists(path):
        print("⚠️ 宏观快线全部失败,不落盘")
        return
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 宏观快线 {ok}/{len(srcs)} → {path}")


if __name__ == "__main__":
    main()
