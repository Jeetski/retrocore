param(
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SnapshotsDir = Join-Path $ProjectRoot "snapshots"
$LocalStateDir = Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState"
$SettingsPath = Join-Path $LocalStateDir "settings.json"
$ManagedValues = @(
    "retrocore.generated.hlsl",
    (Join-Path $LocalStateDir "retrocore.generated.hlsl")
)

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

function Remove-ObjectPropertyIfManagedValue {
    param(
        [Parameter(Mandatory = $true)][object]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$AllowedValues
    )

    $property = $Object.PSObject.Properties[$Name]
    if (-not $property) {
        return $false
    }

    foreach ($allowedValue in $AllowedValues) {
        if ($property.Value -eq $allowedValue) {
            $Object.PSObject.Properties.Remove($Name) | Out-Null
            return $true
        }
    }

    return $false
}

if (-not (Test-Path -LiteralPath $SettingsPath)) {
    throw "Windows Terminal settings were not found at $SettingsPath"
}

Write-Host "Retrocore standalone global removal" -ForegroundColor Green
Write-Host "This removes only Retrocore-managed shader paths from Windows Terminal settings." -ForegroundColor DarkGray

if (-not (Ask-YesNo -Prompt "Remove Retrocore's standalone global shader settings now?" -Default $true)) {
    Write-Host "No changes were made." -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Force -Path $SnapshotsDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $SnapshotsDir "settings.standalone.remove.$timestamp.json"
Copy-Item -LiteralPath $SettingsPath -Destination $backupPath -Force

$settings = Get-Content -LiteralPath $SettingsPath -Raw | ConvertFrom-Json
$removedDefaults = $false
$removedProfiles = @()

$profilesProperty = $settings.PSObject.Properties["profiles"]
if ($profilesProperty) {
    $profilesRoot = $profilesProperty.Value
    $defaultsProperty = $profilesRoot.PSObject.Properties["defaults"]
    if ($defaultsProperty) {
        $removedDefaults = Remove-ObjectPropertyIfManagedValue -Object $defaultsProperty.Value -Name "experimental.pixelShaderPath" -AllowedValues $ManagedValues
    }

    $listProperty = $profilesRoot.PSObject.Properties["list"]
    if ($listProperty) {
        foreach ($profile in $listProperty.Value) {
            if (Remove-ObjectPropertyIfManagedValue -Object $profile -Name "experimental.pixelShaderPath" -AllowedValues $ManagedValues) {
                $removedProfiles += $profile.name
            }
        }
    }
}

$settings | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $SettingsPath -Encoding UTF8

Write-Host ""
Write-Host "Retrocore standalone settings removal completed." -ForegroundColor Green
Write-Host "Settings backup: $backupPath" -ForegroundColor DarkGray
if ($removedDefaults) {
    Write-Host "Removed Retrocore shader from profiles.defaults." -ForegroundColor DarkGray
}
if ($removedProfiles.Count -gt 0) {
    Write-Host ("Removed Retrocore shader from profiles: " + ($removedProfiles -join ", ")) -ForegroundColor DarkGray
}
Write-Host "Restart Windows Terminal to see the change." -ForegroundColor DarkGray
