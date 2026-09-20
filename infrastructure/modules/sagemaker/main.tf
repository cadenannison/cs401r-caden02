# ── modules/sagemaker ────────────────────────────────────────────────────────
# Required resources (Task B1):
#
#   aws_sagemaker_domain
#   aws_sagemaker_user_profile
#
# A brand-new AWS account has no service-linked role for Studio, and the
# Domain fails to create with a service-linked role error. Fix it once in the
# console (IAM -> Roles -> Create Role -> AWS Service -> SageMaker -> SageMaker
# Studio) and re-apply. See the New Account Bootstrap note in the lab.
#
# retention_policy.home_efs_file_system = "Delete" is required: Studio's home
# directory EFS filesystem is invisible to Terraform, and left on its default
# (Retain) its mount target pins the subnet/security group so
# `terraform destroy` hangs for ~10 minutes before failing.

resource "aws_sagemaker_domain" "this" {
  domain_name = "${var.project}-${var.environment}-domain"
  auth_mode   = "IAM"
  vpc_id      = var.vpc_id
  subnet_ids  = var.subnet_ids

  default_user_settings {
    execution_role  = var.execution_role_arn
    security_groups = var.security_group_ids

    sharing_settings {
      notebook_output_option = "Disabled"
    }

    jupyter_lab_app_settings {
      default_resource_spec {
        instance_type = var.instance_type
      }
    }
  }

  retention_policy {
    home_efs_file_system = "Delete"
  }

  tags = {
    Name = "${var.project}-${var.environment}-domain"
  }
}

resource "aws_sagemaker_user_profile" "ml_engineer" {
  domain_id         = aws_sagemaker_domain.this.id
  user_profile_name = "MLEngineer"

  user_settings {
    execution_role = var.execution_role_arn
  }

  tags = {
    Name = "${var.project}-${var.environment}-MLEngineer-profile"
  }
}
