#!/usr/bin/env bash
set -euo pipefail

ECR_REPO="<PLACEHOLDER_ECR_REPO>"  # e.g. 123456789012.dkr.ecr.us-east-1.amazonaws.com/pdf-chart-parser
AWS_REGION="${AWS_REGION:-us-east-1}"
TAG="${1:-latest}"

if [[ "$ECR_REPO" == "<PLACEHOLDER_ECR_REPO>" ]]; then
    echo "ERROR: Set ECR_REPO to your ECR repository URI before running this script." >&2
    echo "  e.g. ECR_REPO=123456789012.dkr.ecr.us-east-1.amazonaws.com/pdf-chart-parser" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Building image: ${ECR_REPO}:${TAG}"
docker build -f "${REPO_ROOT}/docker/Dockerfile" -t "${ECR_REPO}:${TAG}" "${REPO_ROOT}"

echo "Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${ECR_REPO%%/*}"

echo "Pushing image..."
docker push "${ECR_REPO}:${TAG}"

echo "Done: ${ECR_REPO}:${TAG}"
