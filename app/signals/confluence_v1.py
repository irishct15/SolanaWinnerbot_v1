import os, csv, json, argparse
from typing import List, Tuple, Dict, Any

def read_ticks(path: str) -> List[Tuple[str, float]]:
    out = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            ts = (r.get("ts") or r.get("time") or "").strip()
            p  = r.get("price") or r.get("px")
            try:
                px = float(p)
                if px > 0: out.append((ts, px))
            except: pass
    return out

def sma(values: List[float], n: int) -> List[float]:
    if n <= 0: return [0.0]*len(values)
    out = []
    s = 0.0
    q = []
    for v in values:
        q.append(v); s += v
        if len(q) > n:
            s -= q.pop(0)
        out.append(s/len(q))
    return out

def confluence_events(
    pair: str,
    ticks: List[Tuple[str, float]],
    ma_len: int = 20,
    momentum_len: int = 5,
    roi_len: int = 3,
    roi_min: float = 0.01,      # 1% min move over roi_len
    dedupe_bars: int = 10,      # no duplicate signal too soon
) -> List[Dict[str, Any]]:
    if len(ticks) < max(ma_len, momentum_len, roi_len) + 2:
        return []
    ts = [t for t,_ in ticks]
    px = [p for _,p in ticks]
    ma = sma(px, ma_len)

    last_signal_idx = -10_000
    events = []
    for i in range(1, len(px)):
        cross_up = px[i-1] <= ma[i-1] and px[i] > ma[i]  # price crosses up MA
        mom_ok = i - momentum_len >= 0 and (px[i] / px[i-momentum_len] - 1.0) > 0.0
        roi_ok = i - roi_len >= 0 and (px[i] / px[i-roi_len] - 1.0) >= roi_min
        if cross_up and mom_ok and roi_ok and (i - last_signal_idx >= dedupe_bars):
            events.append({
                "t": ts[i],
                "pair": pair.replace("_","/"),
                "price": round(px[i], 8),
                "side": "buy",
                "features": {
                    "ma_len": ma_len,
                    "momentum_len": momentum_len,
                    "roi_len": roi_len,
                    "roi_min": roi_min,
                    "dedupe_bars": dedupe_bars,
                    "reason": "ma_cross_up & momentum & roi",
                }
            })
            last_signal_idx = i
    return events

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks-dir", default="data/real/ticks")
    ap.add_argument("--out", default="data/raw/events.jsonl")
    ap.add_argument("--ma", type=int, default=20)
    ap.add_argument("--mom", type=int, default=5)
    ap.add_argument("--roi-len", type=int, default=3)
    ap.add_argument("--roi-min", type=float, default=0.01)
    ap.add_argument("--dedupe-bars", type=int, default=10)
    ap.add_argument("--max-pairs", type=int, default=1000)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    total = 0
    with open(args.out, "w", encoding="utf-8") as outf:
        count_pairs = 0
        for fn in os.listdir(args.ticks_dir):
            if not fn.lower().endswith(".csv"): continue
            pair = os.path.splitext(fn)[0]      # e.g. TEST_USDC
            path = os.path.join(args.ticks_dir, fn)
            ticks = read_ticks(path)
            evs = confluence_events(
                pair, ticks,
                ma_len=args.ma,
                momentum_len=args.mom,
                roi_len=args.roi_len,
                roi_min=args.roi_min,
                dedupe_bars=args.dedupe_bars,
            )
            for ev in evs:
                outf.write(json.dumps(ev) + "\n")
            total += len(evs)
            count_pairs += 1
            if count_pairs >= args.max_pairs: break
    print(f"[signals] wrote {total} events to {args.out}")

if __name__ == "__main__":
    main()
