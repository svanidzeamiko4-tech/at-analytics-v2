# Start RS.GE APScheduler worker (separate from Streamlit)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Pkg = Join-Path $Root "phase_2_dashboard"
Set-Location $Pkg
$env:PYTHONPATH = $Pkg
python -m workers.rs_ge_worker @args
