param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$ProjectRoot\build", "$ProjectRoot\dist", "$ProjectRoot\dist-installer", "$ProjectRoot\installer\payload"
}

Write-Host "Installing PyInstaller..." -ForegroundColor Cyan
python -m pip install --upgrade pyinstaller

Write-Host "Building Retrocore application bundle..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm .\retrocore.spec

Write-Host "Packaging application payload..." -ForegroundColor Cyan
$payloadDir = Join-Path $ProjectRoot "installer\payload"
New-Item -ItemType Directory -Force -Path $payloadDir | Out-Null
$payloadZip = Join-Path $payloadDir "retrocore-package.zip"
if (Test-Path -LiteralPath $payloadZip) {
    Remove-Item -LiteralPath $payloadZip -Force
}
Compress-Archive -Path "$ProjectRoot\dist\retrocore" -DestinationPath $payloadZip -CompressionLevel Optimal

Write-Host "Building Retrocore installer wizard..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm .\installer\retrocore_installer.spec

Write-Host "Collecting installer artifact..." -ForegroundColor Cyan
$installerOutDir = Join-Path $ProjectRoot "dist-installer"
New-Item -ItemType Directory -Force -Path $installerOutDir | Out-Null
Copy-Item -LiteralPath "$ProjectRoot\dist\retrocore-installer.exe" -Destination (Join-Path $installerOutDir "retrocore-setup.exe") -Force

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "Application bundle: $ProjectRoot\dist\retrocore" -ForegroundColor DarkGray
Write-Host "Installer output:  $ProjectRoot\dist-installer" -ForegroundColor DarkGray
