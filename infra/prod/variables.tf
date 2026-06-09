# =============================================================================
# prod environment inputs.
#
# Required values (no defaults) must be set in terraform.tfvars (git-ignored).
# See terraform.tfvars.example for the expected shape.
# =============================================================================

variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "us-west-2"
}

# ─── EKS cluster ─────────────────────────────────────────────────────────────
variable "cluster_name" {
  description = "Name of the EKS cluster to deploy into."
  type        = string
}

variable "fargate_execution_role_arn" {
  description = "ARN of the IAM role the cluster uses for Fargate pod execution. Typically created alongside the EKS cluster."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs for Fargate pods (at least 2, across separate AZs)."
  type        = list(string)
  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "Provide at least 2 private subnets across distinct AZs."
  }
}

# ─── Container ───────────────────────────────────────────────────────────────
variable "image" {
  description = "Bootstrap container image URI including tag. After first apply, releases use scripts/release.sh and do not require re-applying."
  type        = string
}

variable "replicas" {
  description = "Number of pod replicas. Default 2 for HA in prod."
  type        = number
  default     = 2
}

# ─── Tagging ─────────────────────────────────────────────────────────────────
variable "tags" {
  description = "AWS resource tags."
  type        = map(string)
  default     = {}
}
