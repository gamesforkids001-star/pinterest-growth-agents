import sys
from pathlib import Path
from src.core import orchestrator as o, config
ROOT = Path(__file__).resolve().parents[1]
def main(argv):
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd == "tick": print(o.tick(ROOT))
    elif cmd == "daily": print(o.daily(ROOT))
    elif cmd == "weekly": print(o.weekly(ROOT))
    elif cmd == "monitor": print(o.monitor(ROOT))
    elif cmd == "test-notify": return o.test_notify(ROOT)
    elif cmd == "board-check": o.board_check(ROOT)
    elif cmd == "rules-check":
        ok, failed = o.rules_check(ROOT); print("read:", ok, "failed:", failed)
    elif cmd == "dashboard":
        s, _, _, db = o.ctx(ROOT); o.refresh_dashboard(ROOT, s, db)
    elif cmd == "validate":
        _, _, n = config.load(ROOT); print("\n".join(n) or "settings OK")
    else: print("commands: tick | daily | weekly | monitor | test-notify | board-check | rules-check | dashboard | validate")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv))
