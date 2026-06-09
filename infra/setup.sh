#!/usr/bin/env bash
# =============================================================================
# Env-agnostic wrapper around the per-env IaC lifecycle.
#
# Usage:
#   ./infra/setup.sh <env> [--yes] [--plan-only]
#
# Where <env> is the name of a directory under infra/ (e.g., dev, staging, prod).
#
# Steps:
#   1. Resolve infra/<env>/.
#   2. Verify AWS creds are live.
#   3. Verify backend.hcl and terraform.tfvars exist.
#   4. Validate required tfvars fields.
#   5. terraform init -backend-config=backend.hcl -upgrade.
#   6. terraform plan -out=plan.tfplan.
#   7. Confirm and apply (skip with --yes or --plan-only).
#   8. Print next_steps output.
# =============================================================================
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./infra/setup.sh <env> [--yes] [--plan-only]

Arguments:
  <env>        Required. Directory name under infra/. e.g. dev | staging | prod.

Flags:
  --yes        Skip the interactive Apply? prompt.
  --plan-only  Run init + plan only; do not apply.
  -h, --help   This message.

Examples:
  ./infra/setup.sh dev
  ./infra/setup.sh dev --yes
  ./infra/setup.sh prod --plan-only
EOF
}

if [ $# -lt 1 ]; then
  usage >&2
  exit 1
fi

ENV_NAME=""
YES=0
PLAN_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --yes)        YES=1 ;;
    --plan-only)  PLAN_ONLY=1 ;;
    -h|--help)    usage; exit 0 ;;
    --*)
      echo "FATAL: unknown flag $arg" >&2; usage >&2; exit 1 ;;
    *)
      if [ -z "$ENV_NAME" ]; then
        ENV_NAME="$arg"
      else
        echo "FATAL: unexpected positional arg: $arg" >&2; usage >&2; exit 1
      fi
      ;;
  esac
done

if [ -z "$ENV_NAME" ]; then
  echo "FATAL: missing <env> argument" >&2
  usage >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${SCRIPT_DIR}/${ENV_NAME}"

if [ ! -d "$ENV_DIR" ]; then
  echo "FATAL: env directory not found: $ENV_DIR" >&2
  echo "       Available envs:" >&2
  find "$SCRIPT_DIR" -mindepth 1 -maxdepth 1 -type d ! -name modules \
    -exec basename {} \; | sed 's/^/         - /' >&2
  exit 1
fi

cd "$ENV_DIR"
echo "==> env = $ENV_NAME"
echo "==> cwd = $ENV_DIR"

# ─── Tool preflight ────────────────────────────────────────────────────────
require_tool() {
  command -v "$1" >/dev/null 2>&1 \
    || { echo "FATAL: $1 not on PATH" >&2; exit 1; }
}
require_tool terraform
require_tool aws
require_tool kubectl

# ─── AWS auth ──────────────────────────────────────────────────────────────
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "FATAL: AWS credentials are not available. Log in and retry." >&2
  exit 1
fi

# ─── Input file checks ─────────────────────────────────────────────────────
[ -f backend.hcl ] || {
  echo "FATAL: ${ENV_DIR}/backend.hcl missing."
  echo "       cp backend.hcl.example backend.hcl && edit it."
  exit 1
}
[ -f terraform.tfvars ] || {
  echo "FATAL: ${ENV_DIR}/terraform.tfvars missing."
  echo "       cp terraform.tfvars.example terraform.tfvars && edit it."
  exit 1
}

# Uncommented lines only (strip comments for validation).
tfvars_uc() { grep -v '^[[:space:]]*#' terraform.tfvars; }

if tfvars_uc | grep -E 'subnet_ids[[:space:]]*=[[:space:]]*\[[[:space:]]*\]' >/dev/null 2>&1; then
  echo "FATAL: terraform.tfvars: subnet_ids is empty." >&2
  echo "       Fill in at least 2 private subnet IDs." >&2
  exit 1
fi

if tfvars_uc | grep -E 'fargate_execution_role_arn[[:space:]]*=[[:space:]]*""' >/dev/null 2>&1; then
  echo "FATAL: terraform.tfvars: fargate_execution_role_arn is empty." >&2
  exit 1
fi

# ─── Init ──────────────────────────────────────────────────────────────────
echo "==> terraform init"
terraform init -backend-config=backend.hcl -upgrade

# ─── Plan ──────────────────────────────────────────────────────────────────
echo "==> terraform plan"
terraform plan -out=plan.tfplan

if [ $PLAN_ONLY -eq 1 ]; then
  echo "==> Plan-only mode; not applying. Plan saved to plan.tfplan."
  exit 0
fi

# ─── Apply gate ────────────────────────────────────────────────────────────
if [ $YES -eq 0 ]; then
  printf "Apply? [y/N] "
  read -r reply
  case "$reply" in
    y|Y|yes|YES) ;;
    *) echo "Aborted."; exit 0 ;;
  esac
fi

echo "==> terraform apply"
terraform apply -auto-approve plan.tfplan
rm -f plan.tfplan

# ─── Next steps ────────────────────────────────────────────────────────────
echo ""
echo "==> Done. Next steps:"
echo ""
terraform output -raw next_steps 2>/dev/null || terraform output next_steps
