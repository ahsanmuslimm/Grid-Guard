#!/bin/bash
# =============================================================
# GridGuard — Cloud Run Deployment Script (Phase 09)
# Run from REPO ROOT: bash deploy/deploy_cloudrun.sh
# Prerequisites: GCP project set up, secrets stored (Phase 07)
# =============================================================

set -e

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gridguard-agent-2026}"
REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
SERVICE_NAME="gridguard"
SA_EMAIL="gridguard-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo "=============================================="
echo "  GridGuard — Cloud Run Deployment"
echo "  Project : ${PROJECT_ID}"
echo "  Region  : ${REGION}"
echo "  Service : ${SERVICE_NAME}"
echo "=============================================="
echo ""

# ── Preflight checks ─────────────────────────────────────────
echo "[0/4] Preflight checks..."
gcloud config set project "${PROJECT_ID}"
gcloud config set run/region "${REGION}"

# Verify secrets exist
echo "  Checking secrets..."
gcloud secrets describe PHOENIX_API_KEY --project="${PROJECT_ID}" > /dev/null 2>&1 \
  && echo "  ✓ PHOENIX_API_KEY found" \
  || echo "  ⚠ PHOENIX_API_KEY not found — Phoenix tracing will be disabled"

gcloud secrets describe NVD_API_KEY --project="${PROJECT_ID}" > /dev/null 2>&1 \
  && echo "  ✓ NVD_API_KEY found" \
  || echo "  ⚠ NVD_API_KEY not found — NVD will use fallback CVEs"

# ── Deploy ────────────────────────────────────────────────────
echo ""
echo "[1/4] Deploying to Cloud Run (3-5 minutes)..."

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 10 \
  --timeout 300 \
  --concurrency 80 \
  --service-account "${SA_EMAIL}" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars "GOOGLE_CLOUD_REGION=${REGION}" \
  --set-env-vars "GRIDGUARD_ENV=production" \
  --set-env-vars "LOG_LEVEL=INFO" \
  --set-env-vars "PHOENIX_BASE_URL=https://app.phoenix.arize.com" \
  --set-secrets "PHOENIX_API_KEY=PHOENIX_API_KEY:latest" \
  --set-secrets "NVD_API_KEY=NVD_API_KEY:latest"

# ── Get URL ───────────────────────────────────────────────────
echo ""
echo "[2/4] Retrieving service URL..."
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --format "value(status.url)")

echo "  ✓ Live URL: ${SERVICE_URL}"

# ── Health check ──────────────────────────────────────────────
echo ""
echo "[3/4] Health check (waiting 10s for container warm-up)..."
sleep 10
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/health" 2>/dev/null || echo "000")

if [ "${HTTP_STATUS}" = "200" ]; then
  echo "  ✓ Health check passed (HTTP 200)"
else
  echo "  ⚠ Health check returned HTTP ${HTTP_STATUS}"
  echo "  → Check logs: gcloud run logs read --service ${SERVICE_NAME} --region ${REGION} --limit 50"
fi

# ── External network test hint ────────────────────────────────
echo ""
echo "[4/4] Post-deploy checklist..."
echo "  □ Test from a DIFFERENT device/network (not localhost)"
echo "  □ Open ${SERVICE_URL} in a browser"
echo "  □ Inject ransomware attack — full cycle should complete in <90s"
echo "  □ Verify Arize Phoenix shows traces at https://app.phoenix.arize.com/projects/gridguard"
echo "  □ Copy URL for Devpost submission"

echo ""
echo "=============================================="
echo "  ✅ Deployment Complete!"
echo ""
echo "  SUBMISSION URL:"
echo "  ${SERVICE_URL}"
echo ""
echo "  Save this. You'll need it for Devpost."
echo "=============================================="
