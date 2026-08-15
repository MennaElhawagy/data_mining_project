-- Mining and reporting views.

-- =============================================================================
-- Basket views for association rule mining
-- =============================================================================

-- Product-grain baskets.
CREATE OR REPLACE VIEW v_order_product_baskets AS
SELECT
    foi.order_id,
    MIN(foi.user_id) AS user_id,
    MIN(foi.date_key) AS date_key,
    ARRAY_AGG(foi.product_id ORDER BY foi.product_id) AS items,
    COUNT(*) AS item_count
FROM fact_order_items foi
GROUP BY foi.order_id;

-- Aisle/category-grain baskets.
CREATE OR REPLACE VIEW v_order_aisle_baskets AS
SELECT
    foi.order_id,
    MIN(foi.user_id) AS user_id,
    MIN(foi.date_key) AS date_key,
    ARRAY_AGG(DISTINCT p.category_id ORDER BY p.category_id) AS items,
    COUNT(DISTINCT p.category_id) AS item_count
FROM fact_order_items foi
JOIN dim_product p ON p.product_id = foi.product_id
GROUP BY foi.order_id;

-- Department-grain baskets.
CREATE OR REPLACE VIEW v_order_department_baskets AS
SELECT
    foi.order_id,
    MIN(foi.user_id) AS user_id,
    MIN(foi.date_key) AS date_key,
    ARRAY_AGG(DISTINCT p.department_id ORDER BY p.department_id) AS items,
    COUNT(DISTINCT p.department_id) AS item_count
FROM fact_order_items foi
JOIN dim_product p ON p.product_id = foi.product_id
GROUP BY foi.order_id;

-- User product history profiles.
CREATE OR REPLACE VIEW v_user_product_profiles AS
SELECT
    foi.user_id,
    ARRAY_AGG(DISTINCT foi.product_id ORDER BY foi.product_id) AS product_ids,
    COUNT(DISTINCT foi.product_id) AS distinct_products,
    COUNT(DISTINCT foi.order_id) AS orders_with_products
FROM fact_order_items foi
GROUP BY foi.user_id;

-- =============================================================================
-- Power BI / reporting views
-- =============================================================================

CREATE OR REPLACE VIEW v_order_timing_summary AS
SELECT
    d.weekday,
    d.hour,
    COUNT(DISTINCT foi.order_id) AS orders,
    COUNT(*) AS order_lines
FROM fact_order_items foi
JOIN dim_date d ON d.date_key = foi.date_key
GROUP BY d.weekday, d.hour;

CREATE OR REPLACE VIEW v_product_sales_summary AS
SELECT
    p.product_id,
    p.product_name,
    p.category_id,
    p.category,
    p.department_id,
    p.department,
    COUNT(*) AS order_lines,
    COUNT(DISTINCT foi.order_id) AS orders,
    AVG(foi.reordered::REAL) AS reorder_rate
FROM fact_order_items foi
JOIN dim_product p ON p.product_id = foi.product_id
GROUP BY
    p.product_id,
    p.product_name,
    p.category_id,
    p.category,
    p.department_id,
    p.department;

CREATE OR REPLACE VIEW v_department_sales_summary AS
SELECT
    p.department_id,
    p.department,
    COUNT(*) AS order_lines,
    COUNT(DISTINCT foi.order_id) AS orders,
    COUNT(DISTINCT foi.product_id) AS distinct_products,
    AVG(foi.reordered::REAL) AS reorder_rate
FROM fact_order_items foi
JOIN dim_product p ON p.product_id = foi.product_id
GROUP BY p.department_id, p.department;

CREATE OR REPLACE VIEW v_latest_mining_run AS
SELECT r.*
FROM dim_mining_run r
WHERE r.run_date = (
    SELECT MAX(r2.run_date)
    FROM dim_mining_run r2
);

CREATE OR REPLACE VIEW v_top_association_rules AS
SELECT
    r.rule_key,
    r.run_id,
    m.algorithm,
    r.granularity,
    r.antecedent,
    r.consequent_id,
    r.consequent_name,
    r.support,
    r.confidence,
    r.lift
FROM fact_association_rules r
JOIN dim_mining_run m ON m.run_id = r.run_id
ORDER BY r.lift DESC, r.confidence DESC, r.support DESC;

CREATE OR REPLACE VIEW v_user_recommendations_with_products AS
SELECT
    rec.run_id,
    rec.user_id,
    rec.recommendation_rank,
    rec.score,
    rec.recommended_product_id,
    p.product_name AS recommended_product_name,
    p.category AS recommended_category,
    p.department AS recommended_department,
    rec.source_rule_key,
    rec.generated_at
FROM fact_user_recommendations rec
JOIN dim_product p ON p.product_id = rec.recommended_product_id;
