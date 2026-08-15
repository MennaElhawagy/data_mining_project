#!/usr/bin/env bash
set -euo pipefail

# Research experiment runner for the Instacart mining layer.
# Run from the project root with Git Bash, WSL, Linux, or macOS.

PYTHON_BIN="${PYTHON_BIN:-python}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-instacart_dwh}"
PGUSER="${PGUSER:-postgres}"
PAPER_LOG_DIR="${PAPER_LOG_DIR:-./logs/paper_results}"
WORKERS="${WORKERS:-}"

if [[ -z "${PGPASSWORD:-}" ]]; then
  read -rsp "PostgreSQL password for ${PGUSER}: " PGPASSWORD
  echo
  export PGPASSWORD
fi

COMMON_ARGS=(
  --host "$PGHOST"
  --port "$PGPORT"
  --database "$PGDATABASE"
  --user "$PGUSER"
  --log-dir "$PAPER_LOG_DIR"
)

if [[ -n "$WORKERS" ]]; then
  COMMON_ARGS+=(--workers "$WORKERS")
fi

run_mining() {
  echo
  echo "============================================================"
  echo "Running: $*"
  echo "============================================================"
  "$PYTHON_BIN" ./mining_algo/run_mining.py "${COMMON_ARGS[@]}" "$@"
}

echo "Starting Instacart product-level mining research experiments"
echo "Database: ${PGDATABASE} on ${PGHOST}:${PGPORT}"
echo "Logs: ${PAPER_LOG_DIR}"
mkdir -p "$PAPER_LOG_DIR"

# Product level: Eclat and FP-Growth paper runs.
run_mining --algorithm eclat --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --refresh-baskets --notes "paper_results; product; eclat; top_100; support_0.01; confidence_0.30"
run_mining --algorithm eclat --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; eclat; top_100; support_0.005; confidence_0.30"
run_mining --algorithm eclat --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; eclat; top_100; support_0.003; confidence_0.30"

run_mining --algorithm fp_growth --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_100; support_0.01; confidence_0.30"
run_mining --algorithm fp_growth --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_100; support_0.005; confidence_0.30"
run_mining --algorithm fp_growth --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_100; support_0.003; confidence_0.30"

run_mining --algorithm eclat --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; eclat; top_500; support_0.01; confidence_0.30"
run_mining --algorithm eclat --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; eclat; top_500; support_0.005; confidence_0.30"
run_mining --algorithm eclat --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; eclat; top_500; support_0.003; confidence_0.30"

run_mining --algorithm fp_growth --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_500; support_0.01; confidence_0.30"
run_mining --algorithm fp_growth --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_500; support_0.005; confidence_0.30"
run_mining --algorithm fp_growth --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_500; support_0.003; confidence_0.30"

run_mining --algorithm eclat --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_1000; support_0.01; confidence_0.30"
run_mining --algorithm eclat --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_1000; support_0.005; confidence_0.30"
run_mining --algorithm eclat --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_1000; support_0.003; confidence_0.30"

run_mining --algorithm fp_growth --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_1000; support_0.01; confidence_0.30"
run_mining --algorithm fp_growth --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_1000; support_0.005; confidence_0.30"
run_mining --algorithm fp_growth --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_1000; support_0.003; confidence_0.30"

run_mining --algorithm eclat --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_5000; support_0.01; confidence_0.30"
run_mining --algorithm eclat --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_5000; support_0.005; confidence_0.30"
run_mining --algorithm eclat --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_5000; support_0.003; confidence_0.30"

run_mining --algorithm fp_growth --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_5000; support_0.01; confidence_0.30"
run_mining --algorithm fp_growth --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_5000; support_0.005; confidence_0.30"
run_mining --algorithm fp_growth --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_5000; support_0.003; confidence_0.30"

echo
echo "All research experiments completed."
