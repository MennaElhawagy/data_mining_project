-- Transform staging data into the warehouse tables.

BEGIN;

SET LOCAL synchronous_commit = off;
SET LOCAL work_mem = '128MB';

-- =============================================================================
-- Dimensions
-- =============================================================================

INSERT INTO dim_customer (user_id, total_orders)
SELECT
    o.user_id,
    COUNT(*) AS total_orders
FROM staging.orders o
WHERE o.eval_set IN ('prior', 'train')
GROUP BY o.user_id
ON CONFLICT (user_id) DO UPDATE
SET total_orders = EXCLUDED.total_orders;

INSERT INTO dim_product (
    product_id,
    product_name,
    category_id,
    category,
    department_id,
    department
)
SELECT
    p.product_id,
    p.product_name,
    p.aisle_id AS category_id,
    a.aisle AS category,
    p.department_id,
    d.department
FROM staging.products p
JOIN staging.aisles a ON a.aisle_id = p.aisle_id
JOIN staging.departments d ON d.department_id = p.department_id
ON CONFLICT (product_id) DO UPDATE
SET
    product_name = EXCLUDED.product_name,
    category_id = EXCLUDED.category_id,
    category = EXCLUDED.category,
    department_id = EXCLUDED.department_id,
    department = EXCLUDED.department;

WITH date_rows AS (
    SELECT
        TO_CHAR(ot.order_timestamp, 'YYYYMMDDHH24')::INT AS date_key,
        ot.order_timestamp::DATE AS date,
        EXTRACT(DAY FROM ot.order_timestamp)::SMALLINT AS day,
        EXTRACT(MONTH FROM ot.order_timestamp)::SMALLINT AS month,
        EXTRACT(QUARTER FROM ot.order_timestamp)::SMALLINT AS quarter,
        EXTRACT(YEAR FROM ot.order_timestamp)::SMALLINT AS year,
        o.order_dow AS weekday,
        o.order_hour_of_day AS hour,
        (o.order_dow IN (0, 6)) AS is_weekend
    FROM staging.order_timestamps ot
    JOIN staging.orders o ON o.order_id = ot.order_id
    WHERE o.eval_set IN ('prior', 'train')
),
deduped_date_rows AS (
    SELECT
        date_key,
        MIN(date) AS date,
        MIN(day) AS day,
        MIN(month) AS month,
        MIN(quarter) AS quarter,
        MIN(year) AS year,
        MIN(weekday) AS weekday,
        MIN(hour) AS hour,
        BOOL_OR(is_weekend) AS is_weekend
    FROM date_rows
    GROUP BY date_key
)
INSERT INTO dim_date (
    date_key,
    date,
    day,
    month,
    quarter,
    year,
    weekday,
    hour,
    is_weekend
)
SELECT
    date_key,
    date,
    day,
    month,
    quarter,
    year,
    weekday,
    hour,
    is_weekend
FROM deduped_date_rows
ON CONFLICT (date_key) DO UPDATE
SET
    date = EXCLUDED.date,
    day = EXCLUDED.day,
    month = EXCLUDED.month,
    quarter = EXCLUDED.quarter,
    year = EXCLUDED.year,
    weekday = EXCLUDED.weekday,
    hour = EXCLUDED.hour,
    is_weekend = EXCLUDED.is_weekend;

INSERT INTO dim_order (
    order_id,
    order_number,
    days_since_prior_order
)
SELECT
    o.order_id,
    o.order_number,
    o.days_since_prior_order
FROM staging.orders o
WHERE o.eval_set IN ('prior', 'train')
ON CONFLICT (order_id) DO UPDATE
SET
    order_number = EXCLUDED.order_number,
    days_since_prior_order = EXCLUDED.days_since_prior_order;

-- =============================================================================
-- Fact table
-- =============================================================================

WITH all_order_products AS (
    SELECT
        order_id,
        product_id,
        add_to_cart_order,
        reordered
    FROM staging.order_products_prior

    UNION ALL

    SELECT
        order_id,
        product_id,
        add_to_cart_order,
        reordered
    FROM staging.order_products_train
)
INSERT INTO fact_order_items (
    order_id,
    user_id,
    product_id,
    date_key,
    add_to_cart_order,
    reordered,
    quantity
)
SELECT
    op.order_id,
    o.user_id,
    op.product_id,
    TO_CHAR(ot.order_timestamp, 'YYYYMMDDHH24')::INT AS date_key,
    op.add_to_cart_order,
    op.reordered,
    1 AS quantity
FROM all_order_products op
JOIN staging.orders o ON o.order_id = op.order_id
JOIN staging.order_timestamps ot ON ot.order_id = op.order_id
ON CONFLICT (order_id, product_id) DO UPDATE
SET
    user_id = EXCLUDED.user_id,
    date_key = EXCLUDED.date_key,
    add_to_cart_order = EXCLUDED.add_to_cart_order,
    reordered = EXCLUDED.reordered,
    quantity = EXCLUDED.quantity;

COMMIT;

ANALYZE;
