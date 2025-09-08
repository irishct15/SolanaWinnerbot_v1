# app/backtest/metrics.py
import csv, math

def load_trades(path):
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                r["pnl_pct"] = float(r.get("pnl_pct", 0) or 0)
                r["pnl_usd"] = float(r.get("pnl_usd", 0) or 0)
            except Exception:
                r["pnl_pct"] = 0.0
                r["pnl_usd"] = 0.0
            rows.append(r)
    return rows

def summarize(path):
    rows = load_trades(path)
    n = len(rows)
    if n == 0:
        return {"trades":0,"winrate":0.0,"avg_roi_pct":0.0,"expectancy_pct":0.0,"mdd_pct":0.0,"sharpe":0.0,
                "total_pnl_usd":0.0,"avg_pnl_usd":0.0}

    wins = sum(1 for r in rows if r["pnl_pct"]>0)
    winrate = wins*100.0/n
    avg_roi = sum(r["pnl_pct"] for r in rows)/n

    # expectancy = mean of ROI%
    expectancy = avg_roi

    # equity curve for MDD (%)
    eq = []
    c = 0.0
    for r in rows:
        c += r["pnl_pct"]
        eq.append(c)
    peak = -1e9
    draw = 0.0
    for v in eq:
        if v > peak: peak = v
        draw = max(draw, peak - v)
    mdd = draw

    # Sharpe (rough): mean / std of ROI% (assumes per-trade)
    vals = [r["pnl_pct"] for r in rows]
    mu = avg_roi
    var = sum((x-mu)**2 for x in vals)/n if n>0 else 0.0
    std = math.sqrt(var)
    sharpe = (mu/std) if std>1e-12 else 0.0

    total_pnl_usd = sum(r["pnl_usd"] for r in rows)
    avg_pnl_usd = total_pnl_usd / n

    return {
        "trades": n,
        "winrate": round(winrate, 2),
        "avg_roi_pct": round(avg_roi, 3),
        "expectancy_pct": round(expectancy, 3),
        "mdd_pct": round(mdd, 2),
        "sharpe": round(sharpe, 3),
        "total_pnl_usd": round(total_pnl_usd, 2),
        "avg_pnl_usd": round(avg_pnl_usd, 2),
    }

def pretty_print(path):
    s = summarize(path)
    name = path.replace("\\\\","/").split("/")[-1]
    print(f"=== Summary for {name} ===")
    print(f"trades         : {s['trades']}")
    print(f"winrate        : {s['winrate']}")
    print(f"avg_roi_pct    : {s['avg_roi_pct']}")
    print(f"expectancy_pct : {s['expectancy_pct']}")
    print(f"mdd_pct        : {s['mdd_pct']}")
    print(f"sharpe         : {s['sharpe']}")
    print(f"total_pnl_usd  : {s['total_pnl_usd']}")
    print(f"avg_pnl_usd    : {s['avg_pnl_usd']}")
