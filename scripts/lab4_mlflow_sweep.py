"""Lab 4 MLflow hyperparameter sweep.

Runs models/churn/churn_model.train() once per hyperparameter combo and logs each
run to the SageMaker MLflow App named by MLFLOW_APP_ARN. A combo that trips the
evaluation gate (ValueError) is logged with gate_failed=true and no metrics
rather than crashing the sweep.

Needs `pip install mlflow sagemaker-mlflow pyarrow` locally (see the warning in
churn_training_skeleton.track_run about SigV4 auth and the Tracking Server cost).

Usage:
    export MLFLOW_APP_ARN=arn:aws:sagemaker:us-east-1:<account>:mlflow-app/app-XXXX
    python scripts/lab4_mlflow_sweep.py --features-dir <dir of feature parquet files>

Writes docs/lab4-mlflow-runs.txt.
"""

import argparse
import os
import sys
from pathlib import Path

import mlflow
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "models" / "churn"))
import churn_model  # noqa: E402

EXPERIMENT = "northstar-churn-lab4"
SEED = 42
OUTPUT_PATH = REPO_ROOT / "docs" / "lab4-mlflow-runs.txt"

# (max_depth, eta, num_round). The first is the graded Lab 3 configuration.
# Each (max_depth, eta) pair is unique so the run names are too.
COMBOS = [
    (4, 0.05, 400),
    (6, 0.1, 200),
    (3, 0.1, 300),
    (5, 0.03, 600),
    (8, 0.2, 100),
]

METRIC_KEYS = [
    "auc_roc", "baseline_auc_roc", "precision_top10", "recall_top10",
    "lift_ci_low", "lift_ci_high",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Lab 4 churn MLflow sweep")
    parser.add_argument("--features-dir", required=True,
                        help="Local directory holding the feature parquet file(s)")
    return parser.parse_args()


def load_features(features_dir: str) -> pd.DataFrame:
    files = sorted(Path(features_dir).rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No .parquet files under {features_dir}")
    print(f"Loading {len(files)} parquet file(s) from {features_dir}")
    return pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)


def run_combo(df: pd.DataFrame, max_depth: int, eta: float, num_round: int) -> None:
    run_name = f"depth{max_depth}-eta{eta}"
    saved = (churn_model.MAX_DEPTH, churn_model.ETA, churn_model.NUM_ROUND)
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "max_depth": max_depth,
            "eta": eta,
            "num_round": num_round,
            "seed": SEED,
        })
        churn_model.MAX_DEPTH, churn_model.ETA, churn_model.NUM_ROUND = max_depth, eta, num_round
        try:
            _, metrics = churn_model.train(df, seed=SEED)
        except ValueError as e:
            print(f"{run_name}: gate failed: {e}")
            mlflow.set_tag("gate_failed", "true")
            return
        finally:
            churn_model.MAX_DEPTH, churn_model.ETA, churn_model.NUM_ROUND = saved
        mlflow.set_tag("gate_failed", "false")
        mlflow.log_metrics({k: float(metrics[k]) for k in METRIC_KEYS})
    print(f"{run_name}: logged")


def main():
    args = parse_args()
    arn = os.environ["MLFLOW_APP_ARN"]
    mlflow.set_tracking_uri(arn)
    mlflow.set_experiment(EXPERIMENT)

    df = load_features(args.features_dir)
    for max_depth, eta, num_round in COMBOS:
        run_combo(df, max_depth, eta, num_round)

    runs = mlflow.search_runs(experiment_names=[EXPERIMENT])
    cols = ["run_id", "tags.mlflow.runName", "start_time"] + [
        c for c in runs.columns if c.startswith(("params.", "metrics."))
    ]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(f"tracking_uri: {mlflow.get_tracking_uri()}\n\n")
        f.write(runs[cols].to_string())
        f.write("\n")
    print(f"✓ Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
