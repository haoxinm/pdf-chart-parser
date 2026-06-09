#!/usr/bin/env bash
# =============================================================================
# Release pdf-chart-parser to an EKS cluster.
#
# Builds and pushes a new image (tagged with the git SHA), then rolls out the
# new image via kubectl. Releases are decoupled from IaC: the Deployment's
# infrastructure (replicas, probes, resources) is owned by infra/; only the
# running image tag is updated here.
#
# Usage:
#   scripts/release.sh <env> [git-ref]
#     <env>      dev | staging | prod
#     [git-ref]  commit to build (default: HEAD)
#
# Required env:
#   ECR_REPO    Full ECR repository URI
#               (e.g., 123456789012.dkr.ecr.us-west-2.amazonaws.com/pdf-chart-parser)
#   EKS_CLUSTER EKS cluster name (e.g., my-eks-cluster)
#
# Optional env:
#   AWS_REGION  AWS region (default: us-west-2)
#   NAMESPACE   Kubernetes namespace (default: pdf-chart-parser)
#   DEPLOYMENT  Deployment name (default: pdf-chart-parser)
#   CONTAINER   Container name within the Deployment (default: pdf-chart-parser)
# =============================================================================
set -euo pipefail

ENV="${1:?usage: release.sh <env> [git-ref]}"
GIT_REF="${2:-HEAD}"

: "${ECR_REPO:?ECR_REPO must be set to your ECR repository URI}"
: "${EKS_CLUSTER:?EKS_CLUSTER must be set to your EKS cluster name}"

AWS_REGION="${AWS_REGION:-us-west-2}"
NAMESPACE="${NAMESPACE:-pdf-chart-parser}"
DEPLOYMENT="${DEPLOYMENT:-pdf-chart-parser}"
CONTAINER="${CONTAINER:-pdf-chart-parser}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

TAG="$(git -C "$REPO_ROOT" rev-parse --short=12 "$GIT_REF")"
IMAGE="${ECR_REPO}:${TAG}"

echo "==> Releasing ${DEPLOYMENT} → ${IMAGE}"
echo "    cluster=${EKS_CLUSTER}  namespace=${NAMESPACE}  env=${ENV}"

# ─── Build + push ──────────────────────────────────────────────────────────
TAG="$TAG" ECR_REPO="$ECR_REPO" AWS_REGION="$AWS_REGION" \
  "$SCRIPT_DIR/build_and_push.sh"

# ─── Roll out ──────────────────────────────────────────────────────────────
echo "==> Updating kubeconfig for cluster ${EKS_CLUSTER}"
aws eks update-kubeconfig --name "$EKS_CLUSTER" --region "$AWS_REGION" >/dev/null

echo "==> kubectl set image deployment/${DEPLOYMENT} ${CONTAINER}=${IMAGE}"
kubectl -n "$NAMESPACE" set image "deployment/${DEPLOYMENT}" "${CONTAINER}=${IMAGE}"

echo "==> Waiting for rollout to complete (timeout 5m)"
kubectl -n "$NAMESPACE" rollout status "deployment/${DEPLOYMENT}" --timeout=300s

echo ""
echo "==> Released ${IMAGE}"
