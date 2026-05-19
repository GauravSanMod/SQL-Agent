"""
Verified queries for all three platforms.

These serve as gold-standard few-shot examples that
are dynamically injected into the SLM prompt based
on similarity to the user's question.
"""

from __future__ import annotations

from schema.models import VerifiedQuery

# ── Databricks (Bakehouse) ───────────────────────────────

DATABRICKS_VERIFIED: list[VerifiedQuery] = [
    VerifiedQuery(
        name="franchises_usa_vs_canada",
        question=(
            "How does the number of franchises in the "
            "country 'USA' compare to the number in "
            "'Canada'?"
        ),
        sql=(
            "SELECT country, COUNT(*) AS num_franchises "
            "FROM sales_franchises "
            "WHERE country IN ('USA', 'Canada') "
            "GROUP BY country;"
        ),
    ),
    VerifiedQuery(
        name="total_revenue_by_product",
        question="What is the total revenue by product?",
        sql=(
            "SELECT product, SUM(totalPrice) "
            "AS total_revenue "
            "FROM sales_transactions "
            "GROUP BY product "
            "ORDER BY total_revenue DESC;"
        ),
    ),
    VerifiedQuery(
        name="top_5_customers_by_spending",
        question=(
            "Who are the top 5 customers by total "
            "spending?"
        ),
        sql=(
            "SELECT c.first_name, c.last_name, "
            "SUM(t.totalPrice) AS total_spent "
            "FROM sales_transactions t "
            "LEFT JOIN sales_customers c "
            "ON t.customerID = c.customerID "
            "GROUP BY c.first_name, c.last_name "
            "ORDER BY total_spent DESC LIMIT 5;"
        ),
    ),
    VerifiedQuery(
        name="suppliers_in_europe",
        question=(
            "Which suppliers are located in Europe?"
        ),
        sql=(
            "SELECT supplierID, name, city, ingredient "
            "FROM sales_suppliers "
            "WHERE continent = 'Europe';"
        ),
    ),
    VerifiedQuery(
        name="avg_transaction_per_franchise",
        question=(
            "What is the average transaction amount "
            "per franchise?"
        ),
        sql=(
            "SELECT f.name, "
            "AVG(t.totalPrice) AS avg_amount "
            "FROM sales_transactions t "
            "LEFT JOIN sales_franchises f "
            "ON t.franchiseID = f.franchiseID "
            "GROUP BY f.name "
            "ORDER BY avg_amount DESC;"
        ),
    ),
]

# ── Snowflake (TEST_DB) ─────────────────────────────────

SNOWFLAKE_VERIFIED: list[VerifiedQuery] = [
    VerifiedQuery(
        name="avg_qty_top_customers",
        question=(
            "How does the average quantity ordered differ "
            "between the top two customers?"
        ),
        sql=(
            "SELECT TOP_C.CUSTOMER_ID, "
            "AVG(O.QUANTITY) AS AVG_QTY "
            "FROM CUST_ORDER O "
            "JOIN ("
            "  SELECT CUSTOMER_ID FROM CUST_ORDER "
            "  GROUP BY CUSTOMER_ID "
            "  ORDER BY SUM(QUANTITY) DESC LIMIT 2"
            ") AS TOP_C "
            "ON O.CUSTOMER_ID = TOP_C.CUSTOMER_ID "
            "GROUP BY TOP_C.CUSTOMER_ID "
            "ORDER BY AVG_QTY DESC;"
        ),
    ),
    VerifiedQuery(
        name="total_sales_by_category",
        question=(
            "What are the total sales by product "
            "category?"
        ),
        sql=(
            "SELECT p.PRODUCT_CATEGORY, "
            "SUM(o.TOTAL_AMOUNT) AS total_sales "
            "FROM CUST_ORDER o "
            "JOIN PRODUCT_LOOKUP p "
            "ON o.PRODUCT_ID = p.PRODUCT_ID "
            "GROUP BY p.PRODUCT_CATEGORY "
            "ORDER BY total_sales DESC;"
        ),
    ),
    VerifiedQuery(
        name="customers_most_orders",
        question=(
            "Which customers have placed the most "
            "orders?"
        ),
        sql=(
            "SELECT c.CUSTOMER_NAME, "
            "COUNT(o.ORDER_ID) AS order_count "
            "FROM CUST_ORDER o "
            "JOIN CUSTOMER_MASTER c "
            "ON o.CUSTOMER_ID = c.CUSTOMER_ID "
            "GROUP BY c.CUSTOMER_NAME "
            "ORDER BY order_count DESC;"
        ),
    ),
    VerifiedQuery(
        name="total_amount_per_region",
        question=(
            "What is the total order amount per region?"
        ),
        sql=(
            "SELECT c.REGION, "
            "SUM(o.TOTAL_AMOUNT) AS total "
            "FROM CUST_ORDER o "
            "JOIN CUSTOMER_MASTER c "
            "ON o.CUSTOMER_ID = c.CUSTOMER_ID "
            "GROUP BY c.REGION "
            "ORDER BY total DESC;"
        ),
    ),
    VerifiedQuery(
        name="products_ordered_by_customer",
        question=(
            "List all products ordered by customer "
            "'Aarav Sharma'."
        ),
        sql=(
            "SELECT p.PRODUCT_NAME, o.QUANTITY, "
            "o.TOTAL_AMOUNT "
            "FROM CUST_ORDER o "
            "JOIN CUSTOMER_MASTER c "
            "ON o.CUSTOMER_ID = c.CUSTOMER_ID "
            "JOIN PRODUCT_LOOKUP p "
            "ON o.PRODUCT_ID = p.PRODUCT_ID "
            "WHERE c.CUSTOMER_NAME = 'Aarav Sharma';"
        ),
    ),
]

# ── BigQuery (finance) ───────────────────────────────────

BIGQUERY_VERIFIED: list[VerifiedQuery] = [
    VerifiedQuery(
        name="revenue_by_segment",
        question=(
            "What is the total revenue by customer "
            "segment?"
        ),
        sql=(
            "SELECT c.segment, "
            "SUM(o.order_total) AS total_revenue "
            "FROM orders o "
            "JOIN customers c "
            "ON o.customer_id = c.customer_id "
            "GROUP BY c.segment "
            "ORDER BY total_revenue DESC;"
        ),
    ),
    VerifiedQuery(
        name="highest_discount_products",
        question=(
            "Which products have the highest total "
            "discount amounts?"
        ),
        sql=(
            "SELECT p.product_name, p.category, "
            "SUM(oi.discount_amount) AS total_discount "
            "FROM order_items oi "
            "JOIN products p "
            "ON oi.product_id = p.product_id "
            "GROUP BY p.product_name, p.category "
            "ORDER BY total_discount DESC;"
        ),
    ),
    VerifiedQuery(
        name="orders_delivered_vs_cancelled",
        question=(
            "How many orders are delivered vs cancelled?"
        ),
        sql=(
            "SELECT order_status, "
            "COUNT(*) AS order_count "
            "FROM orders "
            "WHERE order_status "
            "IN ('DELIVERED', 'CANCELLED') "
            "GROUP BY order_status;"
        ),
    ),
    VerifiedQuery(
        name="avg_shipping_cost_by_carrier",
        question=(
            "What is the average shipping cost by "
            "carrier?"
        ),
        sql=(
            "SELECT carrier, "
            "AVG(shipping_cost) AS avg_cost "
            "FROM shipments "
            "GROUP BY carrier "
            "ORDER BY avg_cost DESC;"
        ),
    ),
    VerifiedQuery(
        name="vendors_unpaid_invoices",
        question=(
            "Which vendors have the most unpaid "
            "invoices?"
        ),
        sql=(
            "SELECT v.vendor_name, "
            "COUNT(vi.vendor_invoice_id) AS unpaid "
            "FROM vendor_invoices vi "
            "JOIN vendors v "
            "ON vi.vendor_id = v.vendor_id "
            "WHERE vi.invoice_status = 'UNPAID' "
            "GROUP BY v.vendor_name "
            "ORDER BY unpaid DESC;"
        ),
    ),
]

ALL_VERIFIED = (
    DATABRICKS_VERIFIED
    + SNOWFLAKE_VERIFIED
    + BIGQUERY_VERIFIED
)
