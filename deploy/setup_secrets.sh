#!/bin/bash
# =============================================================
# GridGuard — GCP Secret Manager Setup (Phase 07)
# Run from repo root: bash deploy/setup_secrets.sh
# =============================================================

set -e
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-grid-guard-507218}"

echo ""
echo "=============================================="
echo "  GridGuard — Secret Manager Setup"
echo "  Project: ${PROJECT_ID}"
echo "=============================================="
echo ""

gcloud config set project "${PROJECT_ID}"

# Helper: create or update a secret
upsert_secret() {
    local NAME=$1
    local VALUE=$2
    if gcloud secrets describe "${NAME}" --project="${PROJECT_ID}" > /dev/null 2>&1; then
        echo -n "${VALUE}" | gcloud secrets versions add "${NAME}" --data-file=-
        echo "  ✓ ${NAME} updated"
    else
        echo -n "${VALUE}" | gcloud secrets create "${NAME}" \
            --data-file=- --replication-policy=automatic
        echo "  ✓ ${NAME} created"
    fi
}

# ── PHOENIX_API_KEY ───────────────────────────────────────────
echo "--- Arize Phoenix API Key ---"
echo "Get yours at: https://app.phoenix.arize.com → Settings → API Keys"
read -s -p "Enter PHOENIX_API_KEY: " PHOENIX_KEY
echo ""
if [ -n "${PHOENIX_KEY}" ]; then
    upsert_secret "PHOENIX_API_KEY" "${PHOENIX_KEY}"
else
    echo "  ⚠ Skipped PHOENIX_API_KEY"
fi

# ── NVD_API_KEY ───────────────────────────────────────────────
echo ""
echo "--- NVD API Key (optional, improves rate limits) ---"
echo "Register free at: https://nvd.nist.gov/developers/request-an-api-key"
read -s -p "Enter NVD_API_KEY (Enter to skip): " NVD_KEY
echo ""
if [ -n "${NVD_KEY}" ]; then
    upsert_secret "NVD_API_KEY" "${NVD_KEY}"
else
    echo "  ⚠ Skipped NVD_API_KEY"
fi

# ── Verify ────────────────────────────────────────────────────
echo ""
echo "Secrets stored in ${PROJECT_ID}:"
gcloud secrets list --project="${PROJECT_ID}" --format="table(name)"

echo ""
echo "=============================================="
echo "  ✅ Done! Next: bash deploy/deploy_cloudrun.sh"
echo "=============================================="
