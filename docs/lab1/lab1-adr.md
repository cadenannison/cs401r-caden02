## ADR-001: NorthStar Platform Foundation

### Status
Accepted

### Context
NorthStar is building three AI systems on one shared platform: a weekly
batch churn-prediction model, an LLM/RAG offer-generation service, and an
agentic customer service system. All three will eventually read the same
customer, transaction, and product data, but they are built and operated by
different roles — an ML engineer training and registering models now, a
data engineer maintaining ingestion pipelines starting Lab 2, and a model
monitor watching for drift, also Lab 2. Sharing infrastructure across three
systems only works if the platform can prove which role touched which data,
because the offer system carries FCRA/ECOA non-discrimination exposure and
all three touch PII covered by GDPR (Canadian customers) and CCPA
(California customers). Lab 1 puts that identity and storage boundary in
place before any of the three systems exist, not after. Networking exists
to run SageMaker Studio, where the churn model will be built — it is not
yet a production serving problem, since churn scoring is a weekly batch
job with no external caller.

### Decision
One VPC (`northstar-dev-vpc`, `10.0.0.0/16`) with a single public subnet
(`northstar-dev-public-1`, `10.0.100.0/24`, `us-east-1a`) hosts SageMaker
Studio. Its security group allows inbound traffic only from `10.0.0.0/16`
— no internet inbound — with unrestricted outbound so Studio can pull
training images from ECR and reach S3. One public subnet is deliberately
minimal: the churn model has no live caller yet, so there is no production
traffic pattern to isolate into a private subnet today; Lab 2 adds private
subnets and a NAT gateway once the data engineer and model monitor roles
need compute that should never be internet-reachable.

Storage is one S3 bucket (`northstar-dev-data-<account-id>`) partitioned
into four prefixes — `raw/`, `processed/`, `features/`, `artifacts/` —
rather than four buckets, so bucket-level settings (versioning, SSE-S3,
blocked public access) stay uniform while prefix-scoped IAM policies still
give each role its own boundary. MLEngineer only reads `features/` and
reads/writes `artifacts/`; it has no access to `raw/` or `processed/`,
which hold data not yet cleared for model-adjacent use.

Identity is one IAM role per function, not a shared credential. 
`northstar-dev-MLEngineer` trusts only `sagemaker.amazonaws.com` and is
granted: SageMaker training/endpoint/MLflow/registry actions (`Resource:
"*"`, since these APIs have no resource-level ARNs); Studio self-service
actions scoped to the domain/user-profile/space/app ARN types, so it can
open and close its own Studio session without touching training resources;
S3 access scoped to `artifacts/*` and `features/*` **object** ARNs, never a
bucket-level wildcard, which would silently also grant `raw/` write access;
and read-only ECR. The lab's original policy referenced
`sagemaker:RegisterModel`, which is not a real IAM action — the corrected
policy uses `sagemaker:CreateModelPackage`, the action that actually backs
model registry writes.

SageMaker Studio is the ML environment because it is what this course
standardizes on for every later lab, and its domain-per-execution-role model
maps directly onto the per-role identity design above.

### Consequences

#### What this makes easy
- Adding DataEngineer/ModelMonitor in Lab 2 needs only new IAM policies
  scoped to `raw/`, `processed/`, and CloudWatch — no bucket restructuring.
- Auditing "what can MLEngineer touch" is one `simulate-principal-policy`
  call against one role, not four bucket policies.
- Versioning means an accidental delete in `artifacts/` (the only prefix
  MLEngineer can delete from) is recoverable without a separate backup.

#### What this makes harder
- SageMaker training/endpoint actions don't support resource-level
  conditions, so `SageMakerCore` is `Resource: "*"` — a compromised Studio
  session could stop or describe any training job in the account, not just
  its own. This is an accepted gap, not a solved one.
- One shared bucket means a lifecycle or key-rotation change applies to all
  four stages at once; no prefix-scoped lifecycle rules exist yet (deferred
  per the lab's own scope note).
- Studio's public subnet gives its ENI a public IP; acceptable only because
  Studio isn't yet serving the 2-second offer SLA or 99.5%-uptime agent SLA
  that would require the Lab 2 topology.

#### What would cause you to revisit this decision
- The moment the offer-generation (2s SLA) or customer-service agent
  (99.5% uptime, 14,000 contacts/day) needs infrastructure here, the
  public-subnet-only topology must become Lab 2's private-subnet/NAT
  design.
- If SageMaker adds resource-level IAM conditions on `CreateTrainingJob`/
  `CreateEndpoint`, narrow `SageMakerCore` immediately.
- If `raw/` volume grows enough to need Glacier transitions inside the
  24-month retention window, add prefix-level lifecycle rules.

### Alternative Considered
A plausible alternative is one S3 bucket per stage
(`northstar-dev-raw`, `-processed`, `-features`, `-artifacts`) instead of
one bucket with four prefixes. Four buckets would let each stage have
independently tuned lifecycle rules, encryption keys, and logging targets,
with no risk of a miswritten prefix policy accidentally granting bucket-wide
access. It was rejected because four buckets means every role policy and
every future Lab 2 Glue/Lambda job references four ARNs instead of one, and
NorthStar's actual data volume in this course — a handful of CSVs and model
artifacts — doesn't yet justify four sets of versioning/encryption/public-
access-block settings to keep in sync. The single-bucket design was chosen
specifically because the S3 policy references **object** ARNs
(`bucket/artifacts/*`), which closes the exact risk the four-bucket
alternative was meant to avoid.

### AWS Service Selection
- **Networking isolation:** VPC + one public subnet, VPC-internal-only
  security group — chosen because Studio, Lab 1's only networked workload,
  has no external caller yet, only outbound needs.
- **Storage design:** One versioned, SSE-S3-encrypted bucket partitioned by
  prefix — chosen because object-level ARNs give IAM the same isolation as
  separate buckets while keeping bucket configuration in one place.
- **Identity model:** One IAM role per function, trusted only by the
  service that assumes it — chosen because FCRA/ECOA and GDPR/CCPA exposure
  requires answering "what can this role do" from one policy document, not
  a shared credential audited by exclusion.
- **ML development environment:** SageMaker Studio — chosen because it's
  this course's standard IDE and its domain/user-profile model enforces the
  same per-role execution-role boundary as the rest of the platform.
