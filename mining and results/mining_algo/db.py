"""PostgreSQL access helpers for mining runs."""

from __future__ import annotations

import getpass
import logging
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import execute_values

from .models import AssociationRule, Itemset, Transaction


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"


BASKET_TABLES = {
    "product": ("v_order_product_baskets", "mining_baskets_product"),
    "aisle": ("v_order_aisle_baskets", "mining_baskets_aisle"),
    "department": ("v_order_department_baskets", "mining_baskets_department"),
}


def connect(args) -> PgConnection:
    password = args.password
    if password is None:
        password = getpass.getpass(f"Password for PostgreSQL user {args.user}: ")

    return psycopg2.connect(
        host=args.host,
        port=args.port,
        dbname=args.database,
        user=args.user,
        password=password,
    )


def prepare_basket_table(conn: PgConnection, granularity: str, refresh: bool) -> str:
    source_view, table_name = BASKET_TABLES[granularity]
    with conn.cursor() as cur:
        if refresh:
            logging.info("refresh prepared basket table %s", table_name)
            cur.execute(f"DROP TABLE IF EXISTS {table_name};")

        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            );
            """,
            (table_name,),
        )
        exists = cur.fetchone()[0]

        if not exists:
            logging.info("create prepared basket table %s from %s", table_name, source_view)
            cur.execute(
                f"""
                CREATE UNLOGGED TABLE {table_name} AS
                SELECT
                    order_id,
                    items::INTEGER[] AS items,
                    item_count::INT AS item_count
                FROM {source_view}
                WHERE item_count >= 2;
                """
            )
            cur.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY (order_id);")
            cur.execute(
                f"CREATE INDEX idx_{table_name}_items_gin ON {table_name} USING GIN (items);"
            )
            cur.execute(f"ANALYZE {table_name};")

    conn.commit()
    return table_name


def get_allowed_items(
    conn: PgConnection,
    table_name: str,
    top_items: int | None,
    min_item_support_count: int | None,
) -> set[int] | None:
    if top_items is None and min_item_support_count is None:
        return None

    conditions: list[str] = []
    params: list[int] = []
    if min_item_support_count is not None:
        conditions.append("COUNT(*) >= %s")
        params.append(min_item_support_count)

    having = f"HAVING {' AND '.join(conditions)}" if conditions else ""
    limit = "LIMIT %s" if top_items is not None else ""
    if top_items is not None:
        params.append(top_items)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT item_id
            FROM (
                SELECT UNNEST(items) AS item_id
                FROM {table_name}
            ) unnested
            GROUP BY item_id
            {having}
            ORDER BY COUNT(*) DESC, item_id
            {limit};
            """,
            params,
        )
        allowed = {row[0] for row in cur.fetchall()}

    logging.info("allowed item universe: %s items", f"{len(allowed):,}")
    return allowed


def load_transactions(
    conn: PgConnection,
    table_name: str,
    allowed_items: set[int] | None,
    max_baskets: int | None,
    fetch_size: int,
) -> list[Transaction]:
    transactions: list[Transaction] = []
    limit = "LIMIT %s" if max_baskets is not None else ""
    params: tuple[int, ...] = (max_baskets,) if max_baskets is not None else ()

    with conn.cursor(name="basket_stream") as cur:
        cur.itersize = fetch_size
        cur.execute(
            f"""
            SELECT items
            FROM {table_name}
            WHERE item_count >= 2
            ORDER BY order_id
            {limit};
            """,
            params,
        )
        for (items,) in cur:
            if allowed_items is not None:
                basket = tuple(sorted(item for item in items if item in allowed_items))
            else:
                basket = tuple(items)
            if len(basket) >= 2:
                transactions.append(basket)

    logging.info("loaded %s baskets for mining", f"{len(transactions):,}")
    return transactions


def fetch_item_names(
    conn: PgConnection,
    granularity: str,
    item_ids: Iterable[int],
) -> dict[int, str]:
    ids = sorted(set(item_ids))
    if not ids:
        return {}

    if granularity == "product":
        sql = "SELECT product_id, product_name FROM dim_product WHERE product_id = ANY(%s);"
    elif granularity == "aisle":
        sql = "SELECT DISTINCT category_id, category FROM dim_product WHERE category_id = ANY(%s);"
    else:
        sql = (
            "SELECT DISTINCT department_id, department "
            "FROM dim_product WHERE department_id = ANY(%s);"
        )

    with conn.cursor() as cur:
        cur.execute(sql, (ids,))
        return {row[0]: row[1] for row in cur.fetchall()}


def save_mining_results(
    conn: PgConnection,
    run_id: str,
    algorithm: str,
    granularity: str,
    min_support: float,
    min_confidence: float,
    runtime_seconds: float,
    notes: str | None,
    itemsets: dict[Itemset, int],
    rules: list[AssociationRule],
    transaction_count: int,
    batch_size: int,
) -> None:
    consequent_names = fetch_item_names(conn, granularity, (rule.consequent_id for rule in rules))

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_mining_run (
                run_id,
                algorithm,
                min_support,
                min_confidence,
                granularity,
                runtime_seconds,
                rules_generated,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                run_id,
                algorithm,
                min_support,
                min_confidence,
                granularity,
                runtime_seconds,
                len(rules),
                notes,
            ),
        )

        itemset_rows = [
            (
                list(items),
                len(items),
                support_count,
                support_count / transaction_count,
                granularity,
                run_id,
            )
            for items, support_count in sorted(itemsets.items(), key=lambda row: (len(row[0]), row[0]))
        ]
        if itemset_rows:
            execute_values(
                cur,
                """
                INSERT INTO fact_frequent_itemsets (
                    items,
                    itemset_size,
                    support_count,
                    support,
                    granularity,
                    run_id
                )
                VALUES %s;
                """,
                itemset_rows,
                page_size=batch_size,
            )

        rule_rows = [
            (
                list(rule.antecedent),
                len(rule.antecedent),
                rule.consequent_id,
                consequent_names.get(rule.consequent_id),
                rule.support,
                rule.confidence,
                rule.lift,
                granularity,
                run_id,
            )
            for rule in rules
        ]
        if rule_rows:
            execute_values(
                cur,
                """
                INSERT INTO fact_association_rules (
                    antecedent,
                    antecedent_size,
                    consequent_id,
                    consequent_name,
                    support,
                    confidence,
                    lift,
                    granularity,
                    run_id
                )
                VALUES %s;
                """,
                rule_rows,
                page_size=batch_size,
            )

    conn.commit()
