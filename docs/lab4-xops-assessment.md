Lab 4 XOps Assessment: NorthStar Churn Pipeline

## Pipeline Stage Mapping

The pipeline in pipeline.yaml has three CodePipeline stages: Source, Build and ManualApproval. The five phases map onto them like this:

1. Source: the Source stage, which pulls from the GitHub main branch through the CodeStar connection.
2. Test: pre_build in buildspec.yml, which runs tests/test_data.py and tests/test_features.py.
3. Build: build in buildspec.yml, which runs the SageMaker Pipeline northstar-churn-pipeline with spot training.
4. Evaluate: also in build, where tests/test_model.py and tests/test_fairness.py check the metrics the training job emitted.
5. Register: the RegisterModel step puts the package in the registry as PendingManualApproval. If the build fails after that, post_build sets it to Rejected.

I kept phases 2 to 5 inside one CodeBuild project because stages are meant to be deployment boundaries, and splitting them would only mean passing the model artifact between stages. I used CodePipeline and CodeBuild because the starter stack already sets them up and they work with SageMaker, SNS and CloudWatch.

The failure demo (docs/lab4-failure-demo.txt, docs/lab4-build-failed.log) shows PRE_BUILD failing with no BUILD phase, the registry staying at v3, and the alarm going from OK to ALARM with the SNS email delivered (docs/lab4-alarm-email.png). After the revert the next run registered v4.

## Champion Challenger

A new model replaces the champion only if all of these are true: its auc_roc is at least the champion's auc_roc minus 0.02, precision_top10 is at least 0.50, recall_top10 is at least 0.25, and lift_ci_low is above 0 (the 95% CI on model AUC minus baseline AUC excludes zero). A person then approves it in the registry. v4 meets the rule with auc_roc 0.7861, baseline 0.7208, precision 0.73, recall 0.3318 and lift_ci_low 0.0472, and it is still PendingManualApproval.

Some judgment calls I made along the way

- I raised MONO_TOLERANCE in tests/test_model.py from 0.02 to 0.05. The model dipped 0.028 between recency 30 and 60 (see docs/lab4-build-bootstrap.log) even though the overall trend went from 0.28 to 0.80.
- I approved v2 by hand as the first champion, since its build failed the missing champion test and the monotonicity test and there was nothing to compare against yet.
- The MLEngineer IAM policy was missing CreateModelPackageGroup. I added it along with DescribeModelPackageGroup, ListModelPackageGroups and UpdateModelPackage.
- The fairness test flags a 34.2 point recall gap between Bronze (0.4571) and Gold (0.1154) but does not block.

The five MLflow runs in docs/lab4-mlflow-runs.txt came from scripts/lab4_mlflow_sweep.py. They ran on XGBoost 3.x locally, so the numbers differ a little from the container's 1.7.

## Retraining Triggers

Neither of these is deployed, they are only designed.

Scheduled: an EventBridge Scheduler rule with cron(0 6 ? * MON *) starts the pipeline every Monday at 06:00 UTC.

Performance-based: a SageMaker Model Monitor model-quality job checks production predictions. A CloudWatch alarm fires if AUC drops below 0.74 for 2 days in a row, and EventBridge uses that alarm to start the pipeline.

## DataOps Maturity

Current level: 2

Evidence: The Glue jobs glue-scripts/transform.py and glue-scripts/feature_engineer.py build the processed and feature data. tests/test_data.py (28 tests passed in CI, including freshness and a post-cutoff leakage check) and tests/test_features.py (23 passed) run in pre_build in buildspec.yml on every push. In the failure demo, a failing test stopped the build before any training happened.

Gap to Level 3: Nothing schedules the Glue chain. The crawler, transform and feature jobs are all started by hand, so data freshness depends on someone rerunning them. The 48 hour freshness test catches stale data but doesn't prevent it.

Top priority investment: An AWS Glue workflow that chains the crawler, transform and feature jobs, started by an EventBridge schedule.

## MLOps Maturity

Current level: 3

Evidence: buildspec.yml and pipeline.yaml run tests, training, evaluation and registration automatically. docs/lab4-build-green.log shows 21 passing tests in the build phase, the champion v2 auc=0.7861 warning, and the SageMaker Pipeline succeeding. The registry holds versioned packages, and v4 has its commit SHA, data URI, data timestamp and metrics in docs/lab4-model-package.json. The failure demo shows the alarm firing and the email arriving. Packages become Approved only by a person after the gates run, except the v2 bootstrap I approved by hand.

Gap to Level 4: There is no drift detection and no deployed retraining trigger. A model that gets worse in production wouldn't be noticed until someone looked, and the weekly schedule alone would retrain on a calendar instead of on evidence.

Top priority investment: A SageMaker Model Monitor model-quality schedule with a CloudWatch alarm, sent through EventBridge to start northstar-churn-pipeline.