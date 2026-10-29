"""Previsualización segura de exportaciones de ordenación docente."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from core.auth import require_admin
from repositories import ActividadRepository, AreaRepository, DepartamentoRepository
from services.importacion_docente import (
    ErrorImportacionDocente,
    importar_escenario_sintetico,
    leer_exportacion_bytes,
    resumen_importacion,
)


router = APIRouter(prefix="/api/v1/importacion", tags=["importación"])
_TAMANO_MAXIMO_CSV = 10 * 1024 * 1024


async def _leer_csv_subido(fichero: UploadFile) -> list[dict[str, str]]:
    """Valida el fichero común a las tres operaciones de importación."""
    if not (fichero.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Selecciona un fichero CSV.")
    contenido = await fichero.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El fichero está vacío.")
    if len(contenido) > _TAMANO_MAXIMO_CSV:
        raise HTTPException(status_code=413, detail="El CSV supera el límite de 10 MB.")
    try:
        return leer_exportacion_bytes(contenido)
    except ErrorImportacionDocente as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/previsualizar", summary="Previsualizar un CSV sin importarlo")
async def previsualizar_csv(
    fichero: UploadFile = File(...),
    _: dict = Depends(require_admin),
):
    """Valida y resume el CSV recibido. No modifica la base de datos."""
    try:
        return resumen_importacion(await _leer_csv_subido(fichero))
    except ErrorImportacionDocente as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/planificar", summary="Planificar importación sin escribir datos")
async def planificar_csv(
    fichero: UploadFile = File(...),
    _: dict = Depends(require_admin),
):
    """Compara el CSV con los catálogos existentes; no modifica la base de datos."""
    try:
        from services.importacion_docente import planificar_importacion
        filas = await _leer_csv_subido(fichero)
        return planificar_importacion(
            filas,
            DepartamentoRepository().find_all(),
            AreaRepository().find_all(),
            ActividadRepository().find_all(),
        )
    except ErrorImportacionDocente as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/crear-escenario-prueba", summary="Crear escenario de prueba desde un CSV")
async def crear_escenario_prueba(
    fichero: UploadFile = File(...),
    password_temporal: str = Form(...),
    confirmar: bool = Form(False),
    _: dict = Depends(require_admin),
):
    """Crea catálogo, perfiles y horarios sintéticos sin importar repartos.

    La confirmación explícita impide que una previsualización se convierta por
    error en una escritura. La función de servicio abre una única transacción:
    ante cualquier conflicto no persiste ningún dato parcial.
    """
    if not confirmar:
        raise HTTPException(
            status_code=400,
            detail="Confirma la creación del escenario de prueba antes de continuar.",
        )
    try:
        filas = await _leer_csv_subido(fichero)
        return importar_escenario_sintetico(filas, password_temporal)
    except ErrorImportacionDocente as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
