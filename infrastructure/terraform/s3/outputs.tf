output "bucket_name" {
  description = "Name of the created S3 bucket"
  value       = aws_s3_bucket.assets.id
}

output "bucket_arn" {
  description = "ARN of the created S3 bucket"
  value       = aws_s3_bucket.assets.arn
}

output "bucket_region" {
  description = "AWS region of the bucket"
  value       = aws_s3_bucket.assets.region
}

output "kms_key_arn" {
  description = "ARN of the KMS CMK used for S3 encryption"
  value       = aws_kms_key.meshant_s3.arn
}

output "iam_role_arn" {
  description = "ARN of the hub-api IRSA IAM role"
  value       = aws_iam_role.hub_s3_irsa.arn
}

output "iam_role_name" {
  description = "Name of the hub-api IRSA IAM role"
  value       = aws_iam_role.hub_s3_irsa.name
}

output "worker_iam_role_arn" {
  description = "ARN of the hub-worker IRSA IAM role (read-only)"
  value       = aws_iam_role.hub_worker_irsa.arn
}

output "backup_iam_role_arn" {
  description = "ARN of the hub-backup IRSA IAM role (write to backup/ prefix)"
  value       = aws_iam_role.hub_backup_irsa.arn
}
