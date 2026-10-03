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
