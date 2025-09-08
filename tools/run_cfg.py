# tools/run_cfg.py
import os, yaml, argparse, importlib

CANDIDATES = [
    ("app.backtest.engine", "run_backtest"),
    ("app.backtest.runner_impl", "run_backtest"),
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c","--config", required=True)
    ap.add_argument("-o","--out")
    ap.add_argument("--entry")
    args = ap.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    out = args.out or cfg.get("trade_log_csv") or "artifacts/trades.auto.csv"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    cfg["trade_log_csv"] = out

    tag = None
    if args.entry:
        mod_name, fn_name = args.entry.split(":", 1)
        mod = importlib.import_module(mod_name)
        fn  = getattr(mod, fn_name)
        tag = args.entry
    else:
        fn = None
        for mod_name, fn_name in CANDIDATES:
            try:
                mod = importlib.import_module(mod_name)
                fn  = getattr(mod, fn_name)
                tag = f"{mod_name}:{fn_name}"
                break
            except Exception:
                continue
        if fn is None:
            raise RuntimeError("No suitable engine found. Pass --entry module:function")

    fn(cfg)
    print("[entry]", tag)
    print("[wrote]", out)

if __name__ == "__main__":
    main()
