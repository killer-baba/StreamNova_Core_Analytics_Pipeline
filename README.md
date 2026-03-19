## Product Requirements Document (PRD): StreamNova Core Analytics Pipeline (Senior/Lead Edition)

---

### 1. Executive Summary
StreamNova is scaling rapidly. Our initial batch pipelines are failing under the weight of our new telemetry data, and our finance team's revenue reports are inaccurate due to complex subscription upgrades/downgrades. As our Lead Data Engineer, you are tasked with re-architecting our **Databricks + dbt Medallion pipeline** to handle massive scale, complex semi-structured data, and rigorous financial reporting standards.

---

### 2. Source Data Overview (The "V2" Stack)
The operational systems drop four raw CSV files into cloud storage daily:

* **customers.csv**: Customer demographic data (Mutable).
* **subscriptions.csv**: History of subscription plans.
* **payments.csv**: Transactional data for charges.
* **content_consumption.csv (NEW)**: High-volume, semi-structured telemetry data tracking every video play, pause, and stop. Contains massive data skew and nested JSON metadata.

---

### 3. Medallion Architecture & Complex SQL Requirements

#### 3.1. Bronze Layer (Raw Ingestion & Schema Evolution)
* **Goal**: Resilient ingestion.
* **Requirements**: Use **Databricks Auto Loader** to ingest data. You must configure **Schema Evolution** (using `_rescued_data` columns) to handle upstream systems arbitrarily adding new fields to the `content_consumption` JSON payload.

#### 3.2. Silver Layer (Cleansed, Incremental, & Sessionized)
* **Customers & Payments**: Cleanse types, deduplicate using `QUALIFY ROW_NUMBER() OVER (...) = 1`.
* **Events (stg_content_consumption)**: Parse the nested JSON `device_metadata` string to extract `os`, `app_version`, and `resolution` using Databricks native JSON extraction functions within dbt.
* **Advanced SQL Challenge 1: Event Sessionization (int_user_sessions)**:
    * **Requirement**: Raw telemetry events are just timestamps. You must group these events into discrete "Viewing Sessions".
    * **Logic**: Use `LAG()` window functions to calculate the time difference between events for a user. If the gap is **> 30 minutes**, generate a new `session_id` using a cumulative sum (`SUM(CASE WHEN...) OVER (...)`). Calculate total session duration.

#### 3.3. Gold Layer (Business Value & Point-in-Time Accuracy)
* **dim_customers (SCD Type 2)**: Maintained via dbt snapshots.
* **Advanced SQL Challenge 2: MRR Waterfall (mart_mrr_waterfall)**:
    * **Requirement**: Finance doesn't just want total revenue; they want a Month-over-Month MRR Waterfall.
    * **Logic**: Use CTEs and Window Functions (`LAG()`, `COALESCE()`) to compare a customer's revenue in Month N vs Month N-1. Categorize every user month into: **New, Expansion (upgraded plan), Contraction (downgraded plan), Retained, or Churned.**
* **Advanced SQL Challenge 3: Point-in-Time Customer 360 (mart_customer_360)**:
    * **Requirement**: Join the aggregated session data with the `dim_customers` snapshot. 
    * **Logic**: You must ensure you join the viewing session to the customer's demographic profile as it existed at the time of the viewing, not their current profile (using `valid_from` and `valid_to` date logic).

---

### 4. Advanced dbt & Production Scale Requirements

#### 4.1. Incremental Materializations (Mandatory for Scale)
* **Requirement**: The `stg_content_consumption` and `int_user_sessions` tables process millions of rows. They must be materialized as incremental.
* **Challenge**: Handle Late-Arriving Data. Use an incremental strategy (e.g., merge or `insert_overwrite` with partitions) that looks back **3 days** to update records that arrived out of order due to mobile offline caching.

#### 4.2. Pre/Post Hooks & Databricks Optimization
* **Requirement**: High-volume tables must be performant for BI queries.
* **Action**: Write a dbt post-hook macro that automatically runs `OPTIMIZE {{ this }} ZORDER BY (customer_id, event_date)` on your largest Gold tables after every run.

#### 4.3. Custom Generic Tests (Anomaly Detection)
* **Requirement**: Standard `not_null` tests aren't enough.
* **Action**: Write a custom dbt generic test called `test_row_count_anomaly`. It should fail if the daily volume of `content_consumption` drops by more than **20%** compared to the 7-day trailing average.

---

### 5. "Senior Level" Production Challenges (Interview Talking Points)
* **The "Mega-User" Data Skew**: There are bot accounts in `content_consumption.csv` generating 100x more events than normal users. Your Databricks joins might OOM (Out of Memory). Be prepared to discuss or implement **Salting** or **Broadcast joins**.
* **SCD2 Chronology Failures**: Upstream systems occasionally send a customer update timestamp (`updated_at`) that is older than the previous update. Ensure your snapshot strategy or downstream joins don't create overlapping `valid_from`/`valid_to` periods.
* **Currency Conversion on the Fly**: Payments arrive in USD, EUR, and GBP. Use a dbt macro and a seed file (`exchange_rates.csv`) to convert all revenue to USD at the exchange rate valid on the day of the transaction.

---

### 6. CI/CD: The "Zero Downtime" Deployment
* **Blue/Green Deployment**: Instead of overwriting prod tables directly, configure your dbt Databricks profile to use Blue/Green deployment or table cloning strategies.
* **Slim CI**: In GitHub Actions, configure `dbt run --select state:modified+ --defer --state ./prod-run-artifacts`. Explain how deferral saves money by reading upstream Prod tables for Dev testing.