param([string]$PythonExecutable = "python")
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PreviousTemp = $env:TEMP
$PreviousTmp = $env:TMP
$PreviousPipCache = $env:PIP_CACHE_DIR
$LocalTemp = Join-Path $ProjectRoot '.local/tmp'
New-Item -ItemType Directory -Force -Path $LocalTemp | Out-Null
$env:TEMP = $LocalTemp
$env:TMP = $LocalTemp
$env:PIP_CACHE_DIR = Join-Path $ProjectRoot '.local/pip-cache'
Push-Location -LiteralPath $ProjectRoot
try {
    & $PythonExecutable -c "import sys; assert sys.version_info[:2] == (3,12), 'Use Python 3.12'"
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 não encontrado no executável indicado." }
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        & $PythonExecutable -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente." }
    }
    $ProjectPython = Join-Path $ProjectRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath 'requirements.lock') {
        & $ProjectPython -m pip install -r requirements.lock
        if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências fixadas." }
        & $ProjectPython -m pip install --no-deps --no-build-isolation -e .
    } else {
        & $ProjectPython -m pip install -e '.[dev]'
    }
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar o projeto." }
    if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
    & $ProjectPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Dependências incompatíveis." }
    & $ProjectPython -m entregacerta.cli doctor --skip-tools
    if ($LASTEXITCODE -ne 0) { throw "Diagnóstico do ambiente falhou." }
} finally {
    Pop-Location
    $env:TEMP = $PreviousTemp
    $env:TMP = $PreviousTmp
    $env:PIP_CACHE_DIR = $PreviousPipCache
}
