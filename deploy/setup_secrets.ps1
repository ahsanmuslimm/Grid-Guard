# =============================================================
# GridGuard — GCP Secret Manager Setup (Phase 07)
# Run from repo root: .\deploy\setup_secrets.ps1
# Requires gcloud CLI authenticated and project set
# =============================================================

param(
    [string]$ProjectId = "gridguard-agent-2026"
)

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  GridGuard — Secret Manager Setup"
Write-Host "  Project: $ProjectId"
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Set project
gcloud config set project $ProjectId

# ── PHOENIX_API_KEY ───────────────────────────────────────────
Write-Host "--- Arize Phoenix API Key ---" -ForegroundColor Yellow
Write-Host "Get yours at: https://app.phoenix.arize.com -> Settings -> API Keys"
$phoenixKey = Read-Host "Enter PHOENIX_API_KEY" -AsSecureString
$phoenixPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($phoenixKey)
)

if ($phoenixPlain) {
    # Create or update secret
    $exists = gcloud secrets describe PHOENIX_API_KEY --project=$ProjectId 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Updating existing PHOENIX_API_KEY..." -ForegroundColor Gray
        $phoenixPlain | gcloud secrets versions add PHOENIX_API_KEY --data-file=-
    } else {
        Write-Host "  Creating PHOENIX_API_KEY..." -ForegroundColor Gray
        $phoenixPlain | gcloud secrets create PHOENIX_API_KEY --data-file=- --replication-policy=automatic
    }
    Write-Host "  ✓ PHOENIX_API_KEY stored in Secret Manager" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Skipped PHOENIX_API_KEY (empty input)" -ForegroundColor Yellow
}

# ── NVD_API_KEY ───────────────────────────────────────────────
Write-Host ""
Write-Host "--- NVD API Key (optional) ---" -ForegroundColor Yellow
Write-Host "Register free at: https://nvd.nist.gov/developers/request-an-api-key"
Write-Host "Press Enter to skip."
$nvdKey = Read-Host "Enter NVD_API_KEY"

if ($nvdKey) {
    $exists = gcloud secrets describe NVD_API_KEY --project=$ProjectId 2>$null
    if ($LASTEXITCODE -eq 0) {
        $nvdKey | gcloud secrets versions add NVD_API_KEY --data-file=-
    } else {
        $nvdKey | gcloud secrets create NVD_API_KEY --data-file=- --replication-policy=automatic
    }
    Write-Host "  ✓ NVD_API_KEY stored in Secret Manager" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Skipped NVD_API_KEY (NVD will use fallback CVEs)" -ForegroundColor Yellow
}

# ── Verify ────────────────────────────────────────────────────
Write-Host ""
Write-Host "--- Verification ---" -ForegroundColor Yellow
Write-Host "Secrets in project $ProjectId:"
gcloud secrets list --project=$ProjectId --format="table(name,createTime)"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  ✅ Secret Manager setup complete!"
Write-Host "  Next: bash deploy/deploy_cloudrun.sh"
Write-Host "==============================================" -ForegroundColor Green
