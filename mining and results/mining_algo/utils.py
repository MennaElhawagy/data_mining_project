"""Utility functions for mining scripts."""

from __future__ import annotations

import logging
import math
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Sequence


def default_workers() -> int:
    return max(1, os.cpu_count() or 1)


def min_support_count(min_support: float, transaction_count: int) -> int:
    return max(1, math.ceil(min_support * transaction_count))


def chunked(sequence: Sequence, chunk_count: int) -> list[Sequence]:
    if not sequence:
        return []
    chunk_count = max(1, min(chunk_count, len(sequence)))
    chunk_size = math.ceil(len(sequence) / chunk_count)
    return [sequence[index : index + chunk_size] for index in range(0, len(sequence), chunk_size)]


def setup_logging(log_dir: Path, run_id: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"mining_{run_id}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    logging.info("log file: %s", log_path)


@contextmanager
def timed_step(name: str):
    start = time.perf_counter()
    logging.info("START %s", name)
    try:
        yield
    except Exception:
        elapsed = time.perf_counter() - start
        logging.exception("FAILED %s after %.2fs", name, elapsed)
        raise
    else:
        elapsed = time.perf_counter() - start
        logging.info("DONE  %s in %.2fs", name, elapsed)
