from __future__ import annotations

import os


def main() -> None:
    try:
        from redis import Redis
        from rq import Queue, Worker
    except ImportError as exc:
        raise RuntimeError("instale redis e rq para iniciar o worker") from exc
    connection = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    worker = Worker([Queue("ingestion", connection=connection)], connection=connection)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
