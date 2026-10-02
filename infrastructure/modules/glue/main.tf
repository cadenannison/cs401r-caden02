# ── modules/glue ─────────────────────────────────────────────────────────────
# Transform pipeline plus the feature-engineering job that writes to the
# SageMaker Feature Store.

data "aws_region" "current" {}

resource "aws_glue_catalog_database" "this" {
  name = "${var.project}_${var.environment}"
}

resource "aws_glue_crawler" "raw" {
  name          = "${var.project}-${var.environment}-raw-crawler"
  role          = var.role_arn
  database_name = aws_glue_catalog_database.this.name

  s3_target {
    path = "s3://${var.bucket_name}/raw/customers/"
  }
}

resource "aws_s3_object" "transform_script" {
  bucket = var.bucket_name
  key    = "artifacts/glue/transform.py"
  source = var.script_source_path
  etag   = filemd5(var.script_source_path)
}

resource "aws_glue_connection" "vpc" {
  name            = "${var.project}-${var.environment}-vpc-connection"
  connection_type = "NETWORK"

  physical_connection_requirements {
    availability_zone      = var.availability_zone
    subnet_id              = var.subnet_id
    security_group_id_list = [var.security_group_id]
  }
}

resource "aws_glue_job" "transform" {
  name     = "${var.project}-${var.environment}-transform"
  role_arn = var.role_arn

  glue_version = "4.0"

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.bucket_name}/artifacts/glue/transform.py"
  }

  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30
  max_retries       = 0

  connections = [aws_glue_connection.vpc.name]

  default_arguments = {
    "--job-language"                     = "python"
    "--database_name"                    = aws_glue_catalog_database.this.name
    "--table_name"                       = "customers"
    "--output_path"                      = "s3://${var.bucket_name}/processed/customers/"
    "--enable-continuous-cloudwatch-log" = "true"
  }

  depends_on = [aws_s3_object.transform_script]
}

resource "aws_s3_object" "feature_engineer_script" {
  bucket = var.bucket_name
  key    = "artifacts/glue/feature_engineer.py"
  source = var.feature_script_source_path
  etag   = filemd5(var.feature_script_source_path)
}

resource "aws_glue_job" "feature_engineer" {
  name     = "${var.project}-${var.environment}-feature-engineer"
  role_arn = var.role_arn

  glue_version = "4.0"

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.bucket_name}/artifacts/glue/feature_engineer.py"
  }

  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 60
  max_retries       = 0

  connections = [aws_glue_connection.vpc.name]

  default_arguments = {
    "--job-language"                     = "python"
    "--input_path"                       = "s3://${var.bucket_name}/processed/customers/"
    "--output_path"                      = "s3://${var.bucket_name}/features/customers/"
    "--feature_group_name"               = var.feature_group_name
    "--region"                           = data.aws_region.current.name
    "--enable-continuous-cloudwatch-log" = "true"
  }

  depends_on = [aws_s3_object.feature_engineer_script]
}
