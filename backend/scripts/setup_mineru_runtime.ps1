param(
  [string]$RuntimeDir = "backend\.venv-mineru",
  [switch]$SkipInstall,
  [switch]$Smoke
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$runtimePath = Join-Path $repoRoot $RuntimeDir
$pythonExe = Join-Path $runtimePath "Scripts\python.exe"
$mineruExe = Join-Path $runtimePath "Scripts\mineru.exe"

if (-not (Test-Path $pythonExe)) {
  py -3.12 -m venv $runtimePath
}

if (-not $SkipInstall) {
  & $pythonExe -m pip install --upgrade pip
  & $pythonExe -m pip install -r (Join-Path $repoRoot "backend\requirements-mineru.txt") --extra-index-url https://download.pytorch.org/whl/cpu
}

if (-not (Test-Path $mineruExe)) {
  throw "MinerU CLI was not installed at $mineruExe"
}

& $mineruExe --help | Select-Object -First 24

if ($Smoke) {
  $validationDir = Join-Path $repoRoot "backend\generated\reference-ingestion\validation-pdfs"
  $pdfs = Get-ChildItem $validationDir -Filter "*-real.pdf" -ErrorAction SilentlyContinue
  if ($pdfs.Count -lt 2) {
    throw "Expected at least two *-real.pdf files in $validationDir"
  }

  $env:PYTHONPATH = Join-Path $repoRoot "backend"
  $env:BOS_MINERU_COMMAND = $mineruExe
  $env:BOS_MINERU_EXTRA_ARGS = "-b pipeline -m txt -s 0 -e 1"
  & $pythonExe (Join-Path $repoRoot "backend\scripts\reference_ingestion_smoke.py") `
    $pdfs[0].FullName $pdfs[1].FullName `
    --storage-root "backend/generated/reference-ingestion/smoke-mineru-runtime" `
    --promote-first
}

Write-Output "MinerU runtime ready: $mineruExe"
