-- Raw landing schema for Instacart CSV files.

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.orders (
    order_id                INT      PRIMARY KEY,
    user_id                 INT      NOT NULL,
    eval_set                TEXT     NOT NULL,
    order_number            INT      NOT NULL,
    order_dow               SMALLINT NOT NULL,
    order_hour_of_day       SMALLINT NOT NULL,
    days_since_prior_order  REAL     NULL
);

CREATE TABLE IF NOT EXISTS staging.order_products_prior (
    order_id            INT      NOT NULL,
    product_id          INT      NOT NULL,
    add_to_cart_order   SMALLINT NOT NULL,
    reordered           SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.order_products_train (
    order_id            INT      NOT NULL,
    product_id          INT      NOT NULL,
    add_to_cart_order   SMALLINT NOT NULL,
    reordered           SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.products (
    product_id      INT  PRIMARY KEY,
    product_name    TEXT NOT NULL,
    aisle_id        INT  NOT NULL,
    department_id   INT  NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.aisles (
    aisle_id INT  PRIMARY KEY,
    aisle    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.departments (
    department_id INT  PRIMARY KEY,
    department    TEXT NOT NULL
);

-- Timestamp enrichment from the simplified Instacart release.
CREATE TABLE IF NOT EXISTS staging.order_timestamps (
    order_id        INT       PRIMARY KEY,
    user_id         INT       NOT NULL,
    order_timestamp TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_staging_orders_user_id
    ON staging.orders (user_id);

CREATE INDEX IF NOT EXISTS idx_staging_orders_eval_set
    ON staging.orders (eval_set);

CREATE INDEX IF NOT EXISTS idx_staging_order_products_prior_order
    ON staging.order_products_prior (order_id);

CREATE INDEX IF NOT EXISTS idx_staging_order_products_prior_product
    ON staging.order_products_prior (product_id);

CREATE INDEX IF NOT EXISTS idx_staging_order_products_train_order
    ON staging.order_products_train (order_id);

CREATE INDEX IF NOT EXISTS idx_staging_order_products_train_product
    ON staging.order_products_train (product_id);
