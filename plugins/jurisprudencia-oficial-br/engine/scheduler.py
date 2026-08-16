from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from .audit import HashChainAudit
from .network import probe_sources


running = True


def stop(*_args) -> None:
    global running
    running = False


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    interval = max(int(os.getenv("SOURCE_PROBE_INTERVAL", "3600")), 300)
    root = Path(__file__).resolve().parents[1]
    state = Path(os.getenv("STATE_DIR", ".state"))
    audit = HashChainAudit(state / "audit" / "events.jsonl")
    while running:
        try:
            outcomes = probe_sources(root / "config" / "sources.json")
            for outcome in outcomes:
                audit.append("source_probe", outcome)
        except Exception as exc:
            audit.append("source_monitor_error", {"error": type(exc).__name__, "message": str(exc)})
        deadline = time.monotonic() + interval
        while running and time.monotonic() < deadline:
            time.sleep(min(5, max(deadline - time.monotonic(), 0)))


if __name__ == "__main__":
    main()
