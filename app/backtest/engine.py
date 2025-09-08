# app/backtest/engine.py
import csv, os, json, hashlib, random
from typing import Dict, Any, Iterable

def _pick(cfg: Dict[str, Any], key: str, *layers, default=None):
    # Look in params, then backtest, then sim, then top-level
    for d in layers:
        if isinstance(d, dict) and key in d:
            return d[key]
    return default

def _iter_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                # tolerate occasional junk lines
                continue

def _seed_for(pair: str, ts: str) -> int:
    h = hashlib.sha256(f"{pair}|{ts}".encode("utf-8")).hexdigest()
    return int(h[:16], 16)  # deterministic across runs/processes

def run_backtest(cfg: Dict[str, Any] | None = None) -> int:
    """Minimal deterministic backtest:
       - Reads events JSONL (pair, t, price required; side optional)
       - For each event: simulate up to max_bars with bounded returns
       - TP/SL, optional breakeven, fees + slippage in bps (round trip)
       - Writes CSV to cfg['trade_log_csv']
    """
    cfg = cfg or {}
    ds  = cfg.get("dataset", {}) or {}
    params   = cfg.get("params", {}) or {}
    backtest = cfg.get("backtest", {}) or {}
    sim      = cfg.get("sim", {}) or {}
    risk     = cfg.get("risk", {}) or {}

    out_csv = cfg.get("trade_log_csv") or "artifacts/trades.engine.csv"
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)

    events_path = ds.get("events_jsonl")
    if not events_path or not os.path.exists(events_path):
        raise FileNotFoundError(f"events_jsonl not found: {events_path!r}")

    # knobs
    tp_mult        = _pick(cfg, "tp_mult", params, backtest, default=1.02)  # 2% TP by default
    sl_pct         = _pick(cfg, "sl_pct", params, backtest, default=0.02)   # 2% SL
    max_bars       = int(_pick(cfg, "max_bars", params, backtest, default=12))
    be_arm_frac    = float(_pick(cfg, "be_arm_frac", params, sim, default=0.0))
    fee_bps        = int(risk.get("fee_bps", 0))
    slippage_bps   = int(sim.get("slippage_bps", 0))

    # simple, bounded “vol” model (deterministic per event)
    vol_pct = 0.015  # ±1.5% step range

    rows = []
    for ev in _iter_jsonl(events_path):
        pair = str(ev.get("pair", "UNKNOWN/USDC"))
        ts   = str(ev.get("t", ""))
        try:
            entry_px = float(ev.get("price", 1.0))
        except Exception:
            entry_px = 1.0

        if entry_px <= 0:
            entry_px = 1.0

        # seed RNG for deterministic path per event
        rng = random.Random(_seed_for(pair, ts))

        tp = entry_px * float(tp_mult)
        sl = entry_px * (1.0 - float(sl_pct))
        be_active = False

        price = entry_px
        bars_held = 0
        exit_kind = "timeout"

        for i in range(1, max_bars + 1):
            # bounded uniform step in ±vol_pct
            step = (rng.random() * 2.0 - 1.0) * vol_pct
            price *= (1.0 + step)
            bars_held = i

            # arm breakeven when price moves enough in favor
            if not be_active and be_arm_frac and price >= entry_px * (1.0 + be_arm_frac):
                be_active = True
                sl = entry_px  # move stop to breakeven

            if price >= tp:
                exit_kind = "tp"
                break
            if price <= sl:
                exit_kind = "sl"
                break

        exit_px = price

        # Apply simple round-trip costs (entry + exit)
        rt_cost = 2.0 * (fee_bps + slippage_bps) / 10_000.0  # convert bps to fraction
        pnl_frac = (exit_px / entry_px) - 1.0 - rt_cost
        pnl_pct  = pnl_frac * 100.0

        rows.append({
            "pair": pair,
            "entry_ts": ts,
            "exit_ts": ts,  # synthetic; you can later compute real timestamps using ticks
            "entry_px": round(entry_px, 8),
            "exit_px": round(exit_px, 8),
            "pnl_pct": round(pnl_pct, 4),
            "exit": exit_kind,
            "bars_held": bars_held,
            "fees_bps": fee_bps,
            "slip_bps": slippage_bps,
            "tp_mult": tp_mult,
            "sl_pct": sl_pct,
            "be_arm_frac": be_arm_frac,
            "max_bars": max_bars,
        })

    # Write CSV
    if not rows:
        # still write a header so downstream tools don't crash
        rows = [{
            "pair":"N/A","entry_ts":"","exit_ts":"","entry_px":0,"exit_px":0,
            "pnl_pct":0,"exit":"none","bars_held":0,"fees_bps":fee_bps,
            "slip_bps":slippage_bps,"tp_mult":tp_mult,"sl_pct":sl_pct,
            "be_arm_frac":be_arm_frac,"max_bars":max_bars
        }]

    fieldnames = list(rows[0].keys())
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    return 0
