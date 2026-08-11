[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $HarnessArgs
)

$ErrorActionPreference = 'Stop'

$command = Get-Command -Name 'android-harness.exe' -ErrorAction SilentlyContinue
if ($null -ne $command) {
    & $command.Source @HarnessArgs
    exit $LASTEXITCODE
}

$pyLauncher = Get-Command -Name 'py.exe' -ErrorAction SilentlyContinue
if ($null -ne $pyLauncher) {
    $probeArguments = @(
        '-3'
        '-c'
        'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("android_harness") else 1)'
    )
    & $pyLauncher.Source @probeArguments *> $null
    if ($LASTEXITCODE -eq 0) {
        $pythonArguments = @('-3', '-m', 'android_harness.cli') + $HarnessArgs
        & $pyLauncher.Source @pythonArguments
        exit $LASTEXITCODE
    }
}

$python = Get-Command -Name 'python.exe' -ErrorAction SilentlyContinue
if ($null -ne $python) {
    $probeArguments = @(
        '-c'
        'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("android_harness") else 1)'
    )
    & $python.Source @probeArguments *> $null
    if ($LASTEXITCODE -eq 0) {
        $pythonArguments = @('-m', 'android_harness.cli') + $HarnessArgs
        & $python.Source @pythonArguments
        exit $LASTEXITCODE
    }
}

throw 'Android Harness is not installed. From its repository, run: py -3 -m pip install --user .'
