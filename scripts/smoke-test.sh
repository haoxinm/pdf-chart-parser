#!/usr/bin/env bash
# =============================================================================
# Smoke-test the pdf-chart-parser MCP server running in a Kubernetes cluster.
#
# Uses kubectl port-forward to reach the ClusterIP Service, then sends a
# JSON-RPC tools/list request to verify the server is up and the
# extract_usage_chart tool is registered.
#
# Usage:
#   scripts/smoke-test.sh [env]
#     [env]  dev | staging | prod  (used only for logging; optional)
#
# Required tools: kubectl, curl.
#
# Optional env:
#   EKS_CLUSTER  EKS cluster name; if set, updates kubeconfig first.
#   AWS_REGION   AWS region for kubeconfig update (default: us-west-2).
#   NAMESPACE    Kubernetes namespace (default: pdf-chart-parser).
#   SERVICE      Service name (default: pdf-chart-parser).
#   LOCAL_PORT   Local port for the port-forward (default: 18000).
# =============================================================================
set -euo pipefail

ENV="${1:-}"
AWS_REGION="${AWS_REGION:-us-west-2}"
NAMESPACE="${NAMESPACE:-pdf-chart-parser}"
SERVICE="${SERVICE:-pdf-chart-parser}"
LOCAL_PORT="${LOCAL_PORT:-18000}"
REMOTE_PORT=8000

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*" >&2; exit 1; }

[ -n "$ENV" ] && echo "==> env=$ENV  namespace=$NAMESPACE  service=$SERVICE"

# ─── Optional: update kubeconfig ─────────────────────────────────────────────
if [ -n "${EKS_CLUSTER:-}" ]; then
  echo "==> Updating kubeconfig for ${EKS_CLUSTER}"
  aws eks update-kubeconfig --name "$EKS_CLUSTER" --region "$AWS_REGION" >/dev/null
fi

# ─── Verify pod is running ────────────────────────────────────────────────────
echo "==> Checking pod readiness in namespace ${NAMESPACE}"
if ! kubectl -n "$NAMESPACE" get pods \
    -l "app.kubernetes.io/name=pdf-chart-parser" \
    --field-selector=status.phase=Running \
    --no-headers 2>/dev/null | grep -q .; then
  fail "No Running pods found in namespace ${NAMESPACE}. Is the deployment up?"
fi
pass "At least one pod is Running"

# ─── Port-forward ────────────────────────────────────────────────────────────
echo "==> Starting port-forward ${LOCAL_PORT} → ${NAMESPACE}/${SERVICE}:${REMOTE_PORT}"
kubectl -n "$NAMESPACE" port-forward \
  "svc/${SERVICE}" "${LOCAL_PORT}:${REMOTE_PORT}" \
  >/dev/null 2>&1 &
PF_PID=$!
trap 'kill "$PF_PID" 2>/dev/null || true' EXIT

# Give the tunnel a moment to establish.
sleep 2

BASE_URL="http://localhost:${LOCAL_PORT}"

# ─── Connectivity check ───────────────────────────────────────────────────────
echo "==> Checking TCP connectivity"
if ! curl -fsS --max-time 5 --output /dev/null "$BASE_URL/mcp" 2>/dev/null \
   && ! curl -fsS --max-time 5 --output /dev/null "$BASE_URL/" 2>/dev/null; then
  # A 4xx response still means the server is up — check if we get any HTTP back
  http_code=$(curl -so /dev/null -w '%{http_code}' --max-time 5 "$BASE_URL/mcp" 2>/dev/null || echo "000")
  if [ "$http_code" = "000" ]; then
    fail "No HTTP response from ${BASE_URL} — port-forward may not have established"
  fi
fi
pass "HTTP server is reachable"

# ─── MCP tools/list ──────────────────────────────────────────────────────────
# stateless_http=True + json_response=True: each POST /mcp is independent,
# no prior initialize handshake required.
echo "==> POST /mcp  method=tools/list"
tools_response=$(curl -fsS --max-time 15 \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  "${BASE_URL}/mcp" 2>/dev/null) || {
    fail "POST /mcp tools/list failed (exit $?). Is the server up and the MCP transport set to streamable-http?"
  }

if echo "$tools_response" | grep -q '"extract_usage_chart"'; then
  pass "extract_usage_chart tool is registered"
else
  fail "extract_usage_chart not found in tools/list response:
$tools_response"
fi

echo ""
echo "==> All smoke checks passed."
