#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组合层风险度量(2026-07 指标审计第一批·金融教授关切):
本股票池【有意】100% 聚焦 AI 科技口(算力/存储/光互联/国产替代),是【单一主题集中押注】而非分散组合。
本脚本不去掉集中度,而是【如实量化并暴露】它——把"齐涨齐跌"的系统性风险算成数字摆上台面:
  · 两两收益相关性矩阵(过去约1年日收益)+ 平均相关(整体/美股簇内/A港簇内/跨市)
  · 分散化比率 DR = Σwᵢσᵢ / σ_portfolio(≈1 表示几乎无分散,越大分散越有效)
  · 等权组合年化波动 / 相对 QQQ 的 beta / 区间最大回撤
  · AI 子段集中度(算力/存储/光互联/…)
数据:yfinance 批量历史(相关性慢变,非实时,失败则【保留上期不覆盖】,绝不落空)。
输出:state/portfolio_risk.json,供 build_board 渲染"组合层风险面板"+注入研判 prompt。
"""
import os, sys, json, glob, datetime, warnings
warnings.filterwarnings("ignore")

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
OUT = os.path.join(STATE, "portfolio_risk.json")

# AI 产业链子段(用于集中度披露;分段只为看清"钱压在哪几段",非精确行业分类)
SEGMENTS = {
    "算力芯片(GPU/代工/AI芯)": ["NVDA", "TSM", "AVGO", "MRVL", "688981.SS", "688256.SS", "688052.SS"],
    "存储": ["MU", "001309.SZ", "603986.SS"],
    "光互联(光模块/AEC/光纤)": ["CRDO", "COHR", "600522.SS", "6869.HK"],
    "网络/交换": ["ANET"],
    "硬件配套(电源散热/PCB/显示)": ["VRT", "002384.SZ", "300005.SZ"],
    "AI应用/需求侧": ["0700.HK"],
}


def _load_cfg():
    return json.load(open(os.path.join(os.path.dirname(OUT), "..", "config.json"), encoding="utf-8"))


def _yf_symbol(tk):
    # config 的 A股用 .SS/.SZ、港股 .HK,yfinance 同格式直接可用
    return tk


def main():
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
    bench = cfg.get("benchmark", "QQQ")
    tickers = [s["ticker"] for s in cfg["stocks"]]
    names = {s["ticker"]: s["name"] for s in cfg["stocks"]}
    core = [t for t in tickers if t != bench]   # 剔基准

    try:
        import yfinance as yf
        import pandas as pd
        raw = yf.download([_yf_symbol(t) for t in tickers], period="1y", interval="1d",
                          progress=False, auto_adjust=True)["Close"]
        if raw is None or len(raw) < 60:
            raise RuntimeError("历史行数不足")
        # 只保留成功取到、非空天数足够的票(honest:取不到的如实剔除,不编)
        good = [t for t in tickers if t in raw.columns and int(raw[t].notna().sum()) >= 120]
        rets = raw[good].pct_change().dropna(how="all")
        common = rets.dropna()                 # 全票共同交易日(跨市相关口径统一)
        if len(common) < 60:
            raise RuntimeError(f"共同交易日不足({len(common)})")
        corr = common.corr()

        core_good = [t for t in core if t in good]
        us = [t for t in core_good if t.endswith(("", )) and not t.endswith((".SS", ".SZ", ".HK"))]
        cnhk = [t for t in core_good if t.endswith((".SS", ".SZ", ".HK"))]

        def avg_pair(cols_a, cols_b=None):
            vals = []
            if cols_b is None:  # 组内两两
                for i in range(len(cols_a)):
                    for j in range(i + 1, len(cols_a)):
                        vals.append(float(corr.loc[cols_a[i], cols_a[j]]))
            else:               # 跨组
                for a in cols_a:
                    for b in cols_b:
                        vals.append(float(corr.loc[a, b]))
            return round(sum(vals) / len(vals), 2) if vals else None

        # —— 组合层指标(等权,剔基准)——
        port = common[core_good].mean(axis=1)          # 等权组合日收益
        ann = (252 ** 0.5)
        port_vol = round(float(port.std()) * ann * 100, 1)
        indiv_vol = {t: float(common[t].std()) * ann for t in core_good}
        w = 1.0 / len(core_good)
        wavg_vol = sum(w * indiv_vol[t] for t in core_good)
        div_ratio = round(wavg_vol / (float(port.std()) * ann), 2) if port.std() else None  # DR≥1;≈1=无分散
        # beta vs 基准
        beta = None
        if bench in common.columns:
            b = common[bench]
            var_b = float(b.var())
            beta = round(float(port.cov(b)) / var_b, 2) if var_b else None
        # 等权组合区间最大回撤
        cum = (1 + port).cumprod()
        mdd = round(float((cum / cum.cummax() - 1).min()) * 100, 1)

        # 集中度(等权下按子段份额 + Herfindahl)
        seg_share = {}
        for seg, mem in SEGMENTS.items():
            n = len([t for t in core_good if t in mem])
            if n:
                seg_share[seg] = round(n / len(core_good) * 100, 1)
        hhi = round(sum((v / 100) ** 2 for v in seg_share.values()), 3)   # 越高越集中

        # 每票 vs 组合其余 的平均相关(看谁最"随大流"、谁能提供一点分散)
        each_vs_book = {}
        for t in core_good:
            others = [x for x in core_good if x != t]
            each_vs_book[t] = round(sum(float(corr.loc[t, o]) for o in others) / len(others), 2) if others else None

        # 精简相关矩阵(2位小数)供热力图
        mat = {a: {b: round(float(corr.loc[a, b]), 2) for b in core_good} for a in core_good}

        result = {
            "asof": TODAY,
            "window_days": int(len(common)),
            "included": core_good,
            "excluded": [t for t in core if t not in core_good],
            "names": {t: names.get(t, t) for t in core_good},
            "avg_corr_overall": avg_pair(core_good),
            "avg_corr_us": avg_pair(us) if len(us) > 1 else None,
            "avg_corr_cnhk": avg_pair(cnhk) if len(cnhk) > 1 else None,
            "avg_corr_cross": avg_pair(us, cnhk) if (us and cnhk) else None,
            "diversification_ratio": div_ratio,
            "portfolio_vol_ann_pct": port_vol,
            "portfolio_beta_vs_bench": beta,
            "portfolio_max_drawdown_pct": mdd,
            "segment_share_pct": seg_share,
            "hhi": hhi,
            "each_vs_book_corr": each_vs_book,
            "matrix": mat,
            "note": "过去约1年日收益·等权·剔基准QQQ;跨市相关按全票共同交易日算,时段差异使跨市相关天然偏低。集中是本池【有意】的AI科技口押注,此处只做量化暴露不做分散。",
        }
    except Exception as e:
        # 取数失败:绝不落空覆盖上期(规则9)。有上期就保留,无则写降级标记。
        prev = None
        if os.path.exists(OUT):
            try:
                prev = json.load(open(OUT, encoding="utf-8"))
            except Exception:
                prev = None
        if prev and prev.get("matrix"):
            print(f"⚠️ portfolio_risk 取数失败({repr(e)[:80]}),保留上期 {prev.get('asof')} 不覆盖")
            return
        result = {"asof": TODAY, "degraded": True, "error": repr(e)[:120],
                  "note": "本期组合风险数据取数失败,面板将如实显示不可用"}
        print(f"⚠️ portfolio_risk 取数失败且无上期:{repr(e)[:80]}")

    os.makedirs(STATE, exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not result.get("degraded"):
        print(f"✅ portfolio_risk 写入:{len(result['included'])}票·共同{result['window_days']}日·"
              f"平均相关{result['avg_corr_overall']}(美{result.get('avg_corr_us')}/A港{result.get('avg_corr_cnhk')}/跨市{result.get('avg_corr_cross')})·"
              f"分散比{result['diversification_ratio']}·组合波动{result['portfolio_vol_ann_pct']}%·beta{result['portfolio_beta_vs_bench']}·回撤{result['portfolio_max_drawdown_pct']}%")


if __name__ == "__main__":
    main()
