# Data Contract: processed/customers

## Producer
Glue ETL job `northstar-dev-transform` (role `northstar-dev-DataEngineer`). Reads catalog table `northstar_dev.customers`, writes Parquet to `s3://northstar-dev-data-<account-id>/processed/customers/`.

## Consumers
- Feature engineering job `northstar-dev-feature-engineer`
- (Future) Direct model training in Lab 3

## Grain
One row per transaction. A customer appears on many rows. Collapsing to one row per customer happens downstream in the feature engineering job.

## Schema
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| transaction_id | string | No | Natural key, format `TXN-{12 alphanumeric}`. Unique across the dataset. |
| customer_id | string | No | Format `CUST-{8 digits}`. Repeats across rows by design. |
| purchase_date | date | No | ISO 8601 (`yyyy-MM-dd`); source `MM/dd/yyyy` values are normalized. Observed range 2025-04-01 to 2026-06-30. |
| order_value | double | No | Gross order value in USD. Observed range 15.00 to 620.00. Null source values imputed with the median (141.75). |
| num_items | int | No | Line items in the order. Observed range 1 to 9. Null source values imputed with the rounded median (5). |
| payment_method | string | No | `credit_card`, `debit_card`, `gift_card`, `cash`, or `unknown` (imputed). |
| channel | string | No | `store`, `online`, or `unknown` (imputed). |
| store_id | string | No | `STORE-{3 digits}`, `ONLINE`, or `unknown` (imputed). |
| product_category | string | No | Primary category, or `unknown` (imputed). Consumers must exclude `unknown` when counting distinct categories. |

## Quality Guarantees
- `customer_id` is never null (0 nulls; asserted in the job and checked by `scripts/verify-lab2.sh`).
- No duplicate `transaction_id` rows (0 duplicates). A `customer_id` repeating across rows is expected, not a defect.
- `purchase_date` is a valid ISO 8601 date on every row (0 nulls), between 2025-04-01 and 2026-06-30. Both `yyyy-MM-dd` and `MM/dd/yyyy` source formats are parsed.
- `order_value` is between 15.00 and 620.00 USD (observed; not enforced by the job).
- `num_items` is an integer between 1 and 9 (observed; not enforced by the job).
- No null values in any column (0 nulls across all columns).
- Whitespace is trimmed on every column.
- Transaction-level grain is preserved: 157,627 rows across 9,999 customers (2026-10-02 run).
- The job fails rather than write output if the first three guarantees are violated.
- Observed ingest figures: 163,255 raw rows, 3,265 dropped for null `customer_id`, 2,363 duplicates removed, 157,627 rows written.

## SLA
- Data is available in `processed/customers/` within 2 hours of landing in `raw/customers/`, after the crawler has registered the table.
- Observed transform run time: about 2 minutes (121 s) for about 163,000 rows.
- Reprocessing is idempotent: the job overwrites the output prefix.

## Versioning
- Schema changes require a new S3 prefix (for example `processed/customers/v2/`).
- Breaking changes (removed or renamed columns, type changes, grain changes) require consumer notification 5 business days in advance.
- Additive, non-breaking columns may be added to the existing prefix with notice to consumers.
