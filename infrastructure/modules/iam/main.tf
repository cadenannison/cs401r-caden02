# ── modules/iam ──────────────────────────────────────────────────────────────
# Required resources (Task B1). Exactly one of each:
#
#   aws_iam_role                     MLEngineer, trusted by sagemaker.amazonaws.com
#   aws_iam_policy
#   aws_iam_role_policy_attachment
#
# The module call in environments/dev/main.tf passes only project/environment,
# so the data bucket name is derived here the same way modules/storage derives
# it: ${project}-${environment}-data-${account_id}. Object-level S3 access is
# scoped to artifacts/* and features/* only — never a bare bucket wildcard,
# which would also match raw/* and processed/* and defeat the whole point of
# the prefix split.

data "aws_caller_identity" "current" {}

locals {
  bucket_name = "${var.project}-${var.environment}-data-${data.aws_caller_identity.current.account_id}"
  bucket_arn  = "arn:aws:s3:::${local.bucket_name}"
}

resource "aws_iam_role" "ml_engineer" {
  name = "${var.project}-${var.environment}-MLEngineer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "sagemaker.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project}-${var.environment}-MLEngineer"
  }
}

resource "aws_iam_policy" "ml_engineer" {
  name        = "NorthStarMLEngineerPolicy"
  description = "Least-privilege permissions for the NorthStar MLEngineer role"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SageMakerCore"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateTrainingJob", "sagemaker:DescribeTrainingJob", "sagemaker:StopTrainingJob",
          "sagemaker:CreateEndpoint", "sagemaker:DescribeEndpoint", "sagemaker:DeleteEndpoint",
          "sagemaker:CreateEndpointConfig", "sagemaker:DeleteEndpointConfig",
          "sagemaker:CreateMlflowApp", "sagemaker:DescribeMlflowApp", "sagemaker:ListMlflowApps",
          "sagemaker:CreatePresignedMlflowAppUrl",
          "sagemaker:CreateModelPackage", "sagemaker:DescribeModelPackage", "sagemaker:ListModelPackages"
        ]
        Resource = "*"
      },
      {
        Sid    = "StudioSelfService"
        Effect = "Allow"
        Action = [
          "sagemaker:DescribeDomain", "sagemaker:ListDomains",
          "sagemaker:DescribeUserProfile", "sagemaker:ListUserProfiles",
          "sagemaker:DescribeSpace", "sagemaker:ListSpaces", "sagemaker:CreateSpace",
          "sagemaker:UpdateSpace", "sagemaker:DeleteSpace",
          "sagemaker:DescribeApp", "sagemaker:ListApps", "sagemaker:CreateApp", "sagemaker:DeleteApp",
          "sagemaker:CreatePresignedDomainUrl"
        ]
        Resource = [
          "arn:aws:sagemaker:*:*:domain/*", "arn:aws:sagemaker:*:*:user-profile/*",
          "arn:aws:sagemaker:*:*:space/*", "arn:aws:sagemaker:*:*:app/*"
        ]
      },
      {
        Sid    = "S3ArtifactsAndFeatures"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [
          "${local.bucket_arn}/artifacts/*",
          "${local.bucket_arn}/features/*"
        ]
      },
      {
        Sid      = "S3BucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = local.bucket_arn
      },
      {
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:log-group:/aws/sagemaker/*"
      },
      {
        Sid      = "ECRRead"
        Effect   = "Allow"
        Action   = ["ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage", "ecr:GetAuthorizationToken"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ml_engineer" {
  role       = aws_iam_role.ml_engineer.name
  policy_arn = aws_iam_policy.ml_engineer.arn
}

resource "aws_iam_role" "data_engineer" {
  name = "${var.project}-${var.environment}-DataEngineer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = [
            "glue.amazonaws.com",
            "lambda.amazonaws.com",
            "sagemaker.amazonaws.com"
          ]
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project}-${var.environment}-DataEngineer"
  }
}

resource "aws_iam_policy" "data_engineer" {
  name        = "${var.project}${var.environment}DataEngineerPolicy"
  description = "Least-privilege permissions for the ${var.project} DataEngineer role"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "GlueFull"
        Effect   = "Allow"
        Action   = "glue:*"
        Resource = "*"
      },
      {
        Sid    = "EC2NetworkDescribe"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface", "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSubnets", "ec2:DescribeSecurityGroups", "ec2:DescribeVpcs",
          "ec2:DescribeVpcEndpoints", "ec2:DescribeRouteTables"
        ]
        Resource = "*"
      },
      {
        Sid      = "EC2NetworkInterfaceTags"
        Effect   = "Allow"
        Action   = ["ec2:CreateTags", "ec2:DeleteTags"]
        Resource = "arn:aws:ec2:*:*:network-interface/*"
      },
      {
        Sid    = "S3DataObjects"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [
          "${local.bucket_arn}/raw/*",
          "${local.bucket_arn}/processed/*",
          "${local.bucket_arn}/features/*"
        ]
      },
      {
        Sid      = "S3FeaturesAcl"
        Effect   = "Allow"
        Action   = "s3:PutObjectAcl"
        Resource = "${local.bucket_arn}/features/*"
      },
      {
        Sid      = "S3BucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation", "s3:GetBucketAcl"]
        Resource = local.bucket_arn
      },
      {
        Sid      = "S3ArtifactsGlueRead"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${local.bucket_arn}/artifacts/glue/*"
      },
      {
        Sid      = "SageMakerFeatureStore"
        Effect   = "Allow"
        Action   = ["sagemaker:PutRecord", "sagemaker:CreateFeatureGroup", "sagemaker:DescribeFeatureGroup"]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = [
          "arn:aws:logs:*:*:log-group:/aws-glue/*",
          "arn:aws:logs:*:*:log-group:/aws/sagemaker/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "data_engineer" {
  role       = aws_iam_role.data_engineer.name
  policy_arn = aws_iam_policy.data_engineer.arn
}

resource "aws_iam_role" "model_monitor" {
  name = "${var.project}-${var.environment}-ModelMonitor"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "sagemaker.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project}-${var.environment}-ModelMonitor"
  }
}

resource "aws_iam_policy" "model_monitor" {
  name        = "${var.project}${var.environment}ModelMonitorPolicy"
  description = "Least-privilege permissions for the ${var.project} ModelMonitor role"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "CloudWatchMetrics"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData", "cloudwatch:GetMetricStatistics", "cloudwatch:PutMetricAlarm", "cloudwatch:DescribeAlarms"]
        Resource = "*"
      },
      {
        Sid      = "SageMakerProcessingRead"
        Effect   = "Allow"
        Action   = ["sagemaker:ListProcessingJobs", "sagemaker:DescribeProcessingJob"]
        Resource = "*"
      },
      {
        Sid      = "S3ArtifactsRead"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${local.bucket_arn}/artifacts/*"
      },
      {
        Sid      = "S3BucketList"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = local.bucket_arn
      },
      {
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:log-group:/aws/sagemaker/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "model_monitor" {
  role       = aws_iam_role.model_monitor.name
  policy_arn = aws_iam_policy.model_monitor.arn
}
