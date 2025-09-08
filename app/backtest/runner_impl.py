# app/backtest/runner_impl.py
import csv, os, time

def run_backtest(cfg=None):
    cfg = cfg or {}
    out = cfg.get("trade_log_csv", "artifacts/trades.stub.csv")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    rows = [
        {"pair":"TEST/USDC","entry_px":1.00,"exit_px":1.03,"pnl_pct":3.0,"exit":"tp"},
        {"pair":"TEST/USDC","entry_px":1.02,"exit_px":0.99,"pnl_pct":-2.94,"exit":"sl"},
    ]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    time.sleep(0.1)
    return 0
