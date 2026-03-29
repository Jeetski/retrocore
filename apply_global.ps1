param(
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SnapshotsDir = Join-Path $ProjectRoot "snapshots"
$GeneratedShader = Join-Path $ProjectRoot "shaders\retrocore.generated.hlsl"
$FallbackShader = Join-Path $ProjectRoot "shaders\crt-subtle.hlsl"
$LocalStateDir = Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState"
$SettingsPath = Join-Path $LocalStateDir "settings.json"
$TargetShaderName = "retrocore.generated.hlsl"
$TargetShaderPath = Join-Path $LocalStateDir $TargetShaderName

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

function Ensure-ObjectProperty {
    param(
        [Parameter(Mandatory = $true)][object]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($property) {
        if ($null -eq $property.Value) {
            $property.Value = [pscustomobject]@{}
        }
        return $property.Value
    }

    $child = [pscustomobject]@{}
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $child
    return $child
}

function Set-ObjectProperty {
    param(
        [Parameter(Mandatory = $true)][object]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][object]$Value
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($property) {
        $property.Value = $Value
    }
    else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function ConvertFrom-JsonC {
    param(
        [Parameter(Mandatory = $true)][string]$Text
    )

    $withoutBlockComments = [regex]::Replace($Text, '/\*.*?\*/', '', [System.Text.RegularExpressions.RegexOptions]::Singleline)
    $withoutLineComments = [regex]::Replace($withoutBlockComments, '(?m)(?<!https:)(?<!http:)//.*$', '')
    $withoutTrailingCommas = [regex]::Replace($withoutLineComments, ',(\s*[\}\]])', '$1')
    return $withoutTrailingCommas | ConvertFrom-Json
}

if (Test-Path -LiteralPath $GeneratedShader) {
    $SourceShader = $GeneratedShader
    $SourceKind = "generated Retrocore shader"
}
elseif (Test-Path -LiteralPath $FallbackShader) {
    $SourceShader = $FallbackShader
    $SourceKind = "fallback shader snapshot"
}
else {
    throw "No source shader was found in the project."
}

if (-not (Test-Path -LiteralPath $SettingsPath)) {
    throw "Windows Terminal settings were not found at $SettingsPath"
}

Write-Host "Retrocore standalone global apply" -ForegroundColor Green
Write-Host "This will copy a shader into Windows Terminal LocalState and enable it globally through profiles.defaults." -ForegroundColor DarkGray
Write-Host "Source shader: $SourceShader ($SourceKind)" -ForegroundColor DarkGray
Write-Host "Target shader: $TargetShaderPath" -ForegroundColor DarkGray

if (-not (Ask-YesNo -Prompt "Apply Retrocore globally now?" -Default $true)) {
    Write-Host "No changes were made." -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Force -Path $LocalStateDir, $SnapshotsDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $SnapshotsDir "settings.standalone.apply.$timestamp.json"
Copy-Item -LiteralPath $SettingsPath -Destination $backupPath -Force

Copy-Item -LiteralPath $SourceShader -Destination $TargetShaderPath -Force

$settings = ConvertFrom-JsonC -Text (Get-Content -LiteralPath $SettingsPath -Raw)
$profiles = Ensure-ObjectProperty -Object $settings -Name "profiles"
$defaults = Ensure-ObjectProperty -Object $profiles -Name "defaults"
Set-ObjectProperty -Object $defaults -Name "experimental.pixelShaderPath" -Value $TargetShaderName
$settings | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $SettingsPath -Encoding UTF8

Write-Host ""
Write-Host "Retrocore was applied globally." -ForegroundColor Green
Write-Host "Settings backup: $backupPath" -ForegroundColor DarkGray
Write-Host "Restart Windows Terminal to see the change." -ForegroundColor DarkGray
