param([string]$DirectorioInforme = ('../../output/evaluacion_tfg/integracion_' + (Get-Date -Format 'yyyyMMdd_HHmmss')))
$ErrorActionPreference = 'Stop'
$raizBackend = Split-Path $PSScriptRoot -Parent
$destinoInforme = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $DirectorioInforme))
if (Test-Path (Join-Path $destinoInforme 'suite.xml')) { throw 'El directorio ya contiene una campaña; elija otro para conservar el histórico.' }
New-Item -ItemType Directory -Path $destinoInforme -Force | Out-Null
$anteriores = @{}
foreach ($nombre in @('COVERAGE_FILE','PYTHONPATH','PYTHONIOENCODING','DB_PASSWORD','JWT_SECRET_KEY','GESTUAL_REAL_TESTS','GESTUAL_REPORT_DIR')) {
    $anteriores[$nombre] = [Environment]::GetEnvironmentVariable($nombre,'Process')
}
Push-Location $raizBackend
try {
    # Solo se acepta el contenedor de pruebas, nunca el PostgreSQL habitual.
    $contenedor = 'gestual-tfg-tests-20261027'
    # Leer JSON evita que Windows PowerShell pierda las comillas de Go templates.
    $existentes = @(docker ps -a --filter "name=^/$contenedor$" --format '{{.Names}}')
    if ($LASTEXITCODE -ne 0) { throw 'No se puede acceder a Docker.' }
    if ($contenedor -notin $existentes) {
        docker run --name $contenedor --label gestual.purpose=tfg-tests -e POSTGRES_PASSWORD=gestual-test-local -e POSTGRES_DB=gestual_test -p 127.0.0.1:55432:5432 -d postgres:16-alpine
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear PostgreSQL aislado.' }
    } else {
        $detalle = docker inspect $contenedor | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo inspeccionar el contenedor.' }
        if ($detalle[0].Config.Labels.'gestual.purpose' -ne 'tfg-tests') {
            throw 'El contenedor no tiene la marca de pruebas.'
        }
    }
    docker start $contenedor | Out-Null
    $listo = $false
    for ($i=0; $i -lt 30; $i++) {
        docker exec $contenedor pg_isready -U postgres -d gestual_test *> $null
        if ($LASTEXITCODE -eq 0) { $listo=$true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $listo) { throw 'PostgreSQL de pruebas no está listo.' }
    $env:COVERAGE_FILE = Join-Path $destinoInforme '.coverage'
    $env:PYTHONPATH = '.'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:DB_PASSWORD = 'test-only-no-database'
    $env:JWT_SECRET_KEY = 'test-only-key-for-isolated-validation-2026'
    $env:GESTUAL_REAL_TESTS = '1'
    $env:GESTUAL_REPORT_DIR = $destinoInforme
    $medicion = @('--cov=api','--cov=core','--cov=db','--cov=domain','--cov=models','--cov=repositories','--cov=services','--cov=solver')
    & ./.venv/Scripts/python.exe -m pytest tests -q @medicion "--cov-report=json:$destinoInforme/cobertura_suite.json" "--junitxml=$destinoInforme/suite.xml"
    if ($LASTEXITCODE -ne 0) { throw 'Falló la suite principal.' }
    & ./.venv/Scripts/python.exe -m pytest checks/test_limites_horarios.py checks/test_procesos_criticos.py checks/test_persistencia_critica.py checks/test_permisos_http_criticos.py -q @medicion --cov-append "--cov-report=json:$destinoInforme/cobertura_complementarias.json" "--junitxml=$destinoInforme/complementarias.xml"
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las comprobaciones complementarias.' }
    & ./.venv/Scripts/python.exe -m pytest integration_real/test_postgresql.py integration_real/test_e2e.py -q @medicion --cov-append "--cov-report=json:$destinoInforme/cobertura_sin_api_subproceso.json" "--junitxml=$destinoInforme/integracion_e2e.xml"
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron los escenarios de integración o E2E.' }
    Copy-Item -LiteralPath $env:COVERAGE_FILE -Destination (Join-Path $destinoInforme '.coverage.pytest')
    & ./.venv/Scripts/python.exe -m coverage combine --keep $destinoInforme
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo combinar la cobertura.' }
    & ./.venv/Scripts/python.exe -m coverage json -o (Join-Path $destinoInforme 'cobertura_total.json')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo exportar la cobertura.' }
    Write-Output "Campaña completa: $destinoInforme"
}
finally {
    foreach ($nombre in $anteriores.Keys) { [Environment]::SetEnvironmentVariable($nombre,$anteriores[$nombre],'Process') }
    Pop-Location
}
