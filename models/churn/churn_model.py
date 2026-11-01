"""Lab 3 churn model packaged for the Lab 4 pipeline. train_sagemaker.py imports this module and calls train(df, seed) -> (booster, metrics). Only models/churn/ is uploaded to the training container, so this file must not import mlflow or sagemaker at the top level."""

# Keeps Lab 3 annotations like `-> tuple[np.ndarray, np.ndarray]` from being
# evaluated, whatever Python the training container runs.
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

# Must match the columns your Lab 3 model was trained on, in the same order.
FEATURE_COLUMNS = [
    "days_since_last_purchase",
    "customer_tenure_days",
    "purchase_frequency_30d",
    "purchase_frequency_90d",
    "purchase_frequency_180d",
    "avg_order_value",
    "total_spend_90d",
    "total_lifetime_value",
    "avg_basket_size_6m",
    "category_diversity_score",
    "online_to_store_ratio",
]

LABEL = "churn_label"

# The recency-only baseline model uses just this one feature.
BASELINE_FEATURE = "days_since_last_purchase"

# Not a feature: the column the per-tier recall groups by.
SLICE_COLUMN = "loyalty_tier"

# Lab 3 XGBoost hyperparameters (graded run xgb-final-shallow-slow).
# NUM_ROUND is the max rounds; early stopping (20) usually halts sooner.
MAX_DEPTH = 4
ETA = 0.05
NUM_ROUND = 400
MIN_CHILD_WEIGHT = 5
SUBSAMPLE = 0.8
COLSAMPLE_BYTREE = 0.8

EVAL_THRESHOLDS = {
    "precision_top10": 0.50,   # Minimum precision @ top 10% scored customers
    "recall_top10": 0.25,      # Minimum recall @ top 10% scored customers
}
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 42


def preprocess_features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return (X, y). Rows with a missing label must be filtered by the caller
    first so df, X and y stay row-aligned for the tier split."""
    # Sentinel -1 for missing feature values, so "missing" is distinguishable
    # from any real (non-negative) value.
    X = df[FEATURE_COLUMNS].fillna(-1).values
    y = df[LABEL].values.astype(int)
    print(f"Preprocessing {len(df):,} samples...")
    print(f"  Positive class rate: {y.mean():.1%}")
    print(f"  Feature matrix shape: {X.shape}")
    return X, y


def train_model(X_train: np.ndarray,
                y_train: np.ndarray,
                X_val: np.ndarray,
                y_val: np.ndarray,
                seed: int = 42) -> xgb.Booster:
    """Train the XGBoost churn model."""
    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_COLUMNS)
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=FEATURE_COLUMNS)

    # Class imbalance, computed from the training split.
    spw = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))

    params = {
        # eval_metric ORDER MATTERS: XGBoost early-stops on the LAST metric.
        # Keep "auc" last (Lab 3 defect 49).
        "objective": "binary:logistic",
        "eval_metric": ["logloss", "auc"],
        "max_depth": MAX_DEPTH,
        "eta": ETA,
        "min_child_weight": MIN_CHILD_WEIGHT,
        "subsample": SUBSAMPLE,
        "colsample_bytree": COLSAMPLE_BYTREE,
        "scale_pos_weight": spw,
        "seed": seed,
        "verbosity": 1,
    }
    print(f"\nTraining XGBoost with params: {json.dumps(params, indent=2)}")

    return xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=NUM_ROUND,
        evals=[(dtrain, "train"), (dval, "validation")],
        early_stopping_rounds=20,
        verbose_eval=25,
    )


def train_recency_baseline(X_train: np.ndarray,
                           y_train: np.ndarray,
                           X_val: np.ndarray,
                           seed: int = 42) -> np.ndarray:
    """Train the recency-only baseline and score the validation split.

    A model over `days_since_last_purchase` ALONE, trained on the same training
    rows and scored on the same validation rows as the full model.
    """
    i = FEATURE_COLUMNS.index(BASELINE_FEATURE)
    dtr = xgb.DMatrix(X_train[:, [i]], label=y_train, feature_names=[BASELINE_FEATURE])
    dva = xgb.DMatrix(X_val[:, [i]], feature_names=[BASELINE_FEATURE])
    spw = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    params = {
        "objective": "binary:logistic", "eval_metric": "auc",
        "max_depth": 4, "eta": 0.1, "subsample": 0.9,
        "colsample_bytree": 0.9, "scale_pos_weight": spw, "seed": seed,
    }
    return xgb.train(params, dtr, num_boost_round=200).predict(dva)


def bootstrap_lift_ci(y_true: np.ndarray,
                      proba: np.ndarray,
                      baseline_proba: np.ndarray,
                      n: int = BOOTSTRAP_N,
                      seed: int = BOOTSTRAP_SEED,
                      alpha: float = 0.05) -> tuple[float, float]:
    """Paired percentile CI for (model AUC - baseline AUC), resampling the val set.

    Single-class replicates are skipped (AUC undefined). Seed is fixed so the
    same split always produces the same verdict.
    """
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true)
    idx = np.arange(len(y_true))
    diffs = []
    for _ in range(n):
        s = rng.choice(idx, size=len(idx), replace=True)
        ys = y_true[s]
        if len(np.unique(ys)) < 2:
            continue
        diffs.append(roc_auc_score(ys, proba[s]) - roc_auc_score(ys, baseline_proba[s]))
    if len(diffs) < n // 2:
        raise ValueError(
            "Too few usable bootstrap replicates to form a confidence interval. "
            "Your validation set is too small or too imbalanced to support this gate."
        )
    d = np.sort(diffs)
    return float(np.quantile(d, alpha / 2)), float(np.quantile(d, 1 - alpha / 2))


def top10_cutoff(y_pred_proba: np.ndarray) -> float:
    """Score cutoff for the top 10% of customers; shared by precision/recall@10%
    and the per-tier recall."""
    return float(np.percentile(y_pred_proba, 90))


def predict_val(model: xgb.Booster, X_val: np.ndarray) -> np.ndarray:
    return model.predict(xgb.DMatrix(X_val, feature_names=model.feature_names))


def recall_by_tier(y_val: np.ndarray,
                   y_pred_proba: np.ndarray,
                   tiers: np.ndarray) -> dict:
    """Recall at the SAME global top-10% cutoff as recall_top10, per tier.
    A tier with no positives has undefined recall and is reported as None."""
    selected = y_pred_proba >= top10_cutoff(y_pred_proba)
    out = {}
    for tier in sorted(pd.unique(tiers), key=str):
        mask = tiers == tier
        positives = int(y_val[mask].sum())
        out[str(tier)] = (round(float((selected & mask & (y_val == 1)).sum() / positives), 4)
                          if positives > 0 else None)
    return out


def evaluate_model(model: xgb.Booster,
                   X_val: np.ndarray,
                   y_val: np.ndarray,
                   baseline_proba: np.ndarray,
                   tier_val: np.ndarray) -> dict:
    """Evaluate against the gates and return metrics. RAISES ValueError if any
    gate fails, so the training step fails and the model is never registered."""
    y_val = np.asarray(y_val)
    y_pred_proba = predict_val(model, X_val)

    auc_roc = roc_auc_score(y_val, y_pred_proba)

    top10_mask = y_pred_proba >= top10_cutoff(y_pred_proba)
    precision_top10 = y_val[top10_mask].mean() if top10_mask.sum() > 0 else 0.0
    recall_top10 = y_val[top10_mask].sum() / y_val.sum() if y_val.sum() > 0 else 0.0

    baseline_auc = roc_auc_score(y_val, baseline_proba)
    lift_ci_low, lift_ci_high = bootstrap_lift_ci(y_val, y_pred_proba, baseline_proba)

    metrics = {
        "auc_roc": round(float(auc_roc), 4),
        "precision_top10": round(float(precision_top10), 4),
        "recall_top10": round(float(recall_top10), 4),
        "auc_vs_baseline": round(float(auc_roc - baseline_auc), 4),
        "baseline_auc_roc": round(float(baseline_auc), 4),
        "baseline_auc": round(float(baseline_auc), 4),  # Lab 3 name, kept for compatibility
        "lift_ci_low": round(float(lift_ci_low), 4),
        "lift_ci_high": round(float(lift_ci_high), 4),
        "positive_rate_val": round(float(y_val.mean()), 4),
        "n_val_samples": int(len(y_val)),
        "recall_by_tier": recall_by_tier(y_val, y_pred_proba, np.asarray(tier_val, dtype=object)),
        "eval_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print("\n── Evaluation Results ──────────────────────────────")
    failures = []
    for metric, threshold in EVAL_THRESHOLDS.items():
        value = metrics[metric]
        status = "✓ PASS" if value >= threshold else "✗ FAIL"
        print(f"  {metric:25s}: {value:.4f}  (threshold: {threshold:.4f})  {status}")
        if value < threshold:
            failures.append(f"{metric}={value:.4f} < {threshold}")

    ci_status = "✓ PASS" if lift_ci_low > 0 else "✗ FAIL"
    print(f"  {'auc_lift 95% CI':25s}: [{lift_ci_low:.4f}, {lift_ci_high:.4f}]"
          f"  (must exclude 0)  {ci_status}")
    if lift_ci_low <= 0:
        failures.append(
            f"auc_lift 95% CI [{lift_ci_low:.4f}, {lift_ci_high:.4f}] includes "
            f"zero - no evidence the model beats the recency-only baseline")

    print(f"  recall_by_tier: {metrics['recall_by_tier']}")

    if failures:
        raise ValueError(
            f"Model failed evaluation thresholds: {'; '.join(failures)}. "
            f"Do not promote to Model Registry."
        )
    print("  All thresholds passed ✓")
    return metrics


def train(df: pd.DataFrame, seed: int = 42):
    """Train the churn model on `df` and return (booster, metrics).

    Raises ValueError (from evaluate_model) if a quality gate fails.
    """
    # Filter null labels FIRST so df, X and y stay row-aligned.
    df = df[df[LABEL].notna()].reset_index(drop=True)
    if SLICE_COLUMN not in df.columns:
        print(f"WARNING: '{SLICE_COLUMN}' missing; per-tier recall will use a single 'unknown' tier")
        df[SLICE_COLUMN] = "unknown"
    X, y = preprocess_features(df)

    # The tier goes through the same split call so it lines up with X and y.
    X_train, X_val, y_train, y_val, tier_train, tier_val = train_test_split(
        X, y, df[SLICE_COLUMN], stratify=y, test_size=0.30, random_state=seed
    )
    print(f"\nTrain: {len(X_train):,} | Validation: {len(X_val):,}")

    model = train_model(X_train, y_train, X_val, y_val, seed=seed)
    baseline_proba = train_recency_baseline(X_train, y_train, X_val, seed=seed)
    metrics = evaluate_model(model, X_val, y_val, baseline_proba, tier_val.to_numpy(dtype=object))
    return model, metrics
