param([string]$PostgresBin = 'D:\Postgre\bin', [int]$Port = 8019)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path '.venv\Scripts\python.exe')) { throw 'Create the Python environment first; see README.md.' }
$env:ADRIVA_LIBPQ_DIR = $PostgresBin
$env:ADRIVA_DATABASE_URL = 'postgresql://adriva@127.0.0.1:55439/adriva'
& .venv\Scripts\python.exe tools\run_local.py tools.local start --port $Port
if ($LASTEXITCODE -ne 0) { throw 'ADRIVA startup failed. Inspect .local logs.' }
