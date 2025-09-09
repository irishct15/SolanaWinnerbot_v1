from pathlib import Path

def tick_filepath(symbol: str, out_dir: str) -> Path:
    return Path(out_dir) / f"{symbol.upper()}_USDC.csv"

def _assert_usdc(p: Path):
    # allow tick and future ohlcv variant
    if not (p.name.endswith("_USDC.csv") or p.name.endswith("_USDC_ohlcv.csv")):
        raise RuntimeError(f"[TICKS_GUARD] Illegal tick file target: {p}")

def write_tick(out_dir: str, symbol: str, iso_ts: str, price: float):
    p = tick_filepath(symbol, out_dir)
    _assert_usdc(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(f"{iso_ts},{price}\n")
