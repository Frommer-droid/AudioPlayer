param([string]$WorkRoot = "")
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if (-not $WorkRoot) {
    $version = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
    $WorkRoot = Join-Path (Split-Path $projectRoot -Parent) "temp-dev\AudioPlayer\release-$version"
}
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runtimePaths = & $pythonExe -c "import sys,PySide6; from pathlib import Path; print(Path(PySide6.__file__).parent); print(sys.base_prefix)"
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve project runtime' }
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$helperVersion = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
$helperName = "AudioPlayerShell-$helperVersion.dll"
& (Join-Path $PSScriptRoot 'build_shell_helper.ps1') -OutputPath (Join-Path $WorkRoot "native\$helperName")
$buildTarget = [IO.Path]::GetFullPath((Join-Path $projectRoot 'AudioPlayer'))
if ($buildTarget -ne ([IO.Path]::GetFullPath($projectRoot) + '\AudioPlayer')) { throw 'Bad build target' }
if (Test-Path -LiteralPath $buildTarget) { throw 'Existing build: preserve settings and explicitly remove the verified build directory before rebuilding' }
$savedPath = $env:PATH
try {
    $env:PATH = @($runtimePaths[0], (Join-Path $projectRoot '.venv\Scripts'), $runtimePaths[1],
        (Join-Path $runtimePaths[1] 'DLLs'), (Join-Path $env:SystemRoot 'System32')) -join ';'
    $env:AUDIOPLAYER_BINARY_REPORT = Join-Path $WorkRoot 'binary-origins.json'
    & $pythonExe -m PyInstaller --noconfirm --distpath $projectRoot --workpath (Join-Path $WorkRoot 'work') (Join-Path $PSScriptRoot 'AudioPlayer.spec') *> (Join-Path $WorkRoot 'build.log')
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $WorkRoot\build.log" }
    & $pythonExe (Join-Path $PSScriptRoot 'post_build.py')
    if ($LASTEXITCODE -ne 0) { throw 'post_build failed' }
    Copy-Item -LiteralPath (Join-Path $WorkRoot "native\$helperName") -Destination $buildTarget
} finally { $env:PATH = $savedPath }
