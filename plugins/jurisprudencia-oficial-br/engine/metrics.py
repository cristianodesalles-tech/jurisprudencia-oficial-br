from __future__ import annotations

import threading
from collections import defaultdict


class Metrics:
    def __init__(self):
        self._values: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, name: str, value: float = 1, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._values[key] += value

    def render_prometheus(self) -> str:
        lines = []
        with self._lock:
            items = sorted(self._values.items())
        for (name, labels), value in items:
            label_text = "{" + ",".join(f'{key}="{val}"' for key, val in labels) + "}" if labels else ""
            lines.append(f"juris_{name}{label_text} {value}")
        return "\n".join(lines) + "\n"


metrics = Metrics()
