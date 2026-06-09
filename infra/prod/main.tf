data "aws_eks_cluster" "this" {
  name = var.cluster_name
}

module "pdf_chart_parser" {
  source = "../modules/pdf-chart-parser"

  env          = "prod"
  cluster_name = data.aws_eks_cluster.this.name

  fargate_execution_role_arn = var.fargate_execution_role_arn
  subnet_ids                 = var.subnet_ids

  image    = var.image
  replicas = var.replicas

  tags = var.tags
}
