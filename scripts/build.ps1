param(
    [string]$Version = "dev"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Create .venv first: python -m venv .venv" }

& $Python -m PyInstaller --noconfirm --clean --onedir --noconsole `
    --name VoiceLaunch `
    --collect-all faster_whisper --collect-all ctranslate2 `
    --add-data "$ProjectRoot\config;config" `
    --add-data "$ProjectRoot\assets;assets" `
    --icon "$ProjectRoot\assets\voicelaunch.ico" `
    --paths "$ProjectRoot\src" `
    --distpath "$ProjectRoot\release" `
    --workpath "$ProjectRoot\build" `
    --specpath "$ProjectRoot\build" `
    "$ProjectRoot\run_voicelaunch.py"

Write-Host "Built release\VoiceLaunch\VoiceLaunch.exe ($Version)"
