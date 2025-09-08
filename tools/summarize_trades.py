import sys
from app.backtest.metrics import pretty_print

path = sys.argv[1] if len(sys.argv) > 1 else "artifacts/trades.engine.csv"
pretty_print(path)
