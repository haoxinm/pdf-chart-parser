#!/usr/bin/env bash
# =============================================================================
# Build the pdf-chart-parser Docker image and push it to ECR.
#
# Usage:
#   ECR_REPO=<registry>/<repo> ./scripts/build_and_push.sh
#
# Required env:
#   ECR_REPO    Full ECR repository URI
#               (e.g., 123456789012.dkr.ecr.us-west-2.amazonaws.com/pdf-chart-parser)
#
# Optional env:
#   TAG         Image tag override. Defaults to the 12-char short git SHA of HEAD.
#   AWS_REGION  ECR registry region. Defaults to us-west-2.
# =============================================================================
set -euo pipefail

: "${ECR_REPO:?ECR_REPO must be set to your ECR repository URI}"

AWS_REGION="${AWS_REGION:-us-west-2}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

DEFAULT_TAG="$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD)"
TAG="${TAG:-${DEFAULT_TAG}}"

echo "==> Building ${ECR_REPO}:${TAG}"
docker build --platform linux/amd64 \
  -f "${REPO_ROOT}/docker/Dockerfile" \
  -t "${ECR_REPO}:${TAG}" \
  "${REPO_ROOT}"

echo "==> Logging in to ECR"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REPO%%/*}"

echo "==> Pushing ${ECR_REPO}:${TAG}"
docker push "${ECR_REPO}:${TAG}"

echo "==> Done: ${ECR_REPO}:${TAG}"
