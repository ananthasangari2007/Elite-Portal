<#
Apply database migrations (and optionally seed the admin + domains) against a given database.
Usage (PowerShell):
  .\.venv\Scripts\Activate.ps1
  .\scripts\run_migrations.ps1 -Dsn "postgresql://user:pass@host:5432/db?sslmode=require" [-Seed]
Migrations are additive; nothing is dropped. Back up the database before running against production.
#>

param(
  [Parameter(Mandatory=$true)]
  [string]$Dsn,
  [switch]$Seed
)

$env:DATABASE_URL = $Dsn
Write-Host "DATABASE_URL set for this session (value not printed)."

Write-Host "Running database migrations (python -m app.cli db-upgrade)"
& .\.venv\Scripts\python.exe -m app.cli db-upgrade
if ($LASTEXITCODE -ne 0) {
    Write-Host "Migrations failed."
    exit 1
}
Write-Host "Migrations completed."

if ($Seed) {
    Write-Host "Seeding admin user and default domains (idempotent; requires ADMIN_PASSWORD)"
    & .\.venv\Scripts\python.exe -m app.cli seed-all
    if ($LASTEXITCODE -ne 0) { Write-Host "Seeding failed."; exit 1 }
}
