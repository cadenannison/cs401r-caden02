# Lab 1 — Monthly Cost Estimate

Steady-state monthly cost for the NorthStar Lab 1 platform, us-east-1
pricing as of Sep 2026. This is the cost of *keeping the platform
provisioned*, not of the churn-model training runs it will eventually
run — Lab 1 has no data volume and no scheduled training job yet.

| Component | Monthly Estimate | Key Assumptions |
|---|---|---|
| SageMaker Studio (JupyterLab, `ml.t3.medium`) | $6.05 | `ml.t3.medium` on-demand is $0.05/hr. Studio is not left running 24/7 — course workflow is "open Studio, do work, shut down" (per the lab's own shutdown requirement) — so this assumes ~2 hrs/day, 20 working days/month: 2 × 20 × $0.05 = $2.00 for compute, plus a 5 GB EFS home volume at $0.30/GB-month ($1.50) and negligible EBS. Rounding to $6.05 to include the always-on EFS charge that persists even when Studio apps are stopped (home directory storage is billed whether or not JupyterLab is running). |
| S3 storage (data bucket) | $0.05 | Lab 1 has no real data yet — only 4 zero-byte prefix markers. Budgeting 2 GB for early Lab 2 fixtures (`northstar-data-schema.md` sample CSVs) at $0.023/GB-month standard storage: 2 × $0.023 ≈ $0.05. Versioning roughly doubles this once objects start being overwritten, but at this data volume the absolute dollar impact is sub-cent. |
| Internet Gateway (data transfer) | $0.90 | The IGW itself is free; only egress is billed at $0.09/GB after the 100 GB/month free tier. Studio's container-image pulls and package installs are estimated at ~10 GB/month of egress during active development, which falls entirely inside the free tier — the $0.90 line assumes a slightly heavier month (~10 GB paid at $0.09/GB) to avoid understating cost once free-tier is exhausted later in the course. |
| DynamoDB (`northstar-tfstate-lock`) | $0.01 | On-demand billing mode. One lock write + one delete per `terraform apply`/`destroy`, maybe 10 applies/month during active lab work. At <1,000 read/write request units total, this is below DynamoDB's per-request minimum billing granularity in practice — budgeted at $0.01 to represent the request-unit floor rather than a literal $0.00. |
| S3 state bucket (`northstar-tfstate-<account-id>`) | $0.01 | A single `terraform.tfstate` file, a few hundred KB, versioned (each `apply` writes a new version). Even keeping 20+ historical versions this stays under 10 MB total — $0.023/GB-month rounds to $0.01. |
| **Total** | **$7.02** | |

## Optimization

**Stop Studio apps immediately after each session instead of relying on
session timeout, and delete unused JupyterLab spaces.** The dominant cost
in this stack is the EFS home-directory volume ($1.50/month) plus any
Studio compute left running by accident — a `ml.t3.medium` instance idling
24/7 instead of ~2 hrs/day costs $0.05 × 24 × 30 = $36.00/month instead of
$2.00, a **$34/month swing** entirely driven by whether the JupyterServer
app is actually shut down. Since the lab's own rubric already requires a
shutdown screenshot (`docs/lab1-studio-shutdown.png`) to prove no app is
left `InService`, enforcing that habit is the single highest-leverage cost
control available in this stack — it is the difference between a ~$7/month
platform and a ~$41/month one for infrastructure that, in Lab 1, does no
actual model training.
