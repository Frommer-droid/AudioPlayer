param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
$installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $installation) { throw 'MSVC x64 Build Tools are required for AudioPlayerShell' }
$toolVersion = (Get-Content -LiteralPath (Join-Path $installation 'VC\Auxiliary\Build\Microsoft.VCToolsVersion.default.txt') -Raw).Trim()
$tools = Join-Path $installation "VC\Tools\MSVC\$toolVersion"
$sdk = 'C:\Program Files (x86)\Windows Kits\10'
$sdkVersion = Get-ChildItem -LiteralPath (Join-Path $sdk 'Include') -Directory | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty Name
$output = [IO.Path]::GetFullPath($OutputPath)
$work = Split-Path $output -Parent
New-Item -ItemType Directory -Path $work -Force | Out-Null
$savedHelperPath = $env:PATH
$savedHelperInclude = $env:INCLUDE
$savedHelperLib = $env:LIB
$savedHelperTemp = $env:TEMP
$savedHelperTmp = $env:TMP
try {
    $env:PATH = (Join-Path $tools 'bin\Hostx64\x64') + ';' + (Join-Path $env:SystemRoot 'System32')
    $env:INCLUDE = @((Join-Path $tools 'include'), "$sdk\Include\$sdkVersion\ucrt", "$sdk\Include\$sdkVersion\um", "$sdk\Include\$sdkVersion\shared", "$sdk\Include\$sdkVersion\winrt") -join ';'
    $env:LIB = @((Join-Path $tools 'lib\x64'), "$sdk\Lib\$sdkVersion\ucrt\x64", "$sdk\Lib\$sdkVersion\um\x64") -join ';'
    $env:TEMP = $env:TMP = $work
    & (Join-Path $tools 'bin\Hostx64\x64\cl.exe') /nologo /std:c++17 /O2 /MT /LD /EHsc /W4 /utf-8 /DUNICODE /D_UNICODE "/Fe:$output" "/Fo:$work\AudioPlayerShell.obj" (Join-Path $PSScriptRoot 'shell_helper.cpp') /link /SUBSYSTEM:WINDOWS /Brepro "/DEF:$PSScriptRoot\shell_helper.def" ole32.lib shell32.lib user32.lib advapi32.lib uuid.lib
    if ($LASTEXITCODE -ne 0) { throw 'AudioPlayerShell native compilation failed' }
} finally {
    $env:PATH = $savedHelperPath
    $env:INCLUDE = $savedHelperInclude
    $env:LIB = $savedHelperLib
    $env:TEMP = $savedHelperTemp
    $env:TMP = $savedHelperTmp
}
