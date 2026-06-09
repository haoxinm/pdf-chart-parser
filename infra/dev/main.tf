# Look up the EKS cluster so the Kubernetes provider and module can consume its
# endpoint, CA certificate, and OIDC issuer without repeating the lookup.
data "aws_eks_cluster" "this" {
  name = var.cluster_name
}

module "pdf_chart_parser" {
  source = "../modules/pdf-chart-parser"

  env          = "dev"
  cluster_name = data.aws_eks_cluster.this.name

  fargate_execution_role_arn = var.fargate_execution_role_arn
  subnet_ids                 = var.subnet_ids

  image    = var.image
  replicas = var.replicas

  tags = var.tags
}
