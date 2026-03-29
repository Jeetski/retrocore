$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CommandPath = Join-Path $ProjectRoot "retrocore.cmd"

if (-not (Test-Path -LiteralPath $CommandPath)) {
    throw "retrocore.cmd was not found at $CommandPath"
}

& $CommandPath manager @args
