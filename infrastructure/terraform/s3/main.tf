terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  bucket_name = var.bucket_name != "" ? var.bucket_name : "hub-assets-${var.environment}"
  common_tags = merge(
    {
      Project     = "DataInteroperabilityHub"
      Environment = var.environment
      ManagedBy   = "terraform"
      Component   = "object-storage"
    },
    var.tags,
  )
}

# ---------------------------------------------------------------------------
# S3 Bucket
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "assets" {
  bucket = local.bucket_name
  tags   = local.common_tags
}

# Block all public access — objects are accessed exclusively via IAM/IRSA.
resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning so deleted/overwritten objects are recoverable.
resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

# KMS CMK for S3 encryption (Phase 51 — SSE-KMS replaces SSE-S3).
resource "aws_kms_key" "meshant_s3" {
  description             = "Meshant S3 bucket encryption key"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = local.common_tags
}

resource "aws_kms_alias" "meshant_s3" {
  name          = "alias/meshant-s3-${var.environment}"
  target_key_id = aws_kms_key.meshant_s3.key_id
}

# Server-side encryption with SSE-KMS (Phase 51 — upgraded from AES256).
resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.meshant_s3.arn
    }
    bucket_key_enabled = true
  }
}

# Lifecycle: transition to IA after 90d, expire old versions after 365d,
# abort orphaned multipart uploads after 7d (Phase 51).
resource "aws_s3_bucket_lifecycle_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule {
    id     = "transition-to-ia"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    noncurrent_version_expiration {
      noncurrent_days = 365
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Bucket policy: deny any HTTP (non-HTTPS) requests.
resource "aws_s3_bucket_policy" "assets" {
  bucket = aws_s3_bucket.assets.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyHTTP"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.assets.arn,
          "${aws_s3_bucket.assets.arn}/*",
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid    = "AllowIRSARoles"
        Effect = "Allow"
        Principal = {
          AWS = [
            aws_iam_role.hub_s3_irsa.arn,
            aws_iam_role.hub_worker_irsa.arn,
            aws_iam_role.hub_backup_irsa.arn,
          ]
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.assets.arn,
          "${aws_s3_bucket.assets.arn}/*",
        ]
      },
    ]
  })

  # Bucket policy must be applied after public access block is set.
  depends_on = [aws_s3_bucket_public_access_block.assets]
}

# ---------------------------------------------------------------------------
# IRSA — Per-workload IAM Roles for Service Accounts (Phase 51)
# ---------------------------------------------------------------------------

# Legacy role kept for backward compat (referenced by bucket policy above)
data "aws_iam_policy_document" "irsa_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.service_account_namespace}:hub-api-sa"]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "hub_s3_irsa" {
  name               = "hub-s3-irsa-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.irsa_assume_role.json
  tags               = local.common_tags
}

# --- hub-api-sa: full CRUD on objects + KMS decrypt/encrypt ----------------
data "aws_iam_policy_document" "hub_api_s3" {
  statement {
    sid    = "BucketLevelAccess"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [aws_s3_bucket.assets.arn]
  }
  statement {
    sid    = "ObjectLevelAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.assets.arn}/*"]
  }
  statement {
    sid    = "KMSAccess"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.meshant_s3.arn]
  }
}

resource "aws_iam_role_policy" "hub_api_s3" {
  name   = "hub-api-s3-${var.environment}"
  role   = aws_iam_role.hub_s3_irsa.id
  policy = data.aws_iam_policy_document.hub_api_s3.json
}

# --- hub-worker-sa: read-only objects + KMS decrypt ------------------------
data "aws_iam_policy_document" "worker_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.service_account_namespace}:hub-worker-sa"]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "hub_worker_irsa" {
  name               = "hub-worker-irsa-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.worker_assume_role.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "hub_worker_s3" {
  statement {
    sid       = "ReadOnly"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.assets.arn}/*"]
  }
  statement {
    sid       = "KMSDecrypt"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.meshant_s3.arn]
  }
}

resource "aws_iam_role_policy" "hub_worker_s3" {
  name   = "hub-worker-s3-${var.environment}"
  role   = aws_iam_role.hub_worker_irsa.id
  policy = data.aws_iam_policy_document.hub_worker_s3.json
}

# --- hub-backup-sa: write to backup/ prefix only + KMS encrypt -------------
data "aws_iam_policy_document" "backup_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.service_account_namespace}:hub-backup-sa"]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "hub_backup_irsa" {
  name               = "hub-backup-irsa-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.backup_assume_role.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "hub_backup_s3" {
  statement {
    sid       = "BackupWriteOnly"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.assets.arn}/backup/*"]
  }
  statement {
    sid       = "KMSEncrypt"
    effect    = "Allow"
    actions   = ["kms:GenerateDataKey"]
    resources = [aws_kms_key.meshant_s3.arn]
  }
}

resource "aws_iam_role_policy" "hub_backup_s3" {
  name   = "hub-backup-s3-${var.environment}"
  role   = aws_iam_role.hub_backup_irsa.id
  policy = data.aws_iam_policy_document.hub_backup_s3.json
}
