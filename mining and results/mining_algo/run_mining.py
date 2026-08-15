"""Run association-rule mining against the PostgreSQL DWH."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mining_algo.apriori import run_apriori
from mining_algo.db import (
    connect,
    get_allowed_items,
    load_transactions,
    prepare_basket_table,
    save_mining_results,
)
from mining_algo.eclat import run_eclat
from mining_algo.fp_growth import run_fp_growth
from mining_algo.rules import generate_single_consequent_rules
from mining_algo.utils import default_workers, setup_logging, timed_step


ALGORITHMS = {
    "apriori": run_apriori,
    "fp_growth": run_fp_growth,
    "eclat": run_eclat,
}
ALGORITHM_CHOICES = sorted([*ALGORITHMS, "all"])
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Apriori, FP-Growth, or Eclat on prepared Instacart DWH baskets."
    )
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")))
    parser.add_argument("--database", default=os.getenv("PGDATABASE", "instacart_dwh"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD"))

    parser.add_argument("--algorithm", choices=ALGORITHM_CHOICES, required=True)
    parser.add_argument("--granularity", choices=["product", "aisle", "department"], required=True)
    parser.add_argument("--min-support", type=float, required=True)
    parser.add_argument("--min-confidence", type=float, required=True)

    parser.add_argument("--workers", type=int, default=default_workers())
    parser.add_argument("--max-itemset-size", type=int, default=3)
    parser.add_argument("--max-baskets", type=int)
    parser.add_argument("--top-items", type=int)
    parser.add_argument("--min-item-support-count", type=int)
    parser.add_argument("--fetch-size", type=int, default=10000)
    parser.add_argument("--insert-batch-size", type=int, default=5000)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--refresh-baskets", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--notes")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not 0 < args.min_support <= 1:
        raise ValueError("--min-support must be between 0 and 1")
    if not 0 < args.min_confidence <= 1:
        raise ValueError("--min-confidence must be between 0 and 1")
    if args.workers < 1:
        raise ValueError("--workers must be at least 1")
    if args.max_itemset_size < 2:
        raise ValueError("--max-itemset-size must be at least 2")


def build_run_id(args: argparse.Namespace, algorithm: str | None = None) -> str:
    suffix = uuid.uuid4().hex[:8]
    algorithm_name = algorithm or args.algorithm
    return f"{algorithm_name}_{args.granularity}_{suffix}"


def main() -> int:
    args = parse_args()
    validate_args(args)
    session_id = build_run_id(args)
    setup_logging(args.log_dir, session_id)

    started = time.perf_counter()
    logging.info("session_id=%s", session_id)
    logging.info(
        "algorithm=%s granularity=%s min_support=%s min_confidence=%s workers=%s",
        args.algorithm,
        args.granularity,
        args.min_support,
        args.min_confidence,
        args.workers,
    )

    with connect(args) as conn:
        with timed_step("prepare basket table"):
            table_name = prepare_basket_table(conn, args.granularity, args.refresh_baskets)

        if args.prepare_only:
            logging.info("prepare-only requested; no mining run saved")
            return 0

        with timed_step("load and filter prepared baskets"):
            allowed_items = get_allowed_items(
                conn,
                table_name,
                args.top_items,
                args.min_item_support_count,
            )
            transactions = load_transactions(
                conn,
                table_name,
                allowed_items,
                args.max_baskets,
                args.fetch_size,
            )

        if not transactions:
            raise RuntimeError("No baskets were loaded after filtering.")

        selected_algorithms = sorted(ALGORITHMS) if args.algorithm == "all" else [args.algorithm]
        for algorithm_name in selected_algorithms:
            algorithm = ALGORITHMS[algorithm_name]
            run_id = build_run_id(args, algorithm_name)
            algorithm_started = time.perf_counter()
            logging.info("START mining run %s", run_id)

            with timed_step(f"run {algorithm_name}"):
                mining_result = algorithm(
                    transactions=transactions,
                    min_support=args.min_support,
                    workers=args.workers,
                    max_itemset_size=args.max_itemset_size,
                )

            with timed_step(f"generate {algorithm_name} association rules"):
                rules = generate_single_consequent_rules(
                    mining_result.itemsets,
                    mining_result.transaction_count,
                    args.min_confidence,
                )

            runtime_seconds = time.perf_counter() - algorithm_started
            notes = args.notes
            run_note = f"batch_session_id={session_id}" if args.algorithm == "all" else None
            if run_note:
                notes = f"{notes}; {run_note}" if notes else run_note
            if allowed_items is not None:
                filter_note = (
                    f"filtered_items={len(allowed_items)}; "
                    f"top_items={args.top_items}; "
                    f"min_item_support_count={args.min_item_support_count}"
                )
                notes = f"{notes}; {filter_note}" if notes else filter_note

            logging.info("%s frequent itemsets: %s", algorithm_name, f"{len(mining_result.itemsets):,}")
            logging.info("%s association rules: %s", algorithm_name, f"{len(rules):,}")
            logging.info("%s runtime seconds: %.2f", algorithm_name, runtime_seconds)

            with timed_step(f"save {algorithm_name} mining results to DWH"):
                save_mining_results(
                    conn=conn,
                    run_id=run_id,
                    algorithm=algorithm_name,
                    granularity=args.granularity,
                    min_support=args.min_support,
                    min_confidence=args.min_confidence,
                    runtime_seconds=runtime_seconds,
                    notes=notes,
                    itemsets=mining_result.itemsets,
                    rules=rules,
                    transaction_count=mining_result.transaction_count,
                    batch_size=args.insert_batch_size,
                )

            logging.info("DONE mining run %s in %.2fs", run_id, runtime_seconds)

    logging.info("mining pipeline completed in %.2fs", time.perf_counter() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
