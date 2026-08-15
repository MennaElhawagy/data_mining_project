-- Validation checks for the Instacart Data Warehouse.

-- =============================================================================
-- 1. Table row counts
-- =============================================================================

SELECT 'dim_date' AS table_name, COUNT(*) AS row_count FROM dim_date
UNION ALL
SELECT 'dim_customer', COUNT(*) FROM dim_customer
UNION ALL
SELECT 'dim_product', COUNT(*) FROM dim_product
UNION ALL
SELECT 'dim_order', COUNT(*) FROM dim_order
UNION ALL
SELECT 'fact_order_items', COUNT(*) FROM fact_order_items
UNION ALL
SELECT 'dim_mining_run', COUNT(*) FROM dim_mining_run
UNION ALL
SELECT 'fact_frequent_itemsets', COUNT(*) FROM fact_frequent_itemsets
UNION ALL
SELECT 'fact_association_rules', COUNT(*) FROM fact_association_rules
UNION ALL
SELECT 'fact_user_recommendations', COUNT(*) FROM fact_user_recommendations
ORDER BY table_name;

-- Expected approximate counts after full ETL:
--   dim_customer: 206,209
--   dim_product: 49,688
--   dim_order: 3,346,083
--   fact_order_items: 33,819,106

-- =============================================================================
-- 2. Zero-result integrity checks
-- =============================================================================

SELECT 'dim_order rows connected to test orders' AS check_name,
       COUNT(*) AS should_be_zero
FROM dim_order o
JOIN staging.orders so ON so.order_id = o.order_id
WHERE so.eval_set = 'test';

SELECT 'fact rows connected to missing dim_order rows' AS check_name,
       COUNT(*) AS should_be_zero
FROM fact_order_items foi
LEFT JOIN dim_order o ON o.order_id = foi.order_id
WHERE o.order_id IS NULL;

SELECT 'duplicate product names with same product_id' AS check_name,
       COUNT(*) AS should_be_zero
FROM (
    SELECT product_id
    FROM dim_product
    GROUP BY product_id
    HAVING COUNT(*) > 1
) duplicates;

SELECT 'duplicate fact order/product lines' AS check_name,
       COUNT(*) AS should_be_zero
FROM (
    SELECT order_id, product_id
    FROM fact_order_items
    GROUP BY order_id, product_id
    HAVING COUNT(*) > 1
) duplicates;

SELECT 'empty product basket rows' AS check_name,
       COUNT(*) AS should_be_zero
FROM v_order_product_baskets
WHERE item_count = 0 OR cardinality(items) = 0;

SELECT 'itemsets with wrong itemset_size' AS check_name,
       COUNT(*) AS should_be_zero
FROM fact_frequent_itemsets
WHERE cardinality(items) <> itemset_size;

SELECT 'rules with wrong antecedent_size' AS check_name,
       COUNT(*) AS should_be_zero
FROM fact_association_rules
WHERE cardinality(antecedent) <> antecedent_size;

SELECT 'recommendations whose source rule has different run_id' AS check_name,
       COUNT(*) AS should_be_zero
FROM fact_user_recommendations rec
JOIN fact_association_rules r ON r.rule_key = rec.source_rule_key
WHERE rec.run_id <> r.run_id;

-- =============================================================================
-- 3. Distribution sanity checks
-- =============================================================================

SELECT
    MIN(item_count) AS min_basket_size,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY item_count) AS p25_basket_size,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY item_count) AS median_basket_size,
    AVG(item_count::REAL) AS avg_basket_size,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY item_count) AS p75_basket_size,
    MAX(item_count) AS max_basket_size
FROM v_order_product_baskets;

SELECT
    MIN(total_orders) AS min_orders_per_user,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY total_orders) AS median_orders_per_user,
    AVG(total_orders::REAL) AS avg_orders_per_user,
    MAX(total_orders) AS max_orders_per_user
FROM dim_customer;

SELECT
    p.department,
    COUNT(*) AS order_lines,
    COUNT(DISTINCT foi.order_id) AS orders,
    AVG(foi.reordered::REAL) AS reorder_rate
FROM fact_order_items foi
JOIN dim_product p ON p.product_id = foi.product_id
GROUP BY p.department
ORDER BY order_lines DESC;

-- =============================================================================
-- 4. Mining output inspection
-- =============================================================================

SELECT
    run_id,
    algorithm,
    granularity,
    min_support,
    min_confidence,
    runtime_seconds,
    rules_generated,
    run_date
FROM dim_mining_run
ORDER BY run_date DESC;

SELECT
    run_id,
    granularity,
    COUNT(*) AS rule_count,
    MIN(lift) AS min_lift,
    AVG(lift) AS avg_lift,
    MAX(lift) AS max_lift
FROM fact_association_rules
GROUP BY run_id, granularity
ORDER BY run_id, granularity;
