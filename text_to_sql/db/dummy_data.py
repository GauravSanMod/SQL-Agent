"""
Dummy SQLite database generator.

Creates an in-memory (or file-backed) SQLite database that
mirrors all three platform schemas with 5 realistic sample
rows per table. Used for dry-run validation of generated
SQL without needing live Databricks/Snowflake/BigQuery
credentials.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from config.settings import DUMMY_DB_PATH

LOGGER = logging.getLogger(__name__)


# ── DDL + INSERT statements ─────────────────────────────


_DATABRICKS_DDL = """
-- Databricks: sales_customers
CREATE TABLE IF NOT EXISTS sales_customers (
    customerID      INTEGER PRIMARY KEY,
    first_name      TEXT,
    last_name       TEXT,
    email_address   TEXT,
    phone_number    TEXT,
    address         TEXT,
    city            TEXT,
    state           TEXT,
    country         TEXT,
    continent       TEXT,
    gender          TEXT,
    postal_zip_code INTEGER
);

INSERT OR IGNORE INTO sales_customers VALUES
(1, 'Alice',  'Johnson', 'alice.j@mail.com',
 '+1-555-0101', '123 Oak St', 'New York', 'NY',
 'USA', 'North America', 'Female', 10001),
(2, 'Bob',    'Smith',   'bob.s@mail.com',
 '+1-555-0102', '456 Pine Ave', 'Toronto', 'ON',
 'Canada', 'North America', 'Male', 15201),
(3, 'Chitra', 'Patel',   'chitra.p@mail.com',
 '+44-555-0103', '789 Elm Rd', 'London', 'ENG',
 'UK', 'Europe', 'Female', 30301),
(4, 'David',  'Kim',     'david.k@mail.com',
 '+82-555-0104', '101 Maple Dr', 'Seoul', 'SEL',
 'South Korea', 'Asia', 'Male', 40401),
(5, 'Elena',  'Garcia',  'elena.g@mail.com',
 '+61-555-0105', '202 Birch Ln', 'Sydney', 'NSW',
 'Australia', 'Oceania', 'Female', 50501);

-- Databricks: sales_suppliers
CREATE TABLE IF NOT EXISTS sales_suppliers (
    supplierID INTEGER PRIMARY KEY,
    name       TEXT,
    ingredient TEXT,
    continent  TEXT,
    city       TEXT,
    district   TEXT,
    size       TEXT,
    approved   TEXT,
    longitude  REAL,
    latitude   REAL
);

INSERT OR IGNORE INTO sales_suppliers VALUES
(101, 'Flour Co',       'Flour',  'North America',
 'Chicago',   'Loop',     'Large',  'approved',
 -87.6298, 41.8781),
(102, 'Sugar World',    'Sugar',  'Europe',
 'Paris',     'Marais',   'Medium', 'approved',
 2.3522,   48.8566),
(103, 'Butter Farm',    'Butter', 'Oceania',
 'Melbourne', 'CBD',      'Small',  'approved',
 144.9631, -37.8136),
(104, 'Cocoa Ltd',      'Cocoa',  'Africa',
 'Accra',     'Osu',      'Medium', 'pending',
 -0.1870,   5.6037),
(105, 'Vanilla Beans',  'Vanilla','Asia',
 'Jakarta',   'Menteng',  'Small',  'approved',
 106.8456, -6.2088);

-- Databricks: sales_franchises
CREATE TABLE IF NOT EXISTS sales_franchises (
    franchiseID INTEGER PRIMARY KEY,
    name        TEXT,
    city        TEXT,
    district    TEXT,
    zipcode     TEXT,
    country     TEXT,
    size        TEXT,
    longitude   REAL,
    latitude    REAL,
    supplierID  INTEGER
);

INSERT OR IGNORE INTO sales_franchises VALUES
(201, 'Bakehouse NYC',     'New York',  'Manhattan',
 '10001', 'USA',     'Large',  -73.9857, 40.7484, 101),
(202, 'Bakehouse Toronto', 'Toronto',   'Downtown',
 'M5V',   'Canada',  'Medium', -79.3832, 43.6532, 101),
(203, 'Bakehouse London',  'London',    'Soho',
 'W1D',   'UK',      'Large',  -0.1340,  51.5134, 102),
(204, 'Bakehouse Seoul',   'Seoul',     'Gangnam',
 '06000', 'South Korea','Small',-127.0474,37.5172, 104),
(205, 'Bakehouse Sydney',  'Sydney',    'CBD',
 '2000',  'Australia','Medium', 151.2093,-33.8688, 103);

-- Databricks: sales_transactions
CREATE TABLE IF NOT EXISTS sales_transactions (
    transactionID INTEGER PRIMARY KEY,
    customerID    INTEGER,
    franchiseID   INTEGER,
    product       TEXT,
    quantity       INTEGER,
    unitPrice     INTEGER,
    totalPrice    INTEGER,
    paymentMethod TEXT,
    cardNumber    INTEGER,
    dateTime      TEXT
);

INSERT OR IGNORE INTO sales_transactions VALUES
(3001, 1, 201, 'Croissant',    3,  5,  15,
 'Credit Card', 4111, '2025-01-15 09:30:00'),
(3002, 2, 202, 'Sourdough',    2, 8,   16,
 'Cash',        0,    '2025-01-16 10:00:00'),
(3003, 3, 203, 'Baguette',     5, 4,   20,
 'Mobile Pay',  0,    '2025-02-01 11:15:00'),
(3004, 4, 204, 'Croissant',    1, 6,    6,
 'Credit Card', 5500, '2025-02-10 14:00:00'),
(3005, 5, 205, 'Chocolate Cake',2,25,  50,
 'Credit Card', 3400, '2025-03-05 16:30:00');
"""


_SNOWFLAKE_DDL = """
-- Snowflake: CUSTOMER_MASTER
CREATE TABLE IF NOT EXISTS CUSTOMER_MASTER (
    CUSTOMER_ID   TEXT PRIMARY KEY,
    CUSTOMER_NAME TEXT,
    EMAIL         TEXT,
    PHONE         INTEGER,
    REGION        TEXT
);

INSERT OR IGNORE INTO CUSTOMER_MASTER VALUES
('C001', 'Aarav Sharma',  'aarav@example.com',
 9100000001, 'North'),
('C002', 'Meera Iyer',    'meera@example.com',
 9100000002, 'South'),
('C003', 'Rohan Das',     'rohan@example.com',
 9100000003, 'East'),
('C004', 'Priya Singh',   'priya@example.com',
 9100000004, 'West'),
('C005', 'Karan Reddy',   'karan@example.com',
 9100000005, 'South');

-- Snowflake: PRODUCT_LOOKUP
CREATE TABLE IF NOT EXISTS PRODUCT_LOOKUP (
    PRODUCT_ID       TEXT PRIMARY KEY,
    PRODUCT_NAME     TEXT,
    PRODUCT_CATEGORY TEXT
);

INSERT OR IGNORE INTO PRODUCT_LOOKUP VALUES
('P001', 'Widget A',  'Electronics'),
('P002', 'Widget B',  'Electronics'),
('P003', 'Gadget X',  'Home'),
('P004', 'Gadget Y',  'Home'),
('P005', 'Tool Z',    'Industrial');

-- Snowflake: CUST_ORDER
CREATE TABLE IF NOT EXISTS CUST_ORDER (
    ORDER_ID     TEXT PRIMARY KEY,
    CUSTOMER_ID  TEXT,
    PRODUCT_ID   TEXT,
    QUANTITY     INTEGER,
    TOTAL_AMOUNT REAL,
    ORDER_DATE   TEXT
);

INSERT OR IGNORE INTO CUST_ORDER VALUES
('O001', 'C001', 'P001', 10, 5000.00,  '2025-01-10'),
('O002', 'C002', 'P003',  5, 3500.00,  '2025-01-15'),
('O003', 'C001', 'P002',  8, 4000.00,  '2025-02-01'),
('O004', 'C003', 'P005', 20, 12000.00, '2025-02-20'),
('O005', 'C004', 'P004',  3, 2100.00,  '2025-03-05');
"""


_BIGQUERY_DDL = """
-- BigQuery: customers
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    first_name  TEXT,
    last_name   TEXT,
    email       TEXT,
    segment     TEXT,
    city        TEXT,
    state       TEXT,
    country     TEXT,
    notes       TEXT,
    phone       INTEGER,
    postal_code INTEGER,
    created_at  TEXT
);

INSERT OR IGNORE INTO customers VALUES
('CUST0001','Sneha','Singh','sneha@ex.com',
 'Loyalty-Gold','Bengaluru','KA','India',
 'High value customer',917544930855,560001,
 '2023-10-03'),
('CUST0002','Priya','Patel','priya@ex.com',
 'Loyalty-Silver','Chennai','TN','India',
 'Prefers email',917503007433,600001,
 '2023-05-02'),
('CUST0003','Amit','Gupta','amit@ex.com',
 'Retail','Delhi','DL','India',
 NULL,918525126721,110001,
 '2024-04-12'),
('CUST0004','Ravi','Kumar','ravi@ex.com',
 'Loyalty-Gold','Mumbai','MH','India',
 'VIP',919876543210,400001,
 '2024-01-15'),
('CUST0005','Neha','Joshi','neha@ex.com',
 'Retail','Hyderabad','TS','India',
 NULL,918765432100,500001,
 '2024-06-01');

-- BigQuery: products
CREATE TABLE IF NOT EXISTS products (
    product_id          TEXT PRIMARY KEY,
    product_name        TEXT,
    category            TEXT,
    subcategory         TEXT,
    brand               TEXT,
    vendor_id           TEXT,
    currency            TEXT,
    is_active           INTEGER,
    product_description TEXT,
    unit_price          REAL,
    unit_cost           REAL
);

INSERT OR IGNORE INTO products VALUES
('PROD00001','Electronics_Local_1','Electronics',
 'Local','BrandA','VEND001','INR',1,
 'High quality',1807.82,904.00),
('PROD00002','Electronics_Local_2','Electronics',
 'Local','BrandB','VEND001','INR',1,
 'Top seller',2427.78,1200.00),
('PROD00003','Home_Imported_3','Home',
 'Imported','BrandA','VEND002','INR',1,
 'Imported item',477.92,240.00),
('PROD00004','Grocery_Economy_4','Grocery',
 'Economy','BrandC','VEND003','INR',1,
 'Budget pick',150.00,80.00),
('PROD00005','Home_Local_5','Home',
 'Local','BrandB','VEND002','INR',0,
 'Discontinued',3569.44,1800.00);

-- BigQuery: vendors
CREATE TABLE IF NOT EXISTS vendors (
    vendor_id     TEXT PRIMARY KEY,
    vendor_name   TEXT,
    contact_name  TEXT,
    contact_email TEXT,
    address       TEXT,
    city          TEXT,
    state         TEXT,
    country       TEXT,
    payment_terms TEXT,
    vendor_notes  TEXT,
    phone         INTEGER,
    postal_code   INTEGER
);

INSERT OR IGNORE INTO vendors VALUES
('VEND001','Vendor_1','Kunal','v1@suppliers.com',
 '149 Market Rd','Bengaluru','KA','India',
 'NET30','Trusted supplier',919898361802,560001),
('VEND002','Vendor_2','Isha','v2@suppliers.com',
 '32 Market Rd','Hyderabad','TS','India',
 'NET45','Bulk discounts',916670725133,500001),
('VEND003','Vendor_3','Meera','v3@suppliers.com',
 '91 Market Rd','Kolkata','WB','India',
 'ADVANCE',NULL,919575810782,700001);

-- BigQuery: orders
CREATE TABLE IF NOT EXISTS orders (
    order_id            TEXT PRIMARY KEY,
    customer_id         TEXT,
    order_status        TEXT,
    sales_channel       TEXT,
    payment_method      TEXT,
    shipping_address    TEXT,
    shipping_city       TEXT,
    shipping_state      TEXT,
    shipping_country    TEXT,
    customer_notes      TEXT,
    order_date          TEXT,
    order_subtotal      REAL,
    tax_amount          REAL,
    shipping_amount     REAL,
    order_total         REAL,
    shipping_postal_code INTEGER
);

INSERT OR IGNORE INTO orders VALUES
('ORD000001','CUST0001','DELIVERED','Online','Card',
 '10 MG Rd','Bengaluru','KA','India',
 NULL,'2024-01-05',18370.30,3306.65,200.00,
 21876.95,560001),
('ORD000002','CUST0002','DELIVERED','Store','UPI',
 '20 Anna Nagar','Chennai','TN','India',
 'Call before delivery','2024-04-03',
 19857.05,3574.27,150.00,23581.32,600001),
('ORD000003','CUST0003','CANCELLED','Mobile-App','COD',
 '30 Connaught Pl','Delhi','DL','India',
 NULL,'2024-06-15',5000.00,900.00,100.00,
 6000.00,110001),
('ORD000004','CUST0001','PLACED','Online','Card',
 '10 MG Rd','Bengaluru','KA','India',
 NULL,'2024-09-28',9500.00,1710.00,200.00,
 11410.00,560001),
('ORD000005','CUST0004','DELIVERED','Online','UPI',
 '40 Marine Dr','Mumbai','MH','India',
 NULL,'2024-11-10',12000.00,2160.00,180.00,
 14340.00,400001);

-- BigQuery: order_items
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id   TEXT PRIMARY KEY,
    order_id        TEXT,
    product_id      TEXT,
    quantity        INTEGER,
    unit_price      REAL,
    discount_amount REAL,
    line_total      REAL
);

INSERT OR IGNORE INTO order_items VALUES
('ORD000001-ITEM1','ORD000001','PROD00001',2,
 1807.82,14.16,3601.48),
('ORD000001-ITEM2','ORD000001','PROD00003',4,
 477.92,5.76,1905.92),
('ORD000002-ITEM1','ORD000002','PROD00002',4,
 2427.78,8.33,9702.79),
('ORD000003-ITEM1','ORD000003','PROD00004',10,
 150.00,0.00,1500.00),
('ORD000005-ITEM1','ORD000005','PROD00001',3,
 1807.82,20.00,5403.46);

-- BigQuery: invoices
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id     TEXT PRIMARY KEY,
    order_id       TEXT,
    invoice_status TEXT,
    currency       TEXT,
    invoice_terms  TEXT,
    invoice_date   TEXT,
    due_date       TEXT,
    payment_date   TEXT,
    subtotal       REAL,
    tax_amount     REAL,
    shipping_amount REAL,
    total_amount   REAL
);

INSERT OR IGNORE INTO invoices VALUES
('INVORD000001','ORD000001','PAID','INR','NET30',
 '2024-01-06','2024-02-05','2024-01-21',
 18370.30,3306.65,200.00,21876.95),
('INVORD000002','ORD000002','PAID','INR','NET30',
 '2024-04-04','2024-05-04','2024-04-20',
 19857.05,3574.27,150.00,23581.32),
('INVORD000005','ORD000005','UNPAID','INR','NET30',
 '2024-11-11','2024-12-11',NULL,
 12000.00,2160.00,180.00,14340.00);

-- BigQuery: shipments
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id       TEXT PRIMARY KEY,
    order_id          TEXT,
    carrier           TEXT,
    tracking_number   TEXT,
    shipment_status   TEXT,
    origin_warehouse  TEXT,
    destination_city  TEXT,
    destination_state TEXT,
    destination_country TEXT,
    shipment_notes    TEXT,
    shipped_date      TEXT,
    delivered_date    TEXT,
    shipping_cost     REAL
);

INSERT OR IGNORE INTO shipments VALUES
('SHP001','ORD000001','BlueDart','TRACK001',
 'DELIVERED','BLR-03','Bengaluru','KA','India',
 NULL,'2024-01-06','2024-01-08',200.00),
('SHP002','ORD000002','DTDC','TRACK002',
 'DELIVERED','CHN-01','Chennai','TN','India',
 'Handle with care','2024-04-04','2024-04-06',150.00),
('SHP003','ORD000005','Delhivery','TRACK003',
 'IN_TRANSIT','Mumbai-01','Mumbai','MH','India',
 NULL,'2024-11-12',NULL,180.00);

-- BigQuery: vendor_invoices
CREATE TABLE IF NOT EXISTS vendor_invoices (
    vendor_invoice_id   TEXT PRIMARY KEY,
    vendor_id           TEXT,
    invoice_status      TEXT,
    currency            TEXT,
    invoice_description TEXT,
    invoice_date        TEXT,
    due_date            TEXT,
    payment_date        TEXT,
    pdf_gcs_uri         TEXT,
    subtotal            REAL,
    tax_amount          REAL,
    total_amount        REAL
);

INSERT OR IGNORE INTO vendor_invoices VALUES
('VENDORINV00001','VEND001','PAID','INR',
 'Monthly supply','2024-09-08','2024-10-08',
 '2024-09-25','gs://bucket/inv1.pdf',
 38409.30,6913.67,45322.97),
('VENDORINV00002','VEND002','UNPAID','INR',
 'Bulk order','2024-10-18','2024-12-02',
 NULL,'gs://bucket/inv2.pdf',
 21694.74,3905.05,25599.79),
('VENDORINV00003','VEND003','PAID','INR',
 'Imported batch','2024-09-11','2024-10-26',
 '2024-10-20','gs://bucket/inv3.pdf',
 46202.83,8316.51,54519.34);
"""


# ── Public API ───────────────────────────────────────────


def create_dummy_database(
    db_path: Path | None = None,
) -> sqlite3.Connection:
    """
    Create (or re-create) the dummy SQLite database
    with all three platform schemas and sample data.

    Args:
        db_path: File path for the database.
                 Defaults to ``DUMMY_DB_PATH``.

    Returns:
        An open ``sqlite3.Connection``.
    """
    if db_path is None:
        db_path = DUMMY_DB_PATH

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.executescript(_DATABRICKS_DDL)
    cursor.executescript(_SNOWFLAKE_DDL)
    cursor.executescript(_BIGQUERY_DDL)

    conn.commit()
    LOGGER.info(
        "Dummy database created at %s with all tables.",
        db_path,
    )
    return conn
