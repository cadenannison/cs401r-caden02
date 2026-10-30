"""
Pure pandas/numpy port of the Lab 2 feature logic (glue-scripts/feature_engineer.py).

No pyspark, boto3 or AWS dependency, so the logic can be unit tested in isolation.
Every function reproduces the Glue job exactly:

  * History is purchase_date <= snapshot_date (FEATURE_CUTOFF, 2026-04-01 in Lab 2).
    Rows after the cutoff are the holdout and never contribute to a feature.
  * "Within N days" means datediff(T, purchase_date) < N, i.e. purchase_date > T - N.
    Dates are compared at day granularity (time-of-day is dropped, like Spark's DATE).
  * avg_basket_size_6m is ITEMS per order over 180 days, not dollars.
  * category_diversity_score excludes 'unknown' and divides by N_CATEGORIES = 8.
  * Loyalty tiers: Bronze < 500 <= Silver < 2000 <= Gold < 5000 <= Platinum (on LTV).

Null-filling strategy
---------------------
The Glue job aggregates over customers that HAVE history, so it never emits a null for
them except where an aggregate has nothing to average. Here every function can also be
asked about customers with no (in-window) transactions, so nulls are filled with fixed,
documented defaults instead of being left as NaN:

  days_since_last_purchase    999.0   sentinel: "never bought" reads as maximally dormant
  customer_tenure_days        0.0     no first purchase, so no tenure
  purchase_frequency_*        0.0     no orders in the window
  avg_order_value             0.0     no orders to average (all-null order_value too)
  total_spend_90d             0.0     empty sum
  total_lifetime_value        0.0     empty sum
  avg_basket_size_6m          0.0     matches Glue's coalesce(avg(...), 0.0)
  category_diversity_score    0.0     no known category
  online_to_store_ratio       0.0     no orders, so no online share

Null order_value / num_items cells inside a customer's history are skipped by the
aggregates (pandas and Spark both ignore them), they are not imputed to zero.
"""

import numpy as np
import pandas as pd

TIER_BRONZE_MAX = 500.0
TIER_SILVER_MAX = 2000.0
TIER_GOLD_MAX = 5000.0

RISK_HIGH_LO, RISK_HIGH_HI = 0.7, 1.0
RISK_MED_LO, RISK_MED_HI = 0.4, 0.7
RISK_LOW_LO, RISK_LOW_HI = 0.0, 0.4

FEATURE_CUTOFF = "2026-04-01"
N_CATEGORIES = 8.0
NO_PURCHASE_SENTINEL = 999.0

_ROUNDED_COLUMNS = ["avg_order_value", "total_lifetime_value", "total_spend_90d",
                    "avg_basket_size_6m", "category_diversity_score",
                    "online_to_store_ratio"]


def _to_day(value):
    return pd.Timestamp(value).normalize()


def _history(transactions, snapshot_date):
    """Rows on or before the cutoff, with a day-normalised purchase_date and age_days."""
    T = _to_day(snapshot_date)
    df = transactions.copy()
    df["purchase_date"] = pd.to_datetime(df["purchase_date"]).dt.normalize()
    df = df[df["purchase_date"] <= T].copy()
    df["age_days"] = (T - df["purchase_date"]).dt.days
    return df


def _ids(customer_ids):
    """Accept a DataFrame with customer_id, a Series, or any iterable of ids."""
    if customer_ids is None:
        return None
    if isinstance(customer_ids, pd.DataFrame):
        customer_ids = customer_ids["customer_id"]
    return pd.Index(pd.unique(pd.Series(list(customer_ids))), name="customer_id")


def _reindex(frame, ids, defaults):
    """Restrict/extend to `ids` (if given) and fill nulls with the documented defaults."""
    if ids is not None:
        frame = frame.reindex(ids)
    frame = frame.fillna(defaults)
    return frame.astype("float64").rename_axis("customer_id").reset_index()


def compute_recency_features(transactions_df, snapshot_date, customer_ids=None):
    """days_since_last_purchase per customer; 999 when there is no in-window purchase.

    With customer_ids, the output has exactly those customers (absent ones get 999).
    Without it, only customers with history appear.
    """
    h = _history(transactions_df, snapshot_date)
    last = h.groupby("customer_id")["age_days"].min().rename("days_since_last_purchase")
    return _reindex(last.to_frame(), _ids(customer_ids),
                    {"days_since_last_purchase": NO_PURCHASE_SENTINEL})


def compute_tenure_features(transactions_df, snapshot_date, customer_ids=None):
    """customer_tenure_days: T minus the customer's first purchase (0 when none)."""
    h = _history(transactions_df, snapshot_date)
    first = h.groupby("customer_id")["age_days"].max().rename("customer_tenure_days")
    return _reindex(first.to_frame(), _ids(customer_ids), {"customer_tenure_days": 0.0})


def compute_frequency_features(transactions_df, snapshot_date, customer_ids=None):
    """Order counts in the 30/90/180 days before T (datediff < N)."""
    h = _history(transactions_df, snapshot_date)
    out = pd.DataFrame(index=pd.Index(h["customer_id"].unique(), name="customer_id"))
    for n in (30, 90, 180):
        out[f"purchase_frequency_{n}d"] = (
            (h["age_days"] < n).groupby(h["customer_id"]).sum()
        )
    return _reindex(out, _ids(customer_ids),
                    {f"purchase_frequency_{n}d": 0.0 for n in (30, 90, 180)})


def compute_monetary_features(transactions_df, snapshot_date, customer_ids=None):
    """avg_order_value (all history), total_spend_90d, avg_basket_size_6m (items/order, 180d)."""
    h = _history(transactions_df, snapshot_date)
    out = pd.DataFrame(index=pd.Index(h["customer_id"].unique(), name="customer_id"))
    out["avg_order_value"] = pd.to_numeric(h["order_value"]).groupby(h["customer_id"]).mean()
    in90 = h["age_days"] < 90
    out["total_spend_90d"] = (
        pd.to_numeric(h["order_value"]).where(in90, 0.0).groupby(h["customer_id"]).sum()
    )
    in180 = h["age_days"] < 180
    out["avg_basket_size_6m"] = (
        pd.to_numeric(h["num_items"]).where(in180).groupby(h["customer_id"]).mean()
    )
    return _reindex(out, _ids(customer_ids),
                    {"avg_order_value": 0.0, "total_spend_90d": 0.0,
                     "avg_basket_size_6m": 0.0})


def compute_behavioral_features(transactions_df, customer_ids=None, snapshot_date=None):
    """category_diversity_score and online_to_store_ratio.

    Pass snapshot_date to restrict to history (<= T); build_churn_feature_set does.
    Called with only transactions it uses every row it is given.
    """
    if snapshot_date is not None:
        h = _history(transactions_df, snapshot_date)
    else:
        h = transactions_df
    known = h["product_category"].where(h["product_category"] != "unknown")
    out = pd.DataFrame(index=pd.Index(h["customer_id"].unique(), name="customer_id"))
    out["category_diversity_score"] = known.groupby(h["customer_id"]).nunique() / N_CATEGORIES
    out["online_to_store_ratio"] = (
        (h["channel"] == "online").astype("float64").groupby(h["customer_id"]).mean()
    )
    return _reindex(out, _ids(customer_ids),
                    {"category_diversity_score": 0.0, "online_to_store_ratio": 0.0})


def assign_loyalty_tier(df):
    """Bronze/Silver/Gold/Platinum from total_lifetime_value."""
    ltv = df["total_lifetime_value"]
    df = df.copy()
    df["loyalty_tier"] = np.select(
        [ltv < TIER_BRONZE_MAX, ltv < TIER_SILVER_MAX, ltv < TIER_GOLD_MAX],
        ["Bronze", "Silver", "Gold"],
        default="Platinum",
    )
    return df


def compute_churn_proxy(df):
    """Rule-based churn_risk_score in [0, 1] (the baseline, not the label)."""
    d = df["days_since_last_purchase"]
    high = (d > 60) & (df["purchase_frequency_30d"] == 0)
    score = np.where(
        high,
        RISK_HIGH_LO + (RISK_HIGH_HI - RISK_HIGH_LO) * np.minimum((d - 60) / 120, 1.0),
        np.where(
            d > 30,
            RISK_MED_LO + (RISK_MED_HI - RISK_MED_LO) * np.minimum((d - 30) / 30, 1.0),
            RISK_LOW_HI * np.minimum(d / 30, 1.0),
        ),
    )
    df = df.copy()
    df["churn_risk_score"] = np.clip(score, 0.0, 1.0)
    return df


def build_churn_feature_set(customers, transactions, snapshot_date):
    """One row per customer in `customers`, features measured back from snapshot_date.

    Customers with no history get the defaults in the module docstring. A churn_label
    column on `customers` is carried through; the label is never derived here.
    """
    ids = _ids(customers)
    frames = [
        compute_recency_features(transactions, snapshot_date, ids),
        compute_tenure_features(transactions, snapshot_date, ids),
        compute_frequency_features(transactions, snapshot_date, ids),
        compute_monetary_features(transactions, snapshot_date, ids),
        compute_behavioral_features(transactions, ids, snapshot_date),
    ]
    h = _history(transactions, snapshot_date)
    ltv = (pd.to_numeric(h["order_value"]).groupby(h["customer_id"]).sum()
           .reindex(ids).fillna(0.0).astype("float64").rename("total_lifetime_value")
           .reset_index())
    features = ids.to_frame(index=False)
    for f in frames + [ltv]:
        features = features.merge(f, on="customer_id", how="left")

    features = assign_loyalty_tier(features)
    features = compute_churn_proxy(features)
    for col in _ROUNDED_COLUMNS:
        features[col] = features[col].round(4)
    if isinstance(customers, pd.DataFrame) and "churn_label" in customers.columns:
        features = features.merge(customers[["customer_id", "churn_label"]]
                                  .drop_duplicates("customer_id"),
                                  on="customer_id", how="left")
    return features
