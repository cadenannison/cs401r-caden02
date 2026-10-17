# cs401r-lab1-template
CS 401R Lab 1: Platform Foundation — starter template (do not fork directly)

## Lab 2 — Data Pipeline & Feature Store

### New modules

- `infrastructure/modules/glue` — Glue catalog database, raw-zone crawler,
  a VPC NETWORK connection for Glue jobs, the transform job, the
  feature-engineer job, and S3 uploads of the job scripts.
- `infrastructure/modules/feature_store` — SageMaker Feature Group with 16
  feature definitions, backed by both an online store and an offline store.

### Lab 2 changes to existing modules

- `vpc` — adds a private subnet, a NAT gateway for outbound access from that
  subnet, and a self-referencing security group rule so resources in the
  subnet can reach each other.
- `iam` — adds the `DataEngineer` and `ModelMonitor` roles alongside the
  existing `MLEngineer` role.
- `storage` — adds 5 S3 lifecycle rules (expire-raw-data,
  expire-raw-versions, expire-processed-versions, expire-feature-versions,
  expire-datacapture).
- `sagemaker` — the domain now runs in the private subnet with
  `AppNetworkAccessType = VpcOnly`.

### Running the pipeline end to end

From `infrastructure/environments/dev`:

```
terraform apply
```

Then, from the repo root:

```
aws s3 cp northstar-raw-sample.csv s3://<bucket>/raw/customers/
aws glue start-crawler northstar-dev-raw-crawler
aws glue start-job-run --job-name northstar-dev-transform
aws glue start-job-run --job-name northstar-dev-feature-engineer
bash scripts/verify-lab2.sh
```

Run the transform job and wait for it to finish before starting the
feature-engineer job — the feature-engineer job reads the transform job's
output. `verify-lab2.sh` checks the same assertions used for grading and
prints PASS/FAIL for each one.

### Teardown

```
bash scripts/teardown-lab2.sh
```

`terraform destroy` alone is not enough — the teardown script also clears
state the pipeline creates outside Terraform (e.g. feature store records and
crawled catalog data) before destroying infrastructure.

### Evidence

See `docs/` for supporting evidence, including:

- `lab2-data-contract.md`
- `lab2-data-lineage.png`
- `docs/evidence/screenshots/lab2-domain.png`
- `docs/evidence/screenshots/lab2-featuregroup.png`
- `docs/evidence/screenshots/lab2-nat.png`
- `lab2-glue-apply-output.txt`
- `lab2-feature-apply-output.txt`
- `lab2-verify-output.txt`


## Lab 3: Model Development

### Prerequisites
- A SageMaker **MLflow App** named `northstar-mlflow`; its ARN goes in `MLFLOW_APP_ARN`.
- Python packages: `xgboost scikit-learn pandas pyarrow matplotlib mlflow sagemaker-mlflow boto3 faiss-cpu ragas datasets "langchain-community<0.4" langchain-aws` and `sagemaker>=2.200,<3`.

### Train (Task 1)
```bash
export MLFLOW_APP_ARN=arn:aws:sagemaker:us-east-1:<account>:mlflow-app/<app-id>
python churn_training_skeleton.py \
  --artifacts-bucket <bucket from terraform output s3_bucket_name> \
  --run-name xgb-final-shallow-slow \
  --max-depth 4 --eta 0.05 --num-round 400 \
  --output-data-dir docs/lab3-evidence --register 2>&1 | tee docs/lab3-evidence/train-final.log
```
All hyperparameters are CLI arguments. `--include-risk-score` adds `churn_risk_score` (off by default; used for the ablation). `--register` registers the model as `PendingManualApproval`. `--local-data-path` is for development only; the graded run reads from Athena.

### Evaluate (Track B)
```
python evaluation_harness.py  
```
Copy the final CSV to `docs/lab3-evidence/rag_eval.csv`. The RAG pipeline is in `rag/offer_pipeline.py` (FAISS, Titan Embeddings v2, Claude Haiku 4.5 via Bedrock).

### Where artifacts land
- `docs/lab3-evidence/`: `train-final.log`, `evaluation_metrics.json`, `slice-evaluation.csv`, `confusion-matrix.png`, `feature-importance.png`, plus the AWS exports from the evidence script, `rag_eval.csv` and `track-b-examples.md`.
- `docs/lab3-evaluation-report.md`, `docs/lab3-model-design.md`.
- Model tarball: `s3://<bucket>/artifacts/models/<timestamp>/model.tar.gz`; registry group `northstar-churn-models`.
- MLflow runs: experiment `northstar-churn` in the `northstar-mlflow` App.
