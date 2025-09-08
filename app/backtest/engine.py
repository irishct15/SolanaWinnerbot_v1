# app/backtest/engine.py
import csv, json, os
from typing import List, Dict, Any, Tuple
from datetime import datetime

ISO = "%Y-%m-%dT%H:%M:%SZ"

def _rget(d, path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def _parse_iso(s: str) -> datetime:
    # accepts "...Z" or plain ISO
    s = s.strip()
    if s.endswith("Z"):
        return datetime.strptime(s, ISO)
    try:
        return datetime.fromisoformat(s.replace("Z",""))
    except Exception:
        return datetime.strptime(s, ISO)

def _load_events(path:str) -> List[Dict[str,Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln: continue
            try:
                j = json.loads(ln)
                out.append(j)
            except Exception:
                # tolerate bad lines
                continue
    out.sort(key=lambda r: r.get("t",""))
    return out

def _load_ticks_csv(path: str) -> List[Tuple[datetime, float]]:
    out = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            ts = r.get("ts") or r.get("time")
            px = r.get("price") or r.get("px")
            if ts is None or px is None: continue
            try:
                out.append((_parse_iso(ts), float(px)))
            except Exception:
                pass
    out.sort(key=lambda t: t[0])
    return out

def _find_entry_index(ticks: List[Tuple[datetime,float]], t_event: datetime) -> int:
    # first tick with ts >= event time
    lo, hi = 0, len(ticks)-1
    ans = len(ticks)
    while lo <= hi:
        mid = (lo+hi)//2
        if ticks[mid][0] >= t_event:
            ans = mid
            hi = mid-1
        else:
            lo = mid+1
    return ans if ans < len(ticks) else -1

def _sim_trade(
    ticks: List[Tuple[datetime,float]],
    i0: int,
    entry_ts: datetime,
    entry_px_obs: float,
    side: str,
    *,
    max_bars: int,
    tp_mult: float,
    sl_pct: float,
    trail_frac: float,
    late_after_frac: float,
    late_tp_frac: float,
    slippage_bps: float,
    base_size_usd: float,
    fee_bps: float,
) -> Dict[str,Any]:
    # Entry execution price w/ slippage (long only for now)
    m = slippage_bps/10000.0
    entry_exec = entry_px_obs * (1 + m)

    units = base_size_usd / entry_exec if entry_exec > 0 else 0.0

    tp_px   = entry_px_obs * tp_mult if tp_mult and tp_mult>0 else float("inf")
    sl_px   = entry_px_obs * (1 - sl_pct) if sl_pct and sl_pct>0 else -float("inf")

    high_water = entry_px_obs
    late_active = False

    exit_reason = "timeout"
    exit_idx = min(i0 + max_bars, len(ticks)-1)

    for i in range(i0, min(i0 + max_bars, len(ticks))):
        ts, px = ticks[i]
        if px <= 0: continue

        # track high watermark
        if px > high_water:
            high_water = px

        # activate late-tp once price moved late_after_frac over entry
        if not late_active and late_after_frac and high_water >= entry_px_obs*(1+late_after_frac):
            late_active = True

        # check exits (priority order)
        # 1) classic TP (close >= target)
        if px >= tp_px:
            exit_reason = "tp"
            exit_idx = i
            break

        # 2) late take-profit: if activated and drawdown from high >= late_tp_frac
        if late_active and late_tp_frac and high_water>0 and (high_water - px)/high_water >= late_tp_frac:
            exit_reason = "late_tp"
            exit_idx = i
            break

        # 3) trailing stop: price <= high*(1 - trail_frac)
        if trail_frac and high_water>0 and px <= high_water*(1 - trail_frac):
            exit_reason = "trail"
            exit_idx = i
            break

        # 4) stop loss: price <= entry*(1 - sl_pct)
        if px <= sl_px:
            exit_reason = "sl"
            exit_idx = i
            break

    exit_ts, exit_px_obs = ticks[exit_idx]

    # execution with slippage on exit (sell)
    exit_exec = exit_px_obs * (1 - m)

    # gross pnl in USD
    pnl_usd_gross = units * (exit_exec - entry_exec)

    # fees: fee_bps per side on notional ~ base_size_usd
    fee = fee_bps/10000.0
    fees_usd = base_size_usd * fee * 2.0

    pnl_usd = pnl_usd_gross - fees_usd
    roi_pct = (pnl_usd / base_size_usd) * 100.0 if base_size_usd>0 else 0.0

    bars_held = max(0, exit_idx - i0 + 1)

    return {
        "entry_ts": entry_ts.strftime(ISO),
        "exit_ts": exit_ts.strftime(ISO),
        "entry_px": round(entry_px_obs, 8),
        "exit_px": round(exit_px_obs, 8),
        "bars_held": bars_held,
        "exit": exit_reason,
        "pnl_pct": round(roi_pct, 3),
        "size_usd": round(base_size_usd, 2),
        "pnl_usd": round(pnl_usd, 2),
        "fees_usd": round(fees_usd, 4),
        "tp_mult": tp_mult,
        "sl_pct": sl_pct,
        "trail_frac": trail_frac,
        "late_tp_after_frac": late_after_frac,
        "late_tp_frac": late_tp_frac,
        "slippage_bps": slippage_bps,
        "fee_bps": fee_bps,
        "max_bars": max_bars,
    }

def run_backtest(cfg: Dict[str,Any]=None) -> int:
    cfg = cfg or {}
    ds   = _rget(cfg, ["dataset"], {})
    params = _rget(cfg, ["params"], {})
    bt   = _rget(cfg, ["backtest"], {})
    sim  = _rget(cfg, ["sim"], {})
    risk = _rget(cfg, ["risk"], {})

    events_path = ds.get("events_jsonl") or "data/raw/events.jsonl"
    ticks_dir   = ds.get("ticks_dir") or "data/real/ticks"
    out_csv     = cfg.get("trade_log_csv") or "artifacts/trades.engine.csv"

    tp_mult = params.get("tp_mult", bt.get("tp_mult", 1.02))
    sl_pct  = params.get("sl_pct",  bt.get("sl_pct", 0.02))
    max_bars = int(params.get("max_bars", bt.get("max_bars", 12)))

    late_tp_frac = float(params.get("late_tp_frac",  sim.get("late_tp_frac", 0.0)))
    late_after_frac = float(params.get("late_tp_after_frac", sim.get("late_tp_after_frac", 0.0)))
    trail_frac = float(params.get("trail_frac", sim.get("trail_frac", 0.0)))

    slippage_bps = float(sim.get("slippage_bps", 0))
    base_size_usd = float(risk.get("base_size_usd", 200))
    fee_bps = float(risk.get("fee_bps", 0))

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)

    # load events
    events = _load_events(events_path)

    # group ticks per pair
    cache_ticks: Dict[str, List[Tuple[datetime,float]]] = {}

    rows_out: List[Dict[str,Any]] = []
    for ev in events:
        pair = (ev.get("pair") or "").replace("/","_")
        side = ev.get("side","buy")
        if side != "buy":
            # only long simulated for now
            continue
        t_event = _parse_iso(ev.get("t"))

        tick_path = os.path.join(ticks_dir, f"{pair}.csv")
        if pair not in cache_ticks:
            if not os.path.exists(tick_path):
                continue
            cache_ticks[pair] = _load_ticks_csv(tick_path)
        ticks = cache_ticks[pair]
        if not ticks: 
            continue

        idx = _find_entry_index(ticks, t_event)
        if idx < 0: 
            continue

        entry_ts, entry_px = ticks[idx]

        info = _sim_trade(
            ticks, idx, entry_ts, entry_px, side,
            max_bars=max_bars,
            tp_mult=float(tp_mult),
            sl_pct=float(sl_pct),
            trail_frac=trail_frac,
            late_after_frac=late_after_frac,
            late_tp_frac=late_tp_frac,
            slippage_bps=slippage_bps,
            base_size_usd=base_size_usd,
            fee_bps=fee_bps,
        )
        info["pair"] = pair.replace("_","/")
        rows_out.append(info)

    # write CSV
    if rows_out:
        fields = list(rows_out[0].keys())
    else:
        fields = ["pair","entry_ts","exit_ts","entry_px","exit_px","bars_held","exit",
                  "pnl_pct","size_usd","pnl_usd","fees_usd","tp_mult","sl_pct",
                  "trail_frac","late_tp_after_frac","late_tp_frac",
                  "slippage_bps","fee_bps","max_bars"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    return 0
