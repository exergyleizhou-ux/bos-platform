param(
  [switch]$InstallDeps,
  [switch]$DownloadChronosBolt,
  [switch]$DownloadTimerS1,
  [switch]$DownloadYolo11Dsconv
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendDir = Join-Path $RepoRoot "backend"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $RepoRoot "backend\requirements-native-models.txt"

if (-not (Test-Path $Python)) {
  throw "Python virtual environment not found at $Python"
}

if ($InstallDeps) {
  & $Python -m pip install -r $Requirements
}

if ($DownloadChronosBolt) {
  Push-Location $BackendDir
  & $Python -c "from app.services.bos_native_runtime import download_native_model_artifact; print(download_native_model_artifact(model_key='chronos_bolt'))"
  Pop-Location
}

if ($DownloadTimerS1) {
  Push-Location $BackendDir
  & $Python -c "from app.services.bos_native_runtime import download_native_model_artifact; print(download_native_model_artifact(model_key='timer_s1'))"
  Pop-Location
}

if ($DownloadYolo11Dsconv) {
  Push-Location $BackendDir
  & $Python -c "from app.services.bos_native_runtime import download_native_model_artifact; print(download_native_model_artifact(model_key='yolo11_dsconv'))"
  Pop-Location
}
