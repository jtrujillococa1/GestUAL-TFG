r"""Reconstruye el catálogo anonimizado con horarios oficiales publicados por UAL.

El CSV aporta las áreas, las cuotas y los alias de docentes. La relación que
aparece en ese CSV entre profesor y grupo NO se importa como adjudicación: la
ordenación empieza vacía. Los horarios se obtienen por asignatura, tipo y grupo
desde la API pública de la Universidad de Almería.

Uso (primero validación sin escribir):
Get-Content -Raw -Encoding UTF8 'C:\ruta\Ordenacion_Docente.csv' |
  docker compose exec -T backend python cargar_catalogo_ual_oficial.py --cache /tmp/ual-horarios.json

Para aplicar, tras revisar el resumen:
Get-Content -Raw -Encoding UTF8 'C:\ruta\Ordenacion_Docente.csv' |
  docker compose exec -T -e UAL_IMPORT_PASSWORD='contraseña-temporal-segura' backend \
  python cargar_catalogo_ual_oficial.py --aplicar --cache /tmp/ual-horarios.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from core.auth import get_password_hash
from core.horario import validar_sesion_horaria
from db.connection import conexion_ctx
from services.importacion_docente import (
    ErrorImportacionDocente,
    construir_fichas_actividad,
    construir_perfiles_sinteticos,
    leer_exportacion_bytes,
    requiere_horario_fijo,
    importar_escenario_sintetico,
)


API_DETALLE = "https://campus.ual.es/ual/api/estudios/asignaturas/asignatura/detalle/{plan}/{asignatura}/es"
CODIGOS_AREA = {"AR035", "AR075", "AR520", "AR570"}
# El CSV conserva el código histórico del plan. La API pública, sin embargo,
# publica el Grado de Matemáticas con el código de presentación ``0419``.
# Esta traducción se aplica solo al consultar UAL; nunca modifica el catálogo
# ni sus códigos de origen.
PLANES_UAL = {"419": "0419"}

# Fuentes de respaldo de UAL para asignaturas que no tienen aún una franja
# publicada en la API del curso 2026-27. No se inventan horas: las sesiones
# provienen de los calendarios oficiales 2025-26 y se trasladan 52 semanas
# para conservar día de la semana dentro del curso que se está ordenando.
FUENTE_HORARIO_INFO_2025_26 = "https://www.ual.es/application/files/6117/7885/7161/horarios_2025-26.pdf"
FUENTE_HORARIO_MUTDE_2025_26 = "https://www.ual.es/application/files/3017/5033/3581/horario_25_26_1er_cuatrimestre_16junio25.pdf"
FUENTE_CALENDARIO_DUAL_2025_26 = "https://www.ual.es/application/files/8917/5015/3799/7093_Calendario_MUTDE_2025-26.pdf"

# Solo se incluyen sesiones síncronas o actividades dirigidas con hora de
# inicio y fin explícitas en el calendario publicado. Las actividades
# asíncronas no ocupan una franja del docente y no deben producir solapes.
HORARIOS_REFERENCIA_2025_26: dict[tuple[str, str, str], tuple[str, list[tuple[str, str, str]]]] = {
    # El horario de aulas de Informática 2025-26 identifica A2 los lunes y A1
    # los jueves, de 20:00 a 21:00. Es una plantilla semanal, sin fecha única.
    ("40153328", "GT", "A1"): (FUENTE_HORARIO_INFO_2025_26, [("", "20:00", "21:00")]),
    ("40153328", "GT", "A2"): (FUENTE_HORARIO_INFO_2025_26, [("", "20:00", "21:00")]),
    # Máster en Transformación Digital de Empresas: calendario 2025-26.
    ("71461205", "GD", "A"): (FUENTE_HORARIO_MUTDE_2025_26, [
        ("2025-10-28", "18:00", "20:00"), ("2025-10-29", "18:00", "20:00"),
        ("2025-10-30", "18:00", "20:00"), ("2025-11-04", "18:00", "20:00"),
        ("2025-11-06", "18:00", "20:00"), ("2025-11-11", "18:00", "19:30"),
        ("2025-11-18", "18:00", "20:00"), ("2025-11-20", "18:00", "20:00"),
        ("2025-11-25", "18:00", "19:30"), ("2025-11-27", "18:00", "20:00"),
        ("2025-12-01", "16:00", "18:00"), ("2025-12-01", "18:00", "19:30"),
        ("2025-12-05", "16:00", "18:00"), ("2025-12-09", "18:00", "20:00"),
        ("2025-12-10", "18:00", "19:30"), ("2025-12-12", "18:00", "20:00"),
        ("2026-01-08", "18:00", "20:00"), ("2026-01-12", "18:00", "20:00"),
        ("2026-01-20", "18:00", "20:00"),
    ]),
    ("71461202", "GD", "A"): (FUENTE_HORARIO_MUTDE_2025_26, [
        ("2026-01-07", "16:00", "18:00"), ("2026-01-14", "16:00", "18:00"),
        ("2026-01-21", "16:00", "18:00"), ("2026-01-23", "16:00", "18:00"),
        ("2026-01-28", "16:00", "18:00"), ("2026-01-30", "16:00", "18:00"),
        ("2026-02-04", "16:00", "18:00"), ("2026-02-06", "16:00", "18:00"),
        ("2026-02-10", "16:00", "17:30"),
    ]),
    ("71461206", "GD", "A"): (FUENTE_HORARIO_MUTDE_2025_26, [
        ("2026-01-07", "18:00", "20:00"), ("2026-01-14", "18:00", "20:00"),
        ("2026-01-15", "18:00", "20:00"), ("2026-01-19", "18:00", "20:00"),
        ("2026-01-27", "16:00", "18:00"), ("2026-01-27", "18:00", "20:00"),
        ("2026-01-28", "18:00", "20:00"), ("2026-02-03", "16:00", "17:30"),
        ("2026-02-04", "18:00", "19:30"),
    ]),
}

# La UAL solo publica para esta materia dual el período de impartición en
# empresa, sin hora común. No se debe inventar una franja ni bloquear por un
# solape que no existe: queda registrada con la fuente para completarla si la
# coordinación facilita un calendario individual.
ACTIVIDADES_DUALES_SIN_FRANJA = {"71461607"}
DIA_UAL = {
    "LUN": (0, "Lunes"), "MAR": (1, "Martes"), "MIE": (2, "Miércoles"),
    "JUE": (3, "Jueves"), "VIE": (4, "Viernes"),
}
ZONA_UAL = ZoneInfo("Europe/Madrid")


def _normalizar(valor: object) -> str:
    texto = unicodedata.normalize("NFD", str(valor or "").strip().upper())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn" and c.isalnum())


def _hora(hora: object, minuto: object) -> str:
    return f"{int(hora):02d}:{int(str(minuto or '0')):02d}"


def _fecha_semana(inicio_periodo: str, dia_ual: str) -> date:
    """Obtiene la fecha local de la sesión dentro del período semanal UAL."""
    if dia_ual not in DIA_UAL:
        raise ErrorImportacionDocente(f"Día no reconocido en el horario UAL: {dia_ual!r}.")
    inicio = datetime.fromisoformat(inicio_periodo.replace("Z", "+00:00")).astimezone(ZONA_UAL).date()
    desplazamiento = (DIA_UAL[dia_ual][0] - inicio.weekday()) % 7
    return inicio + timedelta(days=desplazamiento)


def _sesiones_ual(grupo: dict[str, Any]) -> list[dict[str, str]]:
    sesiones: list[dict[str, str]] = []
    for periodo in grupo.get("hor") or []:
        inicio_periodo = periodo.get("per_datini")
        if not inicio_periodo:
            continue
        for franja in periodo.get("franjas") or []:
            dia_ual = str(franja.get("id_dia_semana") or "").upper()
            if dia_ual not in DIA_UAL:
                continue
            inicio = _hora(franja.get("horini"), franja.get("minini"))
            fin = _hora(franja.get("horfin"), franja.get("minfin"))
            try:
                validar_sesion_horaria(inicio, fin)
            except ValueError as error:
                raise ErrorImportacionDocente(
                    f"No se admite la franja publicada para el grupo {grupo.get('grupo')}: "
                    f"{inicio}-{fin}. {error}"
                ) from error
            sesiones.append({
                "fecha": _fecha_semana(str(inicio_periodo), dia_ual).isoformat(),
                "dia": DIA_UAL[dia_ual][1],
                "inicio": inicio,
                "fin": fin,
            })
    return sorted(sesiones, key=lambda s: (s["fecha"], s["inicio"], s["fin"]))


def _resumen_semanal(sesiones: Iterable[dict[str, str]]) -> tuple[str, str]:
    orden_dias = {nombre: posicion for posicion, nombre in enumerate(("Lunes", "Martes", "Miércoles", "Jueves", "Viernes"))}
    bloques = sorted(
        {(sesion["dia"], sesion["inicio"], sesion["fin"]) for sesion in sesiones},
        key=lambda bloque: (orden_dias.get(bloque[0], 99), bloque[1], bloque[2]),
    )
    return (
        ", ".join(dict.fromkeys(bloque[0] for bloque in bloques)),
        " | ".join(f"{dia} {inicio}-{fin}" for dia, inicio, fin in bloques),
    )


def _plan_ual(codigo_plan: object) -> str:
    """Resuelve el identificador público sin alterar el código importado."""
    plan = str(codigo_plan or "")
    return PLANES_UAL.get(plan, plan)


def _sesiones_referencia_2025_26(ficha: dict[str, Any]) -> tuple[list[dict[str, str]], str] | None:
    """Devuelve franjas oficiales del curso anterior adaptadas 52 semanas.

    Una fecha vacía representa una plantilla semanal explícita en el PDF. Es
    preferible a inventar fechas lectivas que la fuente no aporta.
    """
    clave = (str(ficha["codigo"]), str(ficha["tipo"]), str(ficha["codigo_grupo"]))
    referencia = HORARIOS_REFERENCIA_2025_26.get(clave)
    if referencia is None:
        return None
    fuente, bloques = referencia
    sesiones: list[dict[str, str]] = []
    for fecha_origen, inicio, fin in bloques:
        if fecha_origen:
            fecha_destino = date.fromisoformat(fecha_origen) + timedelta(days=364)
            dia = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")[fecha_destino.weekday()]
            sesiones.append({"fecha": fecha_destino.isoformat(), "dia": dia, "inicio": inicio, "fin": fin})
            continue
        # Administración de Bases de Datos se publica como horario semanal de
        # aulas: A2 el lunes y A1 el jueves, ambos de 20:00 a 21:00.
        dia = "Jueves" if clave[2] == "A1" else "Lunes"
        sesiones.append({"dia": dia, "inicio": inicio, "fin": fin})
    return sesiones, fuente


def _aplicar_horario_referencia(ficha: dict[str, Any]) -> bool:
    referencia = _sesiones_referencia_2025_26(ficha)
    if referencia is None:
        return False
    sesiones, fuente = referencia
    dias, horario = _resumen_semanal(sesiones)
    ficha.update({
        "requiere_horario": True, "dias": dias, "horario": horario,
        "horario_detallado": sesiones, "horario_confirmado": False,
        "origen_horario": "UAL_REFERENCIA_2025_26", "fuente_horario": fuente,
    })
    return True


def _aplicar_actividad_dual_sin_franja(ficha: dict[str, Any]) -> bool:
    if str(ficha["codigo"]) not in ACTIVIDADES_DUALES_SIN_FRANJA:
        return False
    ficha.update({
        "requiere_horario": False, "dias": None, "horario": None,
        "horario_detallado": [], "horario_confirmado": False,
        "origen_horario": "UAL_DUAL_SIN_FRANJA", "fuente_horario": FUENTE_CALENDARIO_DUAL_2025_26,
    })
    return True


def _descargar_detalle(plan: str, asignatura: str) -> dict[str, Any]:
    url = API_DETALLE.format(plan=plan, asignatura=asignatura)
    try:
        solicitud = Request(url, headers={"User-Agent": "GestUAL-catalogo-horarios/1.0"})
        with urlopen(solicitud, timeout=45) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ErrorImportacionDocente(f"No se pudo consultar el horario oficial de {plan}/{asignatura}: {exc}") from exc


def _cargar_detalles(fichas: list[dict], cache: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    datos: dict[tuple[str, str], dict[str, Any]] = {}
    if cache and cache.exists():
        try:
            bruto = json.loads(cache.read_text(encoding="utf-8"))
            datos = {tuple(clave.split("/", 1)): valor for clave, valor in bruto.items()}
        except (OSError, json.JSONDecodeError) as exc:
            raise ErrorImportacionDocente(f"La caché de horarios no es válida: {exc}") from exc

    claves = sorted({(_plan_ual(f["codigo_plan"]), str(f["codigo"])) for f in fichas if f.get("codigo_plan")})
    faltan = [clave for clave in claves if clave not in datos]
    def guardar_cache() -> None:
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(
                json.dumps({"/".join(clave): valor for clave, valor in datos.items()}, ensure_ascii=False),
                encoding="utf-8",
            )

    for indice, (plan, asignatura) in enumerate(faltan, start=1):
        if indice == 1 or indice % 25 == 0 or indice == len(faltan):
            print(f"Consultando horarios UAL: {indice}/{len(faltan)}", file=sys.stderr, flush=True)
        datos[(plan, asignatura)] = _descargar_detalle(plan, asignatura)
        # La validación puede tardar varios minutos; conservar el avance evita
        # repetir consultas públicas si se reinicia el proceso local.
        if indice % 10 == 0:
            guardar_cache()
        # Ritmo deliberadamente moderado con un servicio público.
        if indice < len(faltan):
            time.sleep(0.18)

    guardar_cache()
    return datos


def _grupo_oficial(ficha: dict, detalle: dict[str, Any]) -> dict[str, Any] | None:
    """Relaciona exactamente tipo y código de grupo, sin usar docentes reales."""
    asignaturas = detalle.get("asignatura") or []
    if not asignaturas:
        return None
    esperados = {
        _normalizar(ficha.get("codigo_grupo_oficial")),
        _normalizar(ficha.get("codigo_grupo")),
        _normalizar(ficha.get("grupo")),
    }
    esperados.discard("")
    candidatos: list[dict[str, Any]] = []
    for actividad in asignaturas[0].get("actividades") or []:
        if _normalizar(actividad.get("abrv_tipo_grupo")) != _normalizar(ficha.get("tipo")):
            continue
        for grupo in actividad.get("grupos") or []:
            if _normalizar(grupo.get("grupo")) in esperados:
                candidatos.append(grupo)
    if len(candidatos) == 1:
        return candidatos[0]
    if len(candidatos) > 1 and ficha.get("idioma"):
        idioma = str(ficha["idioma"]).lower()[:2]
        por_idioma = [grupo for grupo in candidatos if str(grupo.get("idioma") or "").lower()[:2] == idioma]
        if len(por_idioma) == 1:
            return por_idioma[0]
    return None


def vincular_horarios_oficiales(fichas: list[dict], cache: Path | None) -> tuple[list[dict], list[str]]:
    """Añade horarios vigentes o referencias UAL auditables a las fichas."""
    detalles = _cargar_detalles(fichas, cache)
    incidencias: list[str] = []
    for ficha in fichas:
        if not requiere_horario_fijo({
            "NOM.ASIGNATURA": ficha["nombre_asignatura"], "CARACTER": ficha.get("caracter"),
            "NOM.ACTIVIDAD": ficha.get("nombre_actividad"),
        }):
            ficha.update({
                "requiere_horario": False, "dias": None, "horario": None,
                "horario_detallado": [], "horario_confirmado": False,
                "origen_horario": "NO_APLICA", "fuente_horario": None,
            })
            continue

        if _aplicar_actividad_dual_sin_franja(ficha):
            continue

        clave = (_plan_ual(ficha.get("codigo_plan")), str(ficha["codigo"]))
        grupo = _grupo_oficial(ficha, detalles.get(clave, {}))
        if grupo is None:
            if _aplicar_horario_referencia(ficha):
                continue
            incidencias.append(f"{ficha['codigo']} · {ficha['tipo']} · {ficha['codigo_grupo']}: grupo no localizado en la UAL")
            continue
        sesiones = _sesiones_ual(grupo)
        if not sesiones:
            if _aplicar_horario_referencia(ficha):
                continue
            incidencias.append(f"{ficha['codigo']} · {ficha['tipo']} · {ficha['codigo_grupo']}: la UAL no publica sesiones")
            continue
        dias, horario = _resumen_semanal(sesiones)
        ficha.update({
            "requiere_horario": True, "dias": dias, "horario": horario,
            "horario_detallado": sesiones, "horario_confirmado": True,
            "origen_horario": "UAL_OFICIAL",
            "fuente_horario": API_DETALLE.format(plan=clave[0], asignatura=clave[1]),
        })
    return fichas, incidencias


def _perfil_anonimo(nombre_origen: str, area: str) -> tuple[str, str, str]:
    coincidencia = re.fullmatch(r"Profesor_(\d+)", nombre_origen.strip())
    if not coincidencia:
        raise ErrorImportacionDocente(f"Alias anónimo no reconocido: {nombre_origen!r}.")
    numero = coincidencia.group(1)
    return f"Profesor {numero}", f"Anónimo {area}", f"{area.lower()}.profesor{numero}@prueba.local"


def construir_perfiles_anonimos(filas: list[dict[str, str]]) -> tuple[list[dict], dict[str, str], dict[str, int]]:
    """Genera perfiles test con las proporciones solicitadas y cargas del CSV."""
    perfiles = construir_perfiles_sinteticos(filas)
    perfiles.sort(key=lambda perfil: perfil["identificador_origen"])
    total = len(perfiles)
    cantidad_catedraticos = round(total * 0.30)
    cantidad_psi = round(total * 0.10)
    if cantidad_catedraticos + cantidad_psi + 2 > total:
        raise ErrorImportacionDocente("No hay suficientes perfiles para aplicar las categorías de prueba.")

    for indice, perfil in enumerate(perfiles):
        if indice < cantidad_catedraticos:
            categoria, anio = "Catedrático", 1990 + indice % 8
        elif indice < cantidad_catedraticos + cantidad_psi:
            categoria, anio = "PSI", 2022 + indice % 3
        else:
            categoria, anio = "Titular", 2002 + indice % 13
        nombre, apellidos, email = _perfil_anonimo(
            str(perfil.get("nombre") or perfil["identificador_origen"]), perfil["area_codigo"]
        )
        perfil.update({
            "nombre": nombre, "apellidos": apellidos, "email": email,
            "categoria": categoria, "fecha_ingreso": date(anio, 9, 1), "es_psi": False,
        })

    titulares = [perfil for perfil in perfiles if perfil["categoria"] == "Titular"]
    becario = min((perfil for perfil in titulares if perfil["carga_docente"] <= 60), key=lambda p: p["carga_docente"], default=None)
    postdoc = min(
        (perfil for perfil in titulares if perfil is not becario and perfil["carga_docente"] <= 100),
        key=lambda p: p["carga_docente"], default=None,
    )
    if becario is None or postdoc is None:
        raise ErrorImportacionDocente("No hay perfiles titulares con carga apta para becario y postdoctoral.")
    becario.update({"categoria": "Becario", "fecha_ingreso": date(2025, 9, 1)})
    postdoc.update({"categoria": "Postdoctoral", "fecha_ingreso": date(2021, 9, 1)})

    roles: dict[str, str] = {}
    por_area: dict[str, list[dict]] = defaultdict(list)
    for perfil in perfiles:
        por_area[perfil["area_codigo"]].append(perfil)
    candidatos = sorted(perfiles, key=lambda p: (p["categoria"] != "Catedrático", p["fecha_ingreso"]))
    responsable_departamento = candidatos[0]
    roles[responsable_departamento["identificador_origen"]] = "responsable_departamento"
    usados = {responsable_departamento["identificador_origen"]}
    for area in sorted(por_area):
        responsable = next((p for p in candidatos if p["area_codigo"] == area and p["identificador_origen"] not in usados), None)
        if responsable is None:
            raise ErrorImportacionDocente(f"No se puede designar responsable anónimo para {area}.")
        roles[responsable["identificador_origen"]] = "responsable_area"
        usados.add(responsable["identificador_origen"])

    pesos = {"Catedrático": 1, "Titular": 2, "PSI": 3, "Postdoctoral": 4, "Becario": 5}
    return perfiles, roles, pesos


def _resetear_catalogo(cur, codigos_area: set[str]) -> None:
    """Elimina solo el catálogo destino y sus borradores/adjudicaciones."""
    cur.execute("SELECT id FROM areas WHERE codigo = ANY(%s)", (sorted(codigos_area),))
    area_ids = [fila[0] for fila in cur.fetchall()]
    if not area_ids:
        return

    cur.execute("""
        SELECT DISTINCT a.id
        FROM actividades a
        JOIN actividad_areas aa ON aa.actividad_id=a.id
        WHERE aa.area_id = ANY(%s) AND NOT a.area_id = ANY(%s)
    """, (area_ids, area_ids))
    if cur.fetchall():
        raise ErrorImportacionDocente(
            "Hay actividades compartidas cuya cuota principal pertenece a otra área; no se reinician para no borrar datos ajenos."
        )

    cur.execute("""
        SELECT p.id, p.usuario_id
        FROM profesores p
        WHERE EXISTS (SELECT 1 FROM profesor_areas pa WHERE pa.profesor_id=p.id AND pa.area_id = ANY(%s))
          AND NOT EXISTS (SELECT 1 FROM profesor_areas pa WHERE pa.profesor_id=p.id AND NOT pa.area_id = ANY(%s))
    """, (area_ids, area_ids))
    perfiles = cur.fetchall()
    profesor_ids = [fila[0] for fila in perfiles]
    usuario_ids = [fila[1] for fila in perfiles]

    if profesor_ids:
        cur.execute("""
            SELECT COUNT(*) FROM reparto_docente rd
            JOIN actividades a ON a.id=rd.actividad_id
            WHERE rd.profesor_id = ANY(%s) AND NOT a.area_id = ANY(%s)
        """, (profesor_ids, area_ids))
        if cur.fetchone()[0]:
            raise ErrorImportacionDocente(
                "Un perfil de las áreas destino tiene adjudicaciones fuera de ellas; se cancela el reseteo para protegerlas."
            )
        cur.execute("""
            SELECT COUNT(*) FROM reparto_docente_borrador b
            JOIN actividades a ON a.id=b.actividad_id
            WHERE b.profesor_id = ANY(%s) AND NOT a.area_id = ANY(%s)
        """, (profesor_ids, area_ids))
        if cur.fetchone()[0]:
            raise ErrorImportacionDocente(
                "Un perfil de las áreas destino tiene un borrador fuera de ellas; se cancela el reseteo para protegerlo."
            )

    cur.execute("DELETE FROM ordenacion_revisiones WHERE area_id = ANY(%s)", (area_ids,))
    if profesor_ids:
        cur.execute("DELETE FROM reparto_docente_borrador WHERE actividad_id IN (SELECT id FROM actividades WHERE area_id = ANY(%s)) OR profesor_id = ANY(%s)", (area_ids, profesor_ids))
    else:
        cur.execute("DELETE FROM reparto_docente_borrador WHERE actividad_id IN (SELECT id FROM actividades WHERE area_id = ANY(%s))", (area_ids,))
    cur.execute("DELETE FROM reparto_docente WHERE actividad_id IN (SELECT id FROM actividades WHERE area_id = ANY(%s))", (area_ids,))
    cur.execute("DELETE FROM actividades WHERE area_id = ANY(%s)", (area_ids,))
    cur.execute("DELETE FROM ordenacion_eventos WHERE area_id = ANY(%s)", (area_ids,))
    cur.execute("UPDATE ordenacion_areas_control SET version=0, estado='ABIERTA', cerrado_por_usuario_id=NULL, cerrado_en=NULL WHERE area_id = ANY(%s)", (area_ids,))
    if usuario_ids:
        cur.execute("UPDATE areas SET responsable_area_id=NULL WHERE responsable_area_id = ANY(%s)", (usuario_ids,))
        cur.execute("UPDATE departamentos SET responsable_departamento_id=NULL WHERE responsable_departamento_id = ANY(%s)", (usuario_ids,))
    if profesor_ids:
        cur.execute("DELETE FROM profesores WHERE id = ANY(%s)", (profesor_ids,))
    if usuario_ids:
        cur.execute("DELETE FROM usuarios u WHERE u.id = ANY(%s) AND NOT EXISTS (SELECT 1 FROM profesores p WHERE p.usuario_id=u.id)", (usuario_ids,))


def _actualizar_horarios(cur, fichas: Iterable[dict]) -> None:
    for ficha in fichas:
        cur.execute("""
            UPDATE actividades
            SET dias=%s, horario=%s, requiere_horario=%s, horario_confirmado=%s,
                origen_horario=%s, horario_detallado=%s::jsonb, fuente_horario=%s
            WHERE codigo=%s AND tipo=%s AND codigo_grupo=%s
              AND curso_academico IS NOT DISTINCT FROM %s
              AND area_id=(SELECT id FROM areas WHERE codigo=%s)
        """, (
            ficha["dias"], ficha["horario"], ficha["requiere_horario"], ficha["horario_confirmado"],
            ficha["origen_horario"], json.dumps(ficha["horario_detallado"]), ficha["fuente_horario"],
            ficha["codigo"], ficha["tipo"], ficha["codigo_grupo"], ficha["curso_academico"], ficha["area_codigo_externo"],
        ))
        if cur.rowcount != 1:
            raise ErrorImportacionDocente(f"No se pudo actualizar el horario de {ficha['codigo']} / {ficha['codigo_grupo']}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga catálogo anonimizado y horarios oficiales UAL.")
    parser.add_argument("--aplicar", action="store_true", help="Escribe la reconstrucción en la base de datos.")
    parser.add_argument("--cache", type=Path, default=None, help="Archivo JSON reutilizable de respuestas públicas UAL.")
    args = parser.parse_args()

    filas = [fila for fila in leer_exportacion_bytes(sys.stdin.buffer.read()) if fila.get("COD.AMBITO/AREA") in CODIGOS_AREA]
    if not filas:
        raise ErrorImportacionDocente("El CSV no contiene ninguna de las cuatro áreas de Informática esperadas.")
    if {fila["COD.AMBITO/AREA"] for fila in filas} != CODIGOS_AREA:
        raise ErrorImportacionDocente("El CSV no contiene las cuatro áreas completas de Informática.")
    fichas, incidencias = vincular_horarios_oficiales(construir_fichas_actividad(filas), args.cache)
    perfiles, roles, pesos = construir_perfiles_anonimos(filas)
    resumen = {
        "modo": "APLICAR" if args.aplicar else "VALIDACION",
        "areas": sorted(CODIGOS_AREA), "profesores": len(perfiles), "actividades": len(fichas),
        "sesiones_oficiales": sum(len(ficha.get("horario_detallado") or []) for ficha in fichas),
        "sin_horario_fijo": sum(not ficha["requiere_horario"] for ficha in fichas),
        "incidencias": incidencias,
        "categorias": dict(sorted(Counter(perfil["categoria"] for perfil in perfiles).items())),
    }
    if incidencias:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        raise ErrorImportacionDocente("No se aplica ningún cambio: faltan horarios o grupos oficiales por resolver.")
    if not args.aplicar:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        return

    import os
    password = os.environ.get("UAL_IMPORT_PASSWORD", "")
    if len(password) < 12:
        raise ErrorImportacionDocente("Define UAL_IMPORT_PASSWORD con una contraseña temporal de al menos 12 caracteres.")
    with conexion_ctx() as conn:
        cur = conn.cursor()
        _resetear_catalogo(cur, CODIGOS_AREA)
        resultado = importar_escenario_sintetico(
            filas, password, perfiles_personalizados=perfiles, roles_personalizados=roles,
            pesos_personalizados=pesos, contexto_huella="UAL_OFICIAL_2026_27", conexion=conn,
        )
        _actualizar_horarios(cur, fichas)
    resumen.update(resultado)
    print(json.dumps(resumen, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    try:
        main()
    except ErrorImportacionDocente as exc:
        print(f"Error de carga: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
