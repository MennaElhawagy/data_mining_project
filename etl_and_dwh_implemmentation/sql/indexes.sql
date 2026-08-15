-- Performance indexes for the Instacart Data Warehouse.

-- =============================================================================
-- Layer 1: transactional star schema
-- =============================================================================

-- Fact table joins, grouping, and user-history access.
CREATE INDEX IF NOT EXISTS idx_fact_order_items_order_id
    ON fact_order_items (order_id);

CREATE INDEX IF NOT EXISTS idx_fact_order_items_user_id
    ON fact_order_items (user_id);

CREATE INDEX IF NOT EXISTS idx_fact_order_items_product_id
    ON fact_order_items (product_id);

CREATE INDEX IF NOT EXISTS idx_fact_order_items_date_key
    ON fact_order_items (date_key);

CREATE INDEX IF NOT EXISTS idx_fact_order_items_user_date
    ON fact_order_items (user_id, date_key DESC);

CREATE INDEX IF NOT EXISTS idx_fact_order_items_order_cart
    ON fact_order_items (order_id, add_to_cart_order);

-- Dimension lookups.
CREATE INDEX IF NOT EXISTS idx_dim_order_order_number
    ON dim_order (order_number);

CREATE INDEX IF NOT EXISTS idx_dim_product_category_id
    ON dim_product (category_id);

CREATE INDEX IF NOT EXISTS idx_dim_product_department_id
    ON dim_product (department_id);

CREATE INDEX IF NOT EXISTS idx_dim_product_department_category
    ON dim_product (department_id, category_id);

CREATE INDEX IF NOT EXISTS idx_dim_date_date
    ON dim_date (date);

CREATE INDEX IF NOT EXISTS idx_dim_date_weekday_hour
    ON dim_date (weekday, hour);

-- =============================================================================
-- Layer 2: mining output
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_dim_mining_run_algorithm_granularity
    ON dim_mining_run (algorithm, granularity);

CREATE INDEX IF NOT EXISTS idx_fact_frequent_itemsets_run
    ON fact_frequent_itemsets (run_id);

CREATE INDEX IF NOT EXISTS idx_fact_frequent_itemsets_run_granularity_support
    ON fact_frequent_itemsets (run_id, granularity, support DESC);

-- Array containment for itemset queries.
CREATE INDEX IF NOT EXISTS idx_fact_frequent_itemsets_items_gin
    ON fact_frequent_itemsets USING GIN (items);

CREATE INDEX IF NOT EXISTS idx_fact_association_rules_run
    ON fact_association_rules (run_id);

CREATE INDEX IF NOT EXISTS idx_fact_association_rules_run_granularity_lift
    ON fact_association_rules (run_id, granularity, lift DESC);

CREATE INDEX IF NOT EXISTS idx_fact_association_rules_consequent
    ON fact_association_rules (granularity, consequent_id);

-- Array containment for rule antecedents.
CREATE INDEX IF NOT EXISTS idx_fact_association_rules_antecedent_gin
    ON fact_association_rules USING GIN (antecedent);

CREATE INDEX IF NOT EXISTS idx_fact_user_recommendations_user_run_rank
    ON fact_user_recommendations (user_id, run_id, recommendation_rank);

CREATE INDEX IF NOT EXISTS idx_fact_user_recommendations_run_product
    ON fact_user_recommendations (run_id, recommended_product_id);

CREATE INDEX IF NOT EXISTS idx_fact_user_recommendations_source_rule
    ON fact_user_recommendations (source_rule_key);

ANALYZE;
