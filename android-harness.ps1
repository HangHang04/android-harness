[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $HarnessArgs
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSCommandPath
$env:PYTHONPATH = Join-Path $projectRoot 'src'

$launcher = Get-Command -Name 'py.exe' -ErrorAction SilentlyContinue
if ($null -ne $launcher) {
    $pythonArgs = @('-3', '-m', 'android_harness.cli') + $HarnessArgs
    & $launcher.Source @pythonArgs
    exit $LASTEXITCODE
}

$python = Get-Command -Name 'python.exe' -ErrorAction Stop
$pythonArgs = @('-m', 'android_harness.cli') + $HarnessArgs
& $python.Source @pythonArgs
exit $LASTEXITCODE
