# =============================================================================
# EKS Fargate workload for pdf-chart-parser.
#
# Deploys the MCP server as a ClusterIP-only service — no ingress, no public
# exposure. The LiteLLM gateway (co-located in the same cluster) reaches it
# via the Kubernetes cluster-internal DNS:
#
#   http://<service_name>.<namespace>.svc.cluster.local:8000/mcp
#
# A dedicated Fargate profile gates pod scheduling. No IRSA role is needed:
# the server makes no AWS API calls at runtime.
# =============================================================================

locals {
  name = "pdf-chart-parser"
}

# ─── Fargate profile ──────────────────────────────────────────────────────────
# Must be created before pods are scheduled; the Deployment depends_on it so
# Terraform waits rather than leaving pods stuck in Pending.
resource "aws_eks_fargate_profile" "this" {
  cluster_name           = var.cluster_name
  fargate_profile_name   = "${local.name}-${var.env}"
  pod_execution_role_arn = var.fargate_execution_role_arn
  subnet_ids             = var.subnet_ids

  selector {
    namespace = var.namespace
  }

  tags = var.tags
}

# ─── Namespace ────────────────────────────────────────────────────────────────
resource "kubernetes_namespace" "this" {
  metadata {
    name = var.namespace
  }

  depends_on = [aws_eks_fargate_profile.this]
}

# ─── Service account (no IRSA — server makes no AWS API calls) ───────────────
resource "kubernetes_service_account" "this" {
  metadata {
    name      = local.name
    namespace = kubernetes_namespace.this.metadata[0].name
  }
}

# ─── Deployment ───────────────────────────────────────────────────────────────
resource "kubernetes_deployment" "this" {
  metadata {
    name      = local.name
    namespace = kubernetes_namespace.this.metadata[0].name
    labels = {
      "app.kubernetes.io/name" = local.name
    }
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = {
        "app.kubernetes.io/name" = local.name
      }
    }

    template {
      metadata {
        labels = {
          "app.kubernetes.io/name" = local.name
        }
      }

      spec {
        service_account_name             = kubernetes_service_account.this.metadata[0].name
        termination_grace_period_seconds = 30

        container {
          name  = local.name
          image = var.image

          port {
            container_port = 8000
            protocol       = "TCP"
          }

          # Re-assert the values baked into the Dockerfile so the deployment
          # spec is self-documenting and overridable without a new image.
          env {
            name  = "MCP_TRANSPORT"
            value = "streamable-http"
          }
          env {
            name  = "HOST"
            value = "0.0.0.0"
          }
          env {
            name  = "PORT"
            value = "8000"
          }

          resources {
            requests = {
              cpu    = var.cpu_request
              memory = var.memory_request
            }
            limits = {
              cpu    = var.cpu_limit
              memory = var.memory_limit
            }
          }

          # TCP probes: FastMCP's streamable-http server doesn't expose a
          # dedicated health-check path, so we verify the port is accepting
          # connections. Adjust to an HTTP probe once you confirm the server's
          # health endpoint path.
          readiness_probe {
            tcp_socket {
              port = 8000
            }
            initial_delay_seconds = 15
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          liveness_probe {
            tcp_socket {
              port = 8000
            }
            initial_delay_seconds = 30
            period_seconds        = 30
            timeout_seconds       = 5
            failure_threshold     = 3
          }
        }
      }
    }
  }

  timeouts {
    create = "10m"
    update = "10m"
  }

  # Terraform owns the Deployment infra (replicas, probes, resources, env) but
  # NOT the running image tag. Releases are rolled out by scripts/release.sh
  # (kubectl set image), so a new release never requires a terraform apply.
  # var.image only seeds the bootstrap image on first create.
  lifecycle {
    ignore_changes = [
      spec[0].template[0].spec[0].container[0].image,
    ]
  }

  depends_on = [aws_eks_fargate_profile.this]
}

# ─── Service (ClusterIP — internal only) ─────────────────────────────────────
resource "kubernetes_service" "this" {
  metadata {
    name      = local.name
    namespace = kubernetes_namespace.this.metadata[0].name
  }

  spec {
    selector = {
      "app.kubernetes.io/name" = local.name
    }

    port {
      port        = 8000
      target_port = 8000
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}
