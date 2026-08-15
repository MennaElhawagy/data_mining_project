"""PostgreSQL Data Warehouse pipeline runner for the Instacart project."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2 import sql as pgsql
from psycopg2.extensions import connection as PgConnection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = PROJECT_ROOT / "sql"
DEFAULT_DATASET_DIR = PROJECT_ROOT / "instacart_dataset"


STAGING_INDEXES = [
    "staging.idx_staging_orders_user_id",
    "staging.idx_staging_orders_eval_set",
    "staging.idx_staging_order_products_prior_order",
    "staging.idx_staging_order_products_prior_product",
    "staging.idx_staging_order_products_train_order",
    "staging.idx_staging_order_products_train_product",
]


DWH_INDEXES = [
    "public.idx_fact_order_items_order_id",
    "public.idx_fact_order_items_user_id",
    "public.idx_fact_order_items_product_id",
    "public.idx_fact_order_items_date_key",
    "public.idx_fact_order_items_user_date",
    "public.idx_fact_order_items_order_cart",
    "public.idx_dim_order_order_number",
    "public.idx_dim_product_category_id",
    "public.idx_dim_product_department_id",
    "public.idx_dim_product_department_category",
    "public.idx_dim_date_date",
    "public.idx_dim_date_weekday_hour",
    "public.idx_dim_mining_run_algorithm_granularity",
    "public.idx_fact_frequent_itemsets_run",
    "public.idx_fact_frequent_itemsets_run_granularity_support",
    "public.idx_fact_frequent_itemsets_items_gin",
    "public.idx_fact_association_rules_run",
    "public.idx_fact_association_rules_run_granularity_lift",
    "public.idx_fact_association_rules_consequent",
    "public.idx_fact_association_rules_antecedent_gin",
    "public.idx_fact_user_recommendations_user_run_rank",
    "public.idx_fact_user_recommendations_run_product",
    "public.idx_fact_user_recommendations_source_rule",
]


STAGING_TABLES = [
    "staging.order_products_prior",
    "staging.order_products_train",
    "staging.order_timestamps",
    "staging.orders",
    "staging.products",
    "staging.aisles",
    "staging.departments",
]


DWH_TABLES = [
    "fact_user_recommendations",
    "fact_association_rules",
    "fact_frequent_itemsets",
    "dim_mining_run",
    "fact_order_items",
    "dim_order",
    "dim_product",
    "dim_customer",
    "dim_date",
]


COPY_JOBS = [
    (
        "staging.aisles",
        ("dataset_files", "aisles.csv"),
        ["aisle_id", "aisle"],
    ),
    (
        "staging.departments",
        ("dataset_files", "departments.csv"),
        ["department_id", "department"],
    ),
    (
        "staging.products",
        ("dataset_files", "products.csv"),
        ["product_id", "product_name", "aisle_id", "department_id"],
    ),
    (
        "staging.orders",
        ("dataset_files", "orders.csv"),
        [
            "order_id",
            "user_id",
            "eval_set",
            "order_number",
            "order_dow",
            "order_hour_of_day",
            "days_since_prior_order",
        ],
    ),
    (
        "staging.order_timestamps",
        ("dataset2_files", "orders.csv"),
        ["order_id", "user_id", "order_timestamp"],
    ),
    (
        "staging.order_products_train",
        ("dataset_files", "order_products__train.csv"),
        ["order_id", "product_id", "add_to_cart_order", "reordered"],
    ),
    (
        "staging.order_products_prior",
        ("dataset_files", "order_products__prior.csv"),
        ["order_id", "product_id", "add_to_cart_order", "reordered"],
    ),
]


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


def setup_logging() -> Path:
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"dwh_pipeline_{time.strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    return log_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Instacart PostgreSQL DWH pipeline."
    )
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")))
    parser.add_argument("--database", default=os.getenv("PGDATABASE", "instacart_dwh"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD"))
    parser.add_argument(
        "--prompt-password",
        action="store_true",
        help="Prompt for the PostgreSQL password. This is automatic when no password is supplied.",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="Path to instacart_dataset.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Truncate staging and final DWH tables before loading.",
    )
    parser.add_argument(
        "--no-create-db",
        action="store_true",
        help="Fail instead of creating the target database when it does not exist.",
    )
    parser.add_argument(
        "--skip-copy",
        action="store_true",
        help="Do not reload raw CSV files into staging.",
    )
    parser.add_argument(
        "--skip-etl",
        action="store_true",
        help="Do not run etl_from_staging.sql.",
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Do not run indexes.sql.",
    )
    parser.add_argument(
        "--skip-views",
        action="store_true",
        help="Do not run views.sql.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Do not run validation.sql at the end.",
    )
    parser.add_argument(
        "--exact-counts",
        action="store_true",
        help="Run exact COUNT(*) on final DWH tables. Slower on fact_order_items.",
    )
    return parser.parse_args()


def _database_missing(exc: psycopg2.OperationalError, database: str) -> bool:
    """True when the OperationalError is a 'database does not exist' failure."""
    if getattr(exc, "pgcode", None) == "3D000":  # invalid_catalog_name
        return True
    message = str(exc)
    return "does not exist" in message and f'"{database}"' in message


def create_database(args: argparse.Namespace, password: str) -> None:
    """Create the target database by connecting to the maintenance database."""
    maintenance_db = "postgres"
    logging.warning("Database %r does not exist; creating it.", args.database)
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        dbname=maintenance_db,
        user=args.user,
        password=password,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                pgsql.SQL("CREATE DATABASE {}").format(pgsql.Identifier(args.database))
            )
        logging.info("Created database %r", args.database)
    finally:
        conn.close()


def connect(args: argparse.Namespace) -> PgConnection:
    password = args.password
    if not password:
        password = getpass.getpass(f"Password for PostgreSQL user {args.user}: ")

    connect_kwargs = dict(
        host=args.host,
        port=args.port,
        dbname=args.database,
        user=args.user,
        password=password,
    )

    try:
        conn = psycopg2.connect(**connect_kwargs)
    except psycopg2.OperationalError as exc:
        if args.no_create_db or not _database_missing(exc, args.database):
            raise
        create_database(args, password)
        conn = psycopg2.connect(**connect_kwargs)

    conn.autocommit = True
    return conn


def run_sql(conn: PgConnection, sql: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql)


def run_sql_file(conn: PgConnection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    run_sql(conn, sql)


def relation_exists(conn: PgConnection, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_name = %s
            );
            """,
            (schema, table),
        )
        return bool(cur.fetchone()[0])


def ensure_schema(conn: PgConnection) -> None:
    if relation_exists(conn, "public", "fact_order_items"):
        logging.info("public schema tables already exist; skipping schema.sql")
    else:
        with timed_step("create DWH schema"):
            run_sql_file(conn, SQL_DIR / "schema.sql")

    with timed_step("create/update staging schema"):
        run_sql_file(conn, SQL_DIR / "staging.sql")


def drop_indexes(conn: PgConnection, index_names: Iterable[str]) -> None:
    for index_name in index_names:
        run_sql(conn, f"DROP INDEX IF EXISTS {index_name};")


def truncate_tables(conn: PgConnection, tables: list[str], label: str) -> None:
    joined = ", ".join(tables)
    with timed_step(f"truncate {label}"):
        run_sql(conn, f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE;")


def validate_csv_paths(dataset_dir: Path) -> None:
    missing = []
    for _, path_parts, _ in COPY_JOBS:
        path = dataset_dir.joinpath(*path_parts)
        if not path.exists():
            missing.append(str(path))
    if missing:
        raise FileNotFoundError("Missing CSV files:\n" + "\n".join(missing))


def copy_csvs_to_staging(conn: PgConnection, dataset_dir: Path) -> None:
    validate_csv_paths(dataset_dir)

    with timed_step("drop staging indexes before COPY"):
        drop_indexes(conn, STAGING_INDEXES)

    truncate_tables(conn, STAGING_TABLES, "staging tables")

    old_autocommit = conn.autocommit
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL synchronous_commit = off;")
            for table_name, path_parts, columns in COPY_JOBS:
                csv_path = dataset_dir.joinpath(*path_parts)
                size_mb = csv_path.stat().st_size / (1024 * 1024)
                column_sql = ", ".join(columns)
                copy_sql = (
                    f"COPY {table_name} ({column_sql}) "
                    "FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
                )
                with timed_step(f"COPY {csv_path.name} -> {table_name} ({size_mb:.1f} MB)"):
                    with csv_path.open("r", encoding="utf-8", newline="") as file_obj:
                        cur.copy_expert(copy_sql, file_obj)
                    logging.info("%s", cur.statusmessage)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = old_autocommit

    with timed_step("recreate staging indexes"):
        run_sql_file(conn, SQL_DIR / "staging.sql")


def run_dwh_etl(conn: PgConnection) -> None:
    with timed_step("run SQL transform/load into DWH"):
        run_sql_file(conn, SQL_DIR / "etl_from_staging.sql")


def run_indexes(conn: PgConnection) -> None:
    with timed_step("create DWH helper indexes"):
        run_sql_file(conn, SQL_DIR / "indexes.sql")


def run_views(conn: PgConnection) -> None:
    with timed_step("create/update views"):
        run_sql_file(conn, SQL_DIR / "views.sql")


def run_validation(conn: PgConnection) -> None:
    with timed_step("run validation.sql"):
        run_sql_file(conn, SQL_DIR / "validation.sql")


def log_table_estimates(conn: PgConnection) -> None:
    with timed_step("log PostgreSQL row estimates"):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT schemaname, relname, n_live_tup
                FROM pg_stat_user_tables
                WHERE schemaname IN ('public', 'staging')
                ORDER BY schemaname, relname;
                """
            )
            for schema_name, table_name, rows in cur.fetchall():
                logging.info("estimate %-8s.%-32s %,d rows", schema_name, table_name, rows)


def log_exact_counts(conn: PgConnection) -> None:
    for table_name in reversed(DWH_TABLES):
        with timed_step(f"COUNT {table_name}"):
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cur.fetchone()[0]
                logging.info("exact %-32s %,d rows", table_name, count)


def main() -> int:
    args = parse_args()
    log_file = setup_logging()
    logging.info("Log file: %s", log_file)
    logging.info("Project root: %s", PROJECT_ROOT)
    logging.info("Dataset dir: %s", args.dataset_dir)
    logging.info("Database: %s@%s:%s/%s", args.user, args.host, args.port, args.database)

    pipeline_start = time.perf_counter()
    try:
        with timed_step("connect to PostgreSQL"):
            conn = connect(args)

        try:
            ensure_schema(conn)

            if args.rebuild:
                truncate_tables(conn, DWH_TABLES, "final DWH tables")

            if not args.skip_copy:
                copy_csvs_to_staging(conn, args.dataset_dir)
            else:
                logging.info("Skipping CSV copy step")

            if not args.skip_indexes:
                with timed_step("drop existing DWH helper indexes before ETL"):
                    drop_indexes(conn, DWH_INDEXES)

            if not args.skip_etl:
                run_dwh_etl(conn)
            else:
                logging.info("Skipping SQL ETL step")

            if not args.skip_indexes:
                run_indexes(conn)
            else:
                logging.info("Skipping indexes.sql")

            if not args.skip_views:
                run_views(conn)
            else:
                logging.info("Skipping views.sql")

            log_table_estimates(conn)

            if args.exact_counts:
                log_exact_counts(conn)

            if not args.skip_validation:
                run_validation(conn)
            else:
                logging.info("Skipping validation.sql")
        finally:
            conn.close()

    except Exception as exc:
        logging.error("Pipeline failed: %s", exc)
        return 1

    elapsed = time.perf_counter() - pipeline_start
    logging.info("Pipeline completed in %.2fs (%.2f minutes)", elapsed, elapsed / 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
