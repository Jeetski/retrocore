param(
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectCommand = Join-Path $ProjectRoot "retrocore.cmd"
$ShimRoot = Join-Path $env:LOCALAPPDATA "Retrocore\bin"
$ShimPath = Join-Path $ShimRoot "retrocore.cmd"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Cyan
}

function Ask-YesNo {
    param(
        [string]$Prompt,
        [bool]$Default = $true
    )

    if ($Yes) {
        return $true
    }

    $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }
    $response = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($response)) {
        return $Default
    }

    switch ($response.Trim().ToLowerInvariant()) {
        "y" { return $true }
        "yes" { return $true }
        "n" { return $false }
        "no" { return $false }
        default {
            Write-Host "Please answer y or n." -ForegroundColor Yellow
            return Ask-YesNo -Prompt $Prompt -Default $Default
        }
    }
}

function Get-PythonCommand {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        try {
            & py -3 -c "import sys" *> $null
            if ($LASTEXITCODE -eq 0) {
                return "py -3"
            }
        }
        catch {
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        try {
            & python -c "import sys" *> $null
            if ($LASTEXITCODE -eq 0) {
                return "python"
            }
        }
        catch {
        }
    }

    return $null
}

function Show-PythonVersion {
    param([string]$PythonCommand)
    if ($PythonCommand -eq "py -3") {
        & py -3 --version
        return
    }
    & python --version
}

function Test-TkAvailability {
    param([string]$PythonCommand)

    if ($PythonCommand -eq "py -3") {
        & py -3 -c "import tkinter" *> $null
        return ($LASTEXITCODE -eq 0)
    }

    & python -c "import tkinter" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Install-Python {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Python was not found and winget is unavailable. Install Python 3 manually, then rerun this script."
    }

    Write-Host "Installing Python 3.11 with winget..." -ForegroundColor Cyan
    & winget install --exact --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install Python."
    }
}

function Ensure-PathContains {
    param([string]$Directory)

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($userPath) {
        $parts = $userPath -split ";" | Where-Object { $_ }
    }

    $alreadyPresent = $false
    foreach ($part in $parts) {
        if ($part.Trim().TrimEnd("\") -ieq $Directory.Trim().TrimEnd("\")) {
            $alreadyPresent = $true
            break
        }
    }

    if (-not $alreadyPresent) {
        $newParts = @($parts + $Directory)
        [Environment]::SetEnvironmentVariable("Path", ($newParts -join ";"), "User")
        if (-not (($env:Path -split ";") | Where-Object { $_.Trim().TrimEnd("\") -ieq $Directory.Trim().TrimEnd("\") })) {
            $env:Path = "$Directory;$env:Path"
        }
        Write-Host "Added to user PATH: $Directory" -ForegroundColor Green
    }
    else {
        Write-Host "User PATH already contains: $Directory" -ForegroundColor DarkGray
    }
}

function Write-RetrocoreShim {
    param(
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    $destinationDir = Split-Path -Parent $DestinationPath
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null

    $shimContent = @"
@echo off
setlocal
call "$ProjectCommand" %*
"@
    Set-Content -LiteralPath $DestinationPath -Value $shimContent -Encoding Ascii
    Write-Host "Created shim: $DestinationPath" -ForegroundColor Green
}

function Update-LegacyShimIfNeeded {
    $pathEntries = @()
    if ($env:Path) {
        $pathEntries += ($env:Path -split ";" | Where-Object { $_ })
    }
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath) {
        $pathEntries += ($userPath -split ";" | Where-Object { $_ })
    }

    $seen = @{}
    foreach ($entry in $pathEntries) {
        $normalized = $entry.Trim().TrimEnd("\")
        if (-not $normalized) {
            continue
        }
        if ($seen.ContainsKey($normalized.ToLowerInvariant())) {
            continue
        }
        $seen[$normalized.ToLowerInvariant()] = $true

        if (-not ($normalized -like "$env:USERPROFILE\\*")) {
            continue
        }

        $candidate = Join-Path $normalized "retrocore.cmd"
        if (-not (Test-Path -LiteralPath $candidate)) {
            continue
        }
        if ($candidate -ieq $ShimPath) {
            continue
        }

        Write-Host "Updating existing user shim that could shadow the new install: $candidate" -ForegroundColor Yellow
        Write-RetrocoreShim -DestinationPath $candidate
    }
}

Write-Host "Retrocore guided install" -ForegroundColor Green
Write-Host "This script will check Python, create a retrocore command shim, and optionally add it to your user PATH." -ForegroundColor DarkGray
Write-Host "Project folder: $ProjectRoot" -ForegroundColor DarkGray
Write-Host "If you move this project later, rerun this installer so the shim points at the new location." -ForegroundColor DarkGray

if (-not (Ask-YesNo -Prompt "Continue with setup?" -Default $true)) {
    Write-Host "Setup cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Step "Checking Python"
$pythonCommand = Get-PythonCommand
if (-not $pythonCommand) {
    Write-Host "Python 3 was not found." -ForegroundColor Yellow
    if (-not (Ask-YesNo -Prompt "Install Python 3.11 with winget now?" -Default $true)) {
        throw "Python is required for Retrocore."
    }
    Install-Python
    $pythonCommand = Get-PythonCommand
    if (-not $pythonCommand) {
        throw "Python still was not detected after installation."
    }
}

Write-Host "Python detected via: $pythonCommand" -ForegroundColor Green
Show-PythonVersion -PythonCommand $pythonCommand
if (Test-TkAvailability -PythonCommand $pythonCommand) {
    Write-Host "Tkinter support detected. Retrocore Manager UI is available." -ForegroundColor Green
}
else {
    Write-Host "Tkinter was not detected in this Python install. CLI commands will work, but 'retrocore manager' will not launch." -ForegroundColor Yellow
}

if (Ask-YesNo -Prompt "Create a global 'retrocore' command shim?" -Default $true) {
    Write-Step "Creating retrocore command shim"
    Write-RetrocoreShim -DestinationPath $ShimPath
    Update-LegacyShimIfNeeded

    if (Ask-YesNo -Prompt "Add the shim directory to your user PATH?" -Default $true) {
        Ensure-PathContains -Directory $ShimRoot
    }
    else {
        Write-Host "Skipped PATH update. You can still run the shim directly at $ShimPath" -ForegroundColor Yellow
    }
}

if (Ask-YesNo -Prompt "Run a quick Retrocore status check now?" -Default $true) {
    Write-Step "Running verification"
    & $ProjectCommand status
}

Write-Host ""
Write-Host "Retrocore install setup is complete." -ForegroundColor Green
Write-Host "Open a new terminal window if PATH was changed during this run." -ForegroundColor DarkGray
