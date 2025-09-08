# tools/run_cfg.py  (minimal; points at runner_impl)
import os, yaml, argparse, importlib

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c","--config", required=True)
    ap.add_argument("-o","--out", required=True)
    args = ap.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    cfg["trade_log_csv"] = args.out

    mod = importlib.import_module("app.backtest.runner_impl")
    fn  = getattr(mod, "run_backtest")
    print("[entry] app.backtest.runner_impl:run_backtest")
    fn(cfg)
    print("[wrote]", args.out)

if __name__ == "__main__":
    main()
