variable "environment" {
  description = "Deployment environment (e.g. production, staging)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for the S3 bucket"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "Name of the S3 bucket (defaults to hub-assets-<environment>)"
  type        = string
  default     = ""
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS cluster OIDC provider (for IRSA)"
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the EKS cluster OIDC provider, without https:// prefix"
  type        = string
}

variable "service_account_namespace" {
  description = "Kubernetes namespace where the hub API pod runs"
  type        = string
  default     = "hub"
}

variable "service_account_name" {
  description = "DEPRECATED: Per-workload SA names are now hardcoded (hub-api-sa, hub-worker-sa, hub-backup-sa). Kept for backward compat."
  type        = string
  default     = "hub-api-sa"
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}
