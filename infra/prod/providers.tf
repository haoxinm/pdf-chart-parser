provider "aws" {
  region = var.aws_region

  default_tags {
    tags = var.tags
  }
}

# Authenticates to the EKS cluster using the AWS CLI exec plugin so no
# kubeconfig file needs to be on disk. The cluster is looked up by name in
# main.tf; both providers read that data source at plan time.
provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", data.aws_eks_cluster.this.name, "--region", var.aws_region]
  }
}
