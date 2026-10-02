output "feature_group_name" {
  description = "Name of the SageMaker feature group"
  value       = aws_sagemaker_feature_group.customer_features.feature_group_name
}
