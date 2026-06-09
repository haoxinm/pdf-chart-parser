output "namespace" {
  description = "Kubernetes namespace the server is deployed in."
  value       = kubernetes_namespace.this.metadata[0].name
}

output "service_name" {
  description = "Kubernetes Service name."
  value       = kubernetes_service.this.metadata[0].name
}

output "service_port" {
  description = "Port the MCP server listens on."
  value       = 8000
}

output "cluster_dns" {
  description = "Cluster-internal DNS name to reach the MCP server from other pods in the same cluster (e.g., from the LiteLLM gateway). The MCP endpoint is at /mcp."
  value       = "${kubernetes_service.this.metadata[0].name}.${kubernetes_namespace.this.metadata[0].name}.svc.cluster.local"
}

output "mcp_url" {
  description = "Full cluster-internal URL for the MCP streamable-http endpoint."
  value       = "http://${kubernetes_service.this.metadata[0].name}.${kubernetes_namespace.this.metadata[0].name}.svc.cluster.local:8000/mcp"
}

output "fargate_profile_name" {
  description = "Name of the EKS Fargate profile created for this workload."
  value       = aws_eks_fargate_profile.this.fargate_profile_name
}
