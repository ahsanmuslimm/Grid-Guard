# Google Cloud and production handoff

Run these steps after installing the Google Cloud CLI. Commands assume
PowerShell in the repository root and an activated `venv`.

## 1. Authenticate

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud config set run/region us-central1
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

Do not create a downloadable service-account JSON key. Local code uses ADC and
Cloud Run/Agent Engine use the attached `gridguard-sa` identity.

## 2. Confirm non-secret environment settings

Keep the existing API keys and set:

```env
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
GOOGLE_CLOUD_REGION=us-central1
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_ENTERPRISE=1
GRIDGUARD_MODEL=gemini-3-flash-preview
PHOENIX_PROJECT_NAME=gridguard
GRIDGUARD_ENABLE_PHOENIX_MCP=true
```

Remove `GOOGLE_APPLICATION_CREDENTIALS` when it points to a missing JSON file.

In Phoenix Settings, copy the exact API/application base for your workspace.
Some accounts require a space path such as `https://app.phoenix.arize.com/s/...`.
Set that full value as `PHOENIX_BASE_URL`.

## 3. Provision GCP

From Git Bash or Cloud Shell:

```bash
bash deploy/gcp_setup.sh
```

The script enables Vertex AI, Cloud Run, Cloud Build, Secret Manager, Artifact
Registry, logging, monitoring and telemetry; creates `gridguard-sa`; prepares
Cloud Build IAM; creates the Docker repository and staging bucket; and prompts
for both API secrets.

If infrastructure already exists and only secrets are missing, use PowerShell:

```powershell
.\deploy\setup_secrets.ps1 -ProjectId YOUR_PROJECT_ID
```

## 4. Run live checks before deployment

```powershell
python verify_integrations.py --nvd
python verify_integrations.py --phoenix-api --phoenix-mcp
python verify_integrations.py --gemini --attack ddos
```

Use DDoS for unattended verification. Ransomware and unauthorized access wait
for dashboard approval.

## 5. Run locally

```powershell
python main.py
```

Open `http://localhost:8080`, test all four attacks, approve both gated attacks,
and confirm reports, replay events and evaluation scores.

## 6. Deploy Agent Engine

```powershell
python deploy/deploy_agent_engine.py
```

Save the printed Agent Engine resource name. The Cloud Run application remains
the interactive dashboard/runtime and hosts Phoenix MCP because its container
includes Node.js/npx.

## 7. Deploy Cloud Run

From Git Bash or Cloud Shell:

```bash
bash deploy/deploy_cloudrun.sh
```

This submits `deploy/cloudbuild.yaml`, builds `deploy/Dockerfile`, pushes to
Artifact Registry and deploys one warm Cloud Run instance with Secret Manager
bindings.

## 8. Production verification

```powershell
$serviceUrl = gcloud run services describe gridguard --region us-central1 --format="value(status.url)"
Invoke-RestMethod "$serviceUrl/health"
Invoke-RestMethod -Method Post "$serviceUrl/api/inject-attack/ddos"
gcloud run services logs read gridguard --region us-central1 --limit 100
```

Then test all four attacks in a browser on an external network and confirm the
Cloud Run trace plus `hallucination` and `response_quality` annotations in
Phoenix.

