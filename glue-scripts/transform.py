"""
Glue ETL: raw/customers/ -> processed/customers/

Reads the crawler-registered catalog table, enforces types, imputes nulls,
removes duplicate transactions, and writes Parquet to the processed zone.

Grain note: this job is transaction-level in and transaction-level out. One
row per purchase, many rows per customer. The feature engineering job is
what collapses to one row per customer. Deduplicating on customer_id here
would destroy the purchase history that RFM features are computed from.

Job arguments (wired by Terraform in modules/glue):
  --database_name  Glue catalog database
  --table_name     catalog table produced by the crawler
  --output_path    s3:// destination for Parquet output
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Target types for the processed zone. The crawler infers everything from CSV
# as string, so every one of these is an explicit cast, not a no-op.
SCHEMA = {
    "transaction_id": "string",
    "customer_id": "string",
    "purchase_date": "date",
    "order_value": "double",
    "num_items": "int",
    "payment_method": "string",
    "channel": "string",
    "store_id": "string",
    "product_category": "string",
}

NUMERIC_COLS = ["order_value", "num_items"]
STRING_COLS = ["payment_method", "channel", "store_id", "product_category"]


def cast_types(df):
    """Cast every column to its SCHEMA type. Drop rows with no customer_id.

    Three things to handle, in this order:

    1. TRIM whitespace on every column first. A customer_id of
       "  CUST-10000001 " is not null, but it will not group or join
       correctly either, and the bug is invisible until your feature
       counts come out slightly wrong.
    2. Convert empty strings to real nulls. CSV gives you "" where you
       want None; Spark treats those as different things.
    3. Parse purchase_date. Most rows are ISO 8601 (yyyy-MM-dd) but a few
       percent are MM/dd/yyyy. F.to_date returns null on a format
       mismatch instead of raising, so parse both formats and coalesce.
       If you only parse the ISO form you will silently null out the
       other rows and then drop them.

    Finally, drop rows where customer_id is null. That column is the join
    key for every downstream feature, so a row without it cannot be
    attributed to anyone.
    """
    spark = df.sparkSession
    # yyyy-MM-dd and MM/dd/yyyy both parse under CORRECTED without raising on
    # the mismatched format; LEGACY/EXCEPTION policies can throw instead.
    spark.conf.set("spark.sql.legacy.timeParserPolicy", "CORRECTED")

    df = df.select(*SCHEMA.keys())
    for col in SCHEMA:
        # cast to string first so trim/empty-string handling is uniform
        # regardless of the column's eventual target type.
        df = df.withColumn(col, F.trim(F.col(col).cast("string")))
        df = df.withColumn(
            col, F.when(F.col(col) == "", None).otherwise(F.col(col))
        )

    # try ISO first, then US format; to_date returns null rather than
    # raising on a mismatch, so coalesce picks whichever one parsed.
    df = df.withColumn(
        "purchase_date",
        F.coalesce(
            F.to_date(F.col("purchase_date"), "yyyy-MM-dd"),
            F.to_date(F.col("purchase_date"), "MM/dd/yyyy"),
        ),
    )

    for col, dtype in SCHEMA.items():
        if col == "purchase_date":
            continue
        if dtype == "int":
            # cast through double first: a string like "3.0" fails a direct
            # cast to int but succeeds through double.
            df = df.withColumn(col, F.col(col).cast("double").cast("int"))
        elif dtype == "double":
            df = df.withColumn(col, F.col(col).cast("double"))
        # strings are already strings after the trim/empty-string pass above

    df = df.filter(F.col("customer_id").isNotNull())

    before_date_filter = df.count()
    df = df.filter(F.col("purchase_date").isNotNull())
    dropped = before_date_filter - df.count()
    print(f"[transform] dropped {dropped} rows with unparseable purchase_date")

    return df.select(*SCHEMA.keys())


def impute_nulls(df):
    """Numeric columns -> column median. String columns -> 'unknown'.

    Use the MEDIAN, not the mean. order_value is right-skewed: a handful
    of large orders drags a mean-imputed value well above the typical
    order and quietly inflates every monetary feature you compute later.

    DataFrame.approxQuantile(col, [0.5], 0.0) gives you an exact median.
    Remember num_items is an integer column - round before you fill it.

    Numeric columns: NUMERIC_COLS.  String columns: STRING_COLS.
    """
    int_cols = {c for c, t in SCHEMA.items() if t == "int"}
    for col in NUMERIC_COLS:
        median = df.approxQuantile(col, [0.5], 0.0)
        if not median:
            raise ValueError(f"approxQuantile returned no median for {col}")
        value = median[0]
        if col in int_cols:
            value = round(value)
        print(f"[transform] imputing {col} nulls with median {value}")
        df = df.fillna({col: value})

    for col in STRING_COLS:
        df = df.fillna({col: "unknown"})

    return df


def deduplicate(df):
    """Keep one row per transaction_id.

    Deduplicate on transaction_id, NOT on customer_id. A customer is
    expected to have many transactions - that purchase history is exactly
    what the feature engineering job aggregates over in Task 3.
    Collapsing to one row per customer here makes total_lifetime_value
    and purchase_frequency_30d impossible to compute, and you will not
    discover it until Task 3 fails.

    Duplicates are ingestion artifacts: the same transaction landing twice
    from a retry. Break ties deterministically (for example by
    purchase_date descending, then order_value descending) so repeated
    runs produce the same output rather than depending on partition order.

    A window function with row_number() over a partition by transaction_id
    is the idiomatic approach.
    """
    # order_value desc breaks ties when purchase_date is also tied, so
    # re-running the job on the same input always keeps the same row.
    window = Window.partitionBy("transaction_id").orderBy(
        F.col("purchase_date").desc(),
        F.col("order_value").desc(),
        F.col("customer_id").asc(),
    )
    df = df.withColumn("rn", F.row_number().over(window))
    df = df.filter(F.col("rn") == 1).drop("rn")

    return df


def main():
    args = getResolvedOptions(
        sys.argv, ["JOB_NAME", "database_name", "table_name", "output_path"]
    )

    sc = SparkContext()
    glue_context = GlueContext(sc)
    spark = glue_context.spark_session
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    dyf = glue_context.create_dynamic_frame.from_catalog(
        database=args["database_name"],
        table_name=args["table_name"],
    )
    df = dyf.toDF()
    raw_count = df.count()
    print(f"[transform] read {raw_count} raw rows from "
          f"{args['database_name']}.{args['table_name']}")

    df = cast_types(df)
    after_cast = df.count()
    print(f"[transform] after cast_types: {after_cast} rows "
          f"({raw_count - after_cast} dropped for null customer_id)")

    df = impute_nulls(df)
    print(f"[transform] after impute_nulls: {df.count()} rows")

    df = deduplicate(df)
    final_count = df.count()
    print(f"[transform] after deduplicate: {final_count} rows "
          f"({after_cast - final_count} duplicate transactions removed)")

    # Fail loudly rather than writing a bad dataset the feature job will
    # silently consume. These are the same guarantees the data contract
    # published for processed/customers/, enforced at the producer.
    assert df.filter(F.col("customer_id").isNull()).count() == 0, \
        "null customer_id survived the transform"
    assert df.select("transaction_id").distinct().count() == final_count, \
        "duplicate transaction_id survived the transform"
    assert df.filter(F.col("purchase_date").isNull()).count() == 0, \
        "unparseable purchase_date survived the transform"

    (df.coalesce(4)
       .write
       .mode("overwrite")
       .parquet(args["output_path"]))
    print(f"[transform] wrote {final_count} rows to {args['output_path']}")

    job.commit()


if __name__ == "__main__":
    main()
