# ── modules/feature_store ────────────────────────────────────────────────────
# SageMaker Feature Store for customer features. The feature_definition blocks
# are generated from the local list below via a dynamic block, not written by
# hand, so the 16 features stay easy to audit and extend.

locals {
  customer_features = [
    { name = "customer_id", type = "String" },
    { name = "event_time", type = "Fractional" },
    { name = "days_since_last_purchase", type = "Fractional" },
    { name = "customer_tenure_days", type = "Fractional" },
    { name = "purchase_frequency_30d", type = "Fractional" },
    { name = "purchase_frequency_90d", type = "Fractional" },
    { name = "purchase_frequency_180d", type = "Fractional" },
    { name = "avg_order_value", type = "Fractional" },
    { name = "total_spend_90d", type = "Fractional" },
    { name = "total_lifetime_value", type = "Fractional" },
    { name = "avg_basket_size_6m", type = "Fractional" },
    { name = "category_diversity_score", type = "Fractional" },
    { name = "online_to_store_ratio", type = "Fractional" },
    { name = "loyalty_tier", type = "String" },
    { name = "churn_risk_score", type = "Fractional" },
    { name = "churn_label", type = "Integral" },
  ]
}

resource "aws_sagemaker_feature_group" "customer_features" {
  feature_group_name             = "${var.project}-${var.environment}-customer-features"
  record_identifier_feature_name = "customer_id"
  event_time_feature_name        = "event_time"
  role_arn                       = var.role_arn

  dynamic "feature_definition" {
    for_each = local.customer_features

    content {
      feature_name = feature_definition.value.name
      feature_type = feature_definition.value.type
    }
  }

  online_store_config {
    enable_online_store = true
  }

  offline_store_config {
    s3_storage_config {
      s3_uri = "s3://${var.bucket_name}/features/offline-store/"
    }
  }
}
