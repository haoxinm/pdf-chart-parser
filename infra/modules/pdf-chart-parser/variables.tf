# =============================================================================
# pdf-chart-parser EKS workload module variables.
# =============================================================================

variable "env" {
  description = "Environment short name (dev | staging | prod)."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of: dev, staging, prod"
  }
}

variable "cluster_name" {
  description = "Name of the EKS cluster to deploy into."
  type        = string
}

variable "fargate_execution_role_arn" {
  description = "ARN of the IAM role used by Fargate to pull images and write logs (the cluster's existing pod-execution role)."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs where Fargate pods are scheduled. Must span at least 2 AZs."
  type        = list(string)
  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "Provide at least 2 subnets across distinct AZs."
  }
}

# ─── Container ────────────────────────────────────────────────────────────────
variable "image" {
  description = "Full container image URI including tag (e.g., 123456789012.dkr.ecr.us-west-2.amazonaws.com/pdf-chart-parser:abc1234). Terraform seeds this on first apply; subsequent releases go through scripts/release.sh (kubectl set image) without a terraform apply."
  type        = string
}

variable "replicas" {
  description = "Number of pod replicas. 1 is fine for dev; use 2+ for HA in prod."
  type        = number
  default     = 1
}

# Fargate selects the task size from the pod's combined resource requests.
# Valid combinations: https://docs.aws.amazon.com/eks/latest/userguide/fargate-pod-configuration.html
variable "cpu_request" {
  description = "CPU request (e.g., '256m', '512m', '1'). Fargate rounds up to the next valid vCPU increment."
  type        = string
  default     = "512m"
}

variable "cpu_limit" {
  description = "CPU limit."
  type        = string
  default     = "1"
}

variable "memory_request" {
  description = "Memory request (e.g., '1Gi', '2Gi'). Fargate rounds up to the next valid memory increment."
  type        = string
  default     = "1Gi"
}

variable "memory_limit" {
  description = "Memory limit."
  type        = string
  default     = "2Gi"
}

# ─── Kubernetes ───────────────────────────────────────────────────────────────
variable "namespace" {
  description = "Kubernetes namespace to deploy into. A matching Fargate profile is created for this namespace."
  type        = string
  default     = "pdf-chart-parser"
}

# ─── Tagging ──────────────────────────────────────────────────────────────────
variable "tags" {
  description = "AWS resource tags applied to the Fargate profile."
  type        = map(string)
  default     = {}
}
