# GridGuard Secret Manager setup for Windows PowerShell.
param([string]$ProjectId = "grid-guard-507218")

$ErrorActionPreference = "Stop"

function ConvertFrom-GridGuardSecureString {
    param([Security.SecureString]$SecureValue)
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Set-GridGuardSecret {
    param([string]$Name, [string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        Write-Host "  [SKIP] $Name is empty" -ForegroundColor Yellow
        return
    }

    # --data-file avoids the newline PowerShell pipelines append to native
    # commands. The temporary file is deleted immediately in finally.
    $temporaryPath = [IO.Path]::GetTempFileName()
    try {
        [IO.File]::WriteAllText(
            $temporaryPath,
            $Value.Trim(),
            [Text.UTF8Encoding]::new($false)
        )
        & gcloud secrets describe $Name --project=$ProjectId *> $null
        if ($LASTEXITCODE -eq 0) {
            & gcloud secrets versions add $Name --project=$ProjectId --data-file=$temporaryPath
        }
        else {
            & gcloud secrets create $Name --project=$ProjectId `
                --data-file=$temporaryPath --replication-policy=automatic
        }
        if ($LASTEXITCODE -ne 0) {
            throw "gcloud failed while storing $Name"
        }
        Write-Host "  [OK] $Name stored" -ForegroundColor Green
    }
    finally {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "GridGuard Secret Manager - project $ProjectId" -ForegroundColor Cyan
& gcloud config set project $ProjectId
if ($LASTEXITCODE -ne 0) { throw "Unable to select GCP project $ProjectId" }

$phoenixSecure = Read-Host "Enter PHOENIX_API_KEY" -AsSecureString
$phoenixPlain = ConvertFrom-GridGuardSecureString $phoenixSecure
try { Set-GridGuardSecret "PHOENIX_API_KEY" $phoenixPlain }
finally { $phoenixPlain = $null }

$nvdSecure = Read-Host "Enter NVD_API_KEY" -AsSecureString
$nvdPlain = ConvertFrom-GridGuardSecureString $nvdSecure
try { Set-GridGuardSecret "NVD_API_KEY" $nvdPlain }
finally { $nvdPlain = $null }

Write-Host "Secrets now present:" -ForegroundColor Cyan
& gcloud secrets list --project=$ProjectId --format="table(name,createTime)"
