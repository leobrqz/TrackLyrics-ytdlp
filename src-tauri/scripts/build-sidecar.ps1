$ErrorActionPreference = 'Stop'

$tauriDir = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $tauriDir
$entryPoint = Join-Path $repoRoot 'src\sidecar\main.py'
$requirements = Join-Path $repoRoot 'requirements-backend.txt'
$binaryDir = Join-Path $tauriDir 'binaries'
$workDir = Join-Path $env:TEMP 'tracklyrics-sidecar-build'

if (-not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
    throw "Python sidecar entry point not found: $entryPoint"
}
if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    throw "Backend dependency file not found: $requirements"
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    throw 'Python 3 is required to build the TrackLyrics backend sidecar.'
}

function Get-RustHostTriple {
    $tuple = (& rustc --print host-tuple 2>$null).Trim()
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($tuple)) {
        return $tuple
    }
    $verbose = & rustc -Vv
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not determine the host Rust target triple.'
    }
    $hostLine = $verbose | Where-Object { $_ -match '^host: ' } | Select-Object -First 1
    if ($null -eq $hostLine) {
        throw 'Rust did not report a host target triple.'
    }
    return ($hostLine -replace '^host: ', '').Trim()
}

$hostTriple = Get-RustHostTriple
$target = $env:TAURI_ENV_TARGET_TRIPLE
if ([string]::IsNullOrWhiteSpace($target)) {
    $target = $hostTriple
}
if ($target -ne $hostTriple) {
    throw "The Python sidecar must be built for the host architecture. Requested '$target', host is '$hostTriple'."
}

New-Item -ItemType Directory -Force -Path $binaryDir, $workDir | Out-Null
& $pythonCommand.Source -m pip install -r $requirements pyinstaller
if ($LASTEXITCODE -ne 0) {
    throw 'Could not install backend build dependencies.'
}

& $pythonCommand.Source -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --console `
    --name tracklyrics-backend `
    --paths (Join-Path $repoRoot 'src') `
    --collect-all imageio_ffmpeg `
    --add-data "$($repoRoot)\assets;assets" `
    --distpath $binaryDir `
    --workpath $workDir `
    --specpath $workDir `
    $entryPoint
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller failed while building the TrackLyrics backend sidecar.'
}

$builtBinary = Join-Path $binaryDir 'tracklyrics-backend.exe'
$targetBinary = Join-Path $binaryDir "tracklyrics-backend-$target.exe"
if (-not (Test-Path -LiteralPath $builtBinary -PathType Leaf)) {
    throw "PyInstaller did not produce the expected executable: $builtBinary"
}
Move-Item -LiteralPath $builtBinary -Destination $targetBinary -Force
Write-Output "Built sidecar: $targetBinary"
