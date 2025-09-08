import os, sys, yaml, argparse, importlib, importlib.util, inspect, traceback

SAFE_CANDIDATES = [
    ("app.backtest.engine","run_backtest"),
    ("app.backtest.engine","run"),
    ("app.backtest.core","run_backtest"),
    ("app.backtest.core","run"),
    ("app.backtest.backtest","run_backtest"),
    ("app.backtest.backtest","run"),
    ("app.backtest.runner_impl","run_backtest"),  # current stub
]

def find_entry():
    for mod, fn in SAFE_CANDIDATES:
        try:
            if importlib.util.find_spec(mod) is None:
                continue
            m = importlib.import_module(mod)
            f = getattr(m, fn, None)
            if callable(f):
                return f, f"{mod}:{fn}"
        except Exception:
            continue
    raise RuntimeError("No engine found. Pass --entry module:function")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c","--config", required=True)
    ap.add_argument("-o","--out")
    ap.add_argument("--entry")
    args = ap.parse_args()

    with open(args.config,"r",encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    out_csv = args.out or cfg.get("trade_log_csv") or "artifacts/trades.auto.csv"
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    cfg["trade_log_csv"] = out_csv

    if args.entry:
        mod, fn = args.entry.split(":",1)
        fn_obj = getattr(importlib.import_module(mod), fn)
        tag = args.entry
    else:
        fn_obj, tag = find_entry()

    try:
        sig = inspect.signature(fn_obj)
        if len(sig.parameters)==0:
            fn_obj()
        elif len(sig.parameters)==1:
            fn_obj(cfg)
        else:
            try: fn_obj(cfg=cfg)
            except TypeError: fn_obj()
    except SystemExit:
        raise RuntimeError("Engine tried to parse argv; point to a non-CLI function.")
    except Exception:
        traceback.print_exc()
        raise
    print("[entry]", tag)
    print("[wrote]", out_csv)

if __name__ == "__main__":
    main()
