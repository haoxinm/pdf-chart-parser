output "namespace" {
  description = "Kubernetes namespace."
  value       = module.pdf_chart_parser.namespace
}

output "service_name" {
  description = "Kubernetes Service name."
  value       = module.pdf_chart_parser.service_name
}

output "mcp_url" {
  description = "Cluster-internal MCP endpoint URL (reachable from the LiteLLM gateway pod)."
  value       = module.pdf_chart_parser.mcp_url
}

output "fargate_profile_name" {
  description = "EKS Fargate profile name."
  value       = module.pdf_chart_parser.fargate_profile_name
}

output "next_steps" {
  description = "Post-apply operator checklist."
  value       = <<-EOT

    Deployment complete. Next steps:

    1. Register the MCP server in LiteLLM (one-time, per environment):
       See litellm-gateway/config/config.yaml for the curl command.

    2. Verify pods are Running on Fargate:
       kubectl -n ${module.pdf_chart_parser.namespace} get pods -w

    3. Run the smoke test:
       scripts/smoke-test.sh staging

    4. For future image releases (no re-apply needed):
       ECR_REPO=<uri> EKS_CLUSTER=<name> scripts/release.sh staging
  EOT
}
