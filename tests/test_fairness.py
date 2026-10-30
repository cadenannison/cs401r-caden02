"""
NorthStar Retail — Fairness Flag Tests

Reads the per-tier recall that the training script emitted into
evaluation_metrics.json (metrics["recall_by_tier"]) and flags large gaps between
customer tiers for the approver. A gap is a WARNING, not a failure: the model
is still promotable, but the approver sees the flag in the pytest warnings summary.

The metrics path is resolved the same way as the stored-metrics gate in
tests/test_model.py: the EVAL_METRICS_PATH environment variable, which
tests/conftest.py sets from --eval-metrics-path when that flag is given.

Run locally:
    pytest tests/test_fairness.py -v -rw \
        --eval-metrics-path /tmp/out/evaluation_metrics.json
"""

import json
import os
import warnings
from pathlib import Path

import pytest

# Gap between best and worst tier recall above which the approver is warned.
MAX_TIER_RECALL_GAP = 0.10


@pytest.fixture(scope="module")
def eval_metrics():
    metrics_path = os.environ.get("EVAL_METRICS_PATH", "/tmp/eval_metrics.json")
    # Unlike test_model.py this FAILS rather than skips: a missing file would
    # otherwise let the fairness check silently vanish from the pipeline.
    if not Path(metrics_path).exists():
        pytest.fail(
            f"Evaluation metrics not found at {metrics_path}. The fairness check "
            f"needs evaluation_metrics.json from the training run; set "
            f"EVAL_METRICS_PATH or pass --eval-metrics-path."
        )
    with open(metrics_path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def recall_by_tier(eval_metrics):
    tiers = eval_metrics.get("recall_by_tier")
    assert tiers, (
        "recall_by_tier missing or empty in evaluation metrics. The training "
        "script must emit per-tier recall."
    )
    return tiers


def test_recall_by_tier_present_and_valid(recall_by_tier):
    """Every tier's recall is None (no positives) or a probability in [0, 1]."""
    assert isinstance(recall_by_tier, dict), (
        f"recall_by_tier must be a dict of tier -> recall, got {type(recall_by_tier).__name__}"
    )
    bad = {t: r for t, r in recall_by_tier.items()
           if r is not None and not (0.0 <= r <= 1.0)}
    assert not bad, f"Tier recall outside [0, 1]: {bad}"


def test_tier_recall_gap_flagged_not_failed(recall_by_tier):
    """Warn (never fail) when best and worst tier recall differ by > 10 points."""
    known = {t: r for t, r in recall_by_tier.items() if r is not None}
    if len(known) < 2:
        warnings.warn(
            f"Fairness gap not computable: only {len(known)} tier(s) have a recall "
            f"(recall_by_tier={recall_by_tier})."
        )
        return

    hi_tier = max(known, key=known.get)
    lo_tier = min(known, key=known.get)
    gap = known[hi_tier] - known[lo_tier]

    if gap > MAX_TIER_RECALL_GAP:
        warnings.warn(
            f"FAIRNESS FLAG: tier recall gap {gap:.4f} ({gap * 100:.1f} pts) exceeds "
            f"{MAX_TIER_RECALL_GAP:.2f}. Highest: {hi_tier}={known[hi_tier]:.4f}; "
            f"lowest: {lo_tier}={known[lo_tier]:.4f}. All tiers: {known}. "
            f"Approver review required."
        )
