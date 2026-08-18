#!/bin/bash
# =============================================================
# GridGuard — GCP Infrastructure Setup Script (Phase 02)
# Run this once to configure your GCP project from scratch.
# DO NOT run this more than once — it will error on duplicates.
# =============================================================

set -e  # Exit on any error

PROJECT_ID="gridguard-agent-2026"
PROJECT_NAME="GridGuard"
REGION="us-central1"
SA_NAME="gridguard-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
STAGING_BUCKET="gs://gridguard-staging-${PROJECT_ID}"

echo ""
echo "=============================================="
echo "  GridGuard GCP Setup"
echo "  Project: ${PROJECT_ID}"
echo "=============================================="
echo ""

# ── Step 1: Authenticate ──────────────────────────────────────
echo "[1/9] Authenticating with Google Cloud..."
gcloud auth login
gcloud auth application-default login

# ── Step 2: Create Project ────────────────────────────────────
echo "[2/9] Creating GCP project: ${PROJECT_ID}..."
gcloud projects create ${PROJECT_ID} --name="${PROJECT_NAME}" || echo "  → Project already exists, skipping"
gcloud config set project ${PROJECT_ID}
echo "  ✓ Active project: $(gcloud config get-value project)"

# ── Step 3: Enable APIs ───────────────────────────────────────
echo "[3/9] Enabling required APIs (this takes ~2 minutes)..."
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
echo "  ✓ All 9 APIs enabled"

# ── Step 4: Create Service Account ───────────────────────────
echo "[4/9] Creating service account: ${SA_NAME}..."
gcloud iam service-accounts create ${SA_NAME} \
  --display-name="GridGuard Service Account" || echo "  → SA already exists, skipping"

# Grant required roles
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user" --quiet

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" --quiet

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker" --quiet

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin" --quiet

echo "  ✓ Service account created with 4 roles"

# ── Step 5: Download Credentials Key ─────────────────────────
echo "[5/9] Downloading credentials key to ./credentials/gcp-key.json..."
mkdir -p ./credentials
gcloud iam service-accounts keys create ./credentials/gcp-key.json \
  --iam-account="${SA_EMAIL}"
echo "  ✓ Key downloaded — NEVER commit credentials/ to git!"

# ── Step 6: Set Environment Variables ────────────────────────
echo "[6/9] Setting environment variables..."
export GOOGLE_APPLICATION_CREDENTIALS="./credentials/gcp-key.json"
export GOOGLE_CLOUD_PROJECT="${PROJECT_ID}"
export GOOGLE_CLOUD_REGION="${REGION}"
echo "  ✓ Env vars set for this session"
echo "  → Add these to your .env file manually"

# ── Step 7: Create Staging Bucket ─────────────────────────────
echo "[7/9] Creating Cloud Storage staging bucket..."
gcloud storage buckets create ${STAGING_BUCKET} \
  --location=${REGION} \
  --uniform-bucket-level-access || echo "  → Bucket already exists, skipping"
echo "  ✓ Staging bucket: ${STAGING_BUCKET}"

# ── Step 8: Create Secrets in Secret Manager ─────────────────
echo "[8/9] Setting up Secret Manager secrets..."
echo "  → You will be prompted to enter your API keys"

echo -n "Enter your Arize Phoenix API key: "
read -s PHOENIX_KEY
echo ""
echo -n "${PHOENIX_KEY}" | gcloud secrets create PHOENIX_API_KEY \
  --data-file=- --replication-policy=automatic 2>/dev/null || \
  echo -n "${PHOENIX_KEY}" | gcloud secrets versions add PHOENIX_API_KEY --data-file=-
echo "  ✓ PHOENIX_API_KEY stored"

echo -n "Enter your NVD API key (press Enter to skip): "
read -s NVD_KEY
echo ""
if [ -n "${NVD_KEY}" ]; then
  echo -n "${NVD_KEY}" | gcloud secrets create NVD_API_KEY \
    --data-file=- --replication-policy=automatic 2>/dev/null || \
    echo -n "${NVD_KEY}" | gcloud secrets versions add NVD_API_KEY --data-file=-
  echo "  ✓ NVD_API_KEY stored"
else
  echo "  → NVD_API_KEY skipped (rate limits apply without key)"
fi

# ── Step 9: Verify Setup ──────────────────────────────────────
echo "[9/9] Verifying setup..."
echo "  Project: $(gcloud config get-value project)"
echo "  Region:  $(gcloud config get-value run/region 2>/dev/null || echo 'not set')"
echo "  Secrets: $(gcloud secrets list --format='value(name)' | tr '\n' ' ')"

echo ""
echo "=============================================="
echo "  ✅ GCP Setup Complete!"
echo "  Next: pip install -r requirements.txt"
echo "  Then: python main.py"
echo "=============================================="
