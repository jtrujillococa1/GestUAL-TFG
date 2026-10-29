# Publicar_GestUAL_GitHub.ps1
# 1. Crear ANTES un repositorio vacio GestUAL-TFG en github.com/jtrujillococa1
#    (sin README, sin .gitignore y sin licencia inicial).
# 2. Descomprimir este paquete.
# 3. Desde PowerShell: powershell -ExecutionPolicy Bypass -File .\Publicar_GestUAL_GitHub.ps1
# Requiere Git para Windows y autenticacion con permiso de escritura.
param(
    [string]$Repositorio = "https://github.com/jtrujillococa1/GestUAL-TFG.git"
)
$ErrorActionPreference = 'Stop'
$carpeta = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git no esta instalado. Instala Git para Windows antes de publicar."
}
if (Test-Path (Join-Path $carpeta '.git')) {
    throw "Este directorio ya contiene .git. No se repetira una publicacion automaticamente."
}
Push-Location $carpeta
try {
    & git init -b main
    if ($LASTEXITCODE -ne 0) { throw 'Error al inicializar Git.' }
    & git add --all
    if ($LASTEXITCODE -ne 0) { throw 'Error al preparar los archivos.' }
    & git commit -m 'Publicacion academica inicial GestUAL TFG'
    if ($LASTEXITCODE -ne 0) { throw 'Error al confirmar archivos. Configura git user.name y user.email.' }
    & git remote add origin $Repositorio
    if ($LASTEXITCODE -ne 0) { throw 'Error al configurar GitHub como remoto.' }
    & git push -u origin main
    if ($LASTEXITCODE -ne 0) { throw 'Error al subir. Comprueba que el repositorio existe, esta vacio y has iniciado sesion.' }
    Write-Host "Publicado en: $($Repositorio -replace '\.git$', '')"
} finally {
    Pop-Location
}
