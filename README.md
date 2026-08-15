# Instacart Market Basket Analysis

A data warehouse and association rule mining project built on the [Instacart Online Grocery Basket](https://www.kaggle.com/c/instacart-market-basket-analysis) dataset.

The project has two halves. The first builds a PostgreSQL star-schema data warehouse from raw CSV files. The second implements the Apriori, FP-Growth, and Eclat algorithms from scratch and mines the warehouse for association rules, writing the results back into the same database.

Everything is written in Python with only `psycopg2` as an external dependency — the mining algorithms use no data-mining libraries.

---

## Results

All three algorithms were benchmarked at product granularity on **1,725,017 baskets**, with `max_itemset_size = 2` and `min_confidence = 0.30`. Runtimes are in seconds.

| Item universe | Min support | Itemsets | Rules | Apriori | FP-Growth | Eclat |
|--------------:|------------:|---------:|------:|--------:|----------:|------:|
| Top 100       | 0.010       | 171      | 10    | 245.3   | 23.3      | **20.7** |
| Top 100       | 0.005       | 450      | 28    | 222.3   | 22.4      | **15.6** |
| Top 100       | 0.003       | 859      | 28    | 259.8   | **28.1**  | 29.1 |
| Top 500       | 0.010       | 183      | 8     | 879.3   | 35.3      | **30.3** |
| Top 500       | 0.005       | 555      | 16    | 5999.2  | 52.0      | **51.1** |

Two things stand out:

- **All three algorithms return identical itemset and rule counts** for every configuration, which cross-validates the three independent implementations.
- **Apriori scales badly.** At 100 items it is roughly 10× slower than the others; at 500 items the gap widens to 29× and then 117×. This is the expected consequence of Apriori's repeated full passes over the transaction set for each candidate level, versus the single tree build (FP-Growth) or tid-set intersection (Eclat).

Full logs for every run are committed under [`mining and results/logs/paper_results/`](mining%20and%20results/logs/paper_results/).

The ETL pipeline loads ~790 MB of CSV and completes in about 16.5 minutes on a local PostgreSQL instance.

---

## Repository layout

```
etl_and_dwh_implemmentation/
  pipeline/run_dwh_pipeline.py    ETL orchestrator
  sql/                            schema, staging, ETL, indexes, views, validation
  logs/                           pipeline run logs

mining and results/
  mining_algo/
    run_mining.py                 mining orchestrator (all DB access)
    apriori/  fp_growth/  eclat/  algorithm implementations
    rules.py                      association rule generation
    db.py  models.py  utils.py    shared helpers
    run_research_experiments.*    benchmark sweep scripts
  logs/                           mining run logs, incl. paper_results/
```

## Warehouse design

A star schema in the `public` schema, loaded from a `staging` schema that mirrors the raw CSVs.

**Dimensions** — `dim_customer`, `dim_product`, `dim_order`, `dim_date`
**Fact** — `fact_order_items` (one row per product per order)
**Mining output** — `dim_mining_run`, `fact_frequent_itemsets`, `fact_association_rules`

`dim_date` uses an hour-grain key in `YYYYMMDDHH` format. Only the `prior` and `train` splits are loaded; the `test` split is excluded.

Three views expose baskets at different granularities, all aggregating `fact_order_items` into arrays:

| Granularity | View | Items are |
|---|---|---|
| `product`    | `v_order_product_baskets`    | product IDs |
| `aisle`      | `v_order_aisle_baskets`      | aisle / category IDs |
| `department` | `v_order_department_baskets` | department IDs |

Before mining, each view is materialized into an `UNLOGGED` table with a GIN index and reused across runs, which avoids re-aggregating the full fact table on every experiment.

## Mining design

`run_mining.py` holds all database access; the algorithm packages are pure in-memory Python. Each implements the same interface:

```python
run_algorithm(transactions, min_support, workers, max_itemset_size) -> MiningResult
```

All three parallelize with `multiprocessing`, but along different axes:

- **Apriori** — level-wise candidate generation, splitting *transactions* across workers for each counting pass.
- **FP-Growth** — builds an FP-tree, then mines conditional pattern bases per top-level item in parallel.
- **Eclat** — vertical tid-set representation, intersecting tid-sets depth-first with one *branch* per worker.

Rules are generated in the `A,B => C` form with a single consequent, scored by support, confidence, and lift. Every run is tagged with a unique `run_id` so results from different parameter sweeps stay separable in the same database.

---

## Setup

**Requirements:** PostgreSQL 12+, Python 3.12, `pip install psycopg2-binary`

The dataset is not included in this repository. Place the CSVs under `etl_and_dwh_implemmentation/instacart_dataset/`:

```
instacart_dataset/
  dataset_files/     aisles.csv, departments.csv, products.csv, orders.csv,
                     order_products__prior.csv, order_products__train.csv
  dataset2_files/    orders.csv  (order_id, user_id, order_timestamp)
```

`dataset2_files/orders.csv` is a separate file supplying real order timestamps. The original Instacart data only provides day-of-week and hour-of-day, so this file is what `dim_date` and `fact_order_items.date_key` are derived from.

Connection settings come from the standard `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGPASSWORD` environment variables, each overridable by a command-line flag. Defaults are `localhost:5432/instacart_dwh` as user `postgres`. If no password is supplied the scripts prompt for one.

## Usage

**Build the warehouse** (from `etl_and_dwh_implemmentation/`):

```bash
python pipeline/run_dwh_pipeline.py                # full run
python pipeline/run_dwh_pipeline.py --skip-copy    # re-run ETL without reloading CSVs
python pipeline/run_dwh_pipeline.py --rebuild      # truncate everything first
```

Each stage has a `--skip-*` flag (`--skip-copy`, `--skip-etl`, `--skip-indexes`, `--skip-views`, `--skip-validation`). The database is created automatically if it does not exist.

**Run mining** (from `mining and results/`):

```bash
python mining_algo/run_mining.py --algorithm fp_growth --granularity product \
    --min-support 0.005 --min-confidence 0.30 --top-items 500 --max-itemset-size 2

python mining_algo/run_mining.py --algorithm all --granularity department \
    --min-support 0.01 --min-confidence 0.30
```

Useful options:

| Flag | Purpose |
|---|---|
| `--algorithm` | `apriori`, `fp_growth`, `eclat`, or `all` |
| `--granularity` | `product`, `aisle`, or `department` |
| `--top-items N` | restrict mining to the N most frequent items |
| `--max-itemset-size N` | cap itemset length (default 3) |
| `--refresh-baskets` | rebuild the prepared basket table |
| `--workers N` | worker processes (defaults to CPU count) |

Pass `--refresh-baskets` after reloading the warehouse, otherwise the previously materialized basket table is reused.

**Reproduce the benchmark sweep** (from `mining and results/`):

```powershell
.\mining_algo\run_research_experiments.ps1     # or run_research_experiments.sh
```

---

## Notes

`fact_user_recommendations` and its supporting view exist in the schema as a planned extension — turning mined rules into per-user product recommendations — but that step is not implemented yet.
