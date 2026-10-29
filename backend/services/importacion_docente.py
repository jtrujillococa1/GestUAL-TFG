"""Lectura, normalización e importación explícita de exportaciones docentes.

La importación de prueba crea catálogo y perfiles sintéticos, pero nunca toma
del CSV la relación publicada profesor--grupo: esa relación se construye en la
ordenación de la aplicación.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import defaultdict
from contextlib import nullcontext
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List

from core.activity_values import normalizar_tipo_actividad, normalizar_turno
from core.auth import get_password_hash
from db.connection import conexion_ctx


COLUMNAS_REQUERIDAS = {
    "COD.DEPARTAMENTO", "NOM.DEPARTAMENTO", "COD.AMBITO/AREA", "DES.AMBITO/AREA",
    "COD.ASIGNATURA", "NOM.ASIGNATURA", "COD.ACTIVIDAD", "ID.ACTIVIDAD",
    "NOM.ACTIVIDAD", "COD.GRUPO", "ID.GRUPO", "NOM.GRUPO", "DURACION", "TURNO",
    "HORAS ASIGNATURA", "HORAS ACTIVIDAD", "HORAS AMBITO/AREA",
}

COLUMNAS_REPARTO_OPCIONALES = {
    "NIF.PROFESOR", "NOM.PROFESOR", "PROF.ACTIVO", "HORAS PROFESOR",
    "PROF.PRINCIPAL", "COORDINADOR", "COD.PLAZA", "ID.PLAZA",
}


class ErrorImportacionDocente(ValueError):
    """El fichero no tiene una estructura que pueda importarse con seguridad."""


def _texto(valor: object) -> str:
    return str(valor or "").strip()


def _horas(valor: object, columna: str) -> float:
    try:
        return float(_texto(valor).replace(",", "."))
    except ValueError as exc:
        raise ErrorImportacionDocente(f"Valor de horas inválido en «{columna}»: {valor!r}") from exc


def _texto_normalizado(valor: object) -> str:
    """Normaliza texto institucional para clasificar actividades especiales."""
    return "".join(
        caracter for caracter in unicodedata.normalize("NFD", _texto(valor).lower())
        if unicodedata.category(caracter) != "Mn"
    )


def requiere_horario_fijo(fila: Dict[str, str]) -> bool:
    """Indica si la actividad ocupa una franja semanal presencial.

    Las prácticas externas se supervisan y tienen carga docente, pero sus
    estancias dependen de las entidades colaboradoras y no reservan un aula ni
    una franja semanal fija. No se les debe inventar un horario sintético.
    """
    textos = (
        _texto_normalizado(fila.get("NOM.ASIGNATURA")),
        _texto_normalizado(fila.get("CARACTER")),
        _texto_normalizado(fila.get("NOM.ACTIVIDAD")),
    )
    return not any("practicas externas" in texto for texto in textos)


def generar_horario_sintetico(codigo: str, tipo: str, codigo_grupo: str, turno: str) -> Dict[str, str]:
    """Genera una franja semanal estable, lógica y marcada como no oficial.

    No usa profesores ni repartos: la actividad conserva el mismo horario con
    independencia de quién termine impartiéndola durante la ordenación.
    """
    teoria = tipo == "GD"
    franjas = {
        "Mañana": (
            [("Lunes, Miércoles", "09:00-10:30"), ("Martes, Jueves", "10:45-12:15"), ("Viernes", "12:30-14:00")]
            if teoria else
            [("Lunes", "09:00-11:00"), ("Martes", "11:15-13:15"), ("Miércoles", "13:30-15:30"), ("Jueves", "09:00-11:00"), ("Viernes", "11:15-13:15")]
        ),
        "Tarde": (
            [("Lunes, Miércoles", "15:30-17:00"), ("Martes, Jueves", "17:15-18:45"), ("Viernes", "19:00-20:30")]
            if teoria else
            [("Lunes", "15:30-17:30"), ("Martes", "17:45-19:45"), ("Miércoles", "15:30-17:30"), ("Jueves", "17:45-19:45"), ("Viernes", "15:30-17:30")]
        ),
        "Tarde semipresencial y virtual": [("Martes, Jueves", "17:00-19:00")],
    }
    turno_efectivo = turno
    if turno == "Mañana/Tarde":
        turno_efectivo = "Mañana" if int(hashlib.sha256(codigo.encode()).hexdigest(), 16) % 2 == 0 else "Tarde"
    opciones = franjas.get(turno_efectivo, franjas["Tarde"])
    clave = f"{codigo}|{tipo}|{codigo_grupo}|{turno}".encode()
    indice = int(hashlib.sha256(clave).hexdigest(), 16) % len(opciones)
    dias, horario = opciones[indice]
    return {"dias": dias, "horario": horario, "origen_horario": "SINTETICO"}


def _leer_exportacion(fichero: io.TextIOBase) -> List[Dict[str, str]]:
    reader = csv.DictReader(fichero, delimiter=";")
    if not reader.fieldnames:
        raise ErrorImportacionDocente("El fichero no contiene cabecera.")
    faltan = COLUMNAS_REQUERIDAS - set(reader.fieldnames)
    if faltan:
        raise ErrorImportacionDocente(
            "Faltan columnas obligatorias: " + ", ".join(sorted(faltan))
        )
    return [{clave: _texto(valor) for clave, valor in fila.items()} for fila in reader]


def leer_exportacion(ruta: str | Path) -> List[Dict[str, str]]:
    """Lee el CSV institucional separado por punto y coma, conservando UTF-8."""
    with Path(ruta).open(encoding="utf-8-sig", errors="replace", newline="") as fichero:
        return _leer_exportacion(fichero)


def leer_exportacion_bytes(contenido: bytes) -> List[Dict[str, str]]:
    """Versión para la previsualización web; no guarda el fichero recibido."""
    with io.TextIOWrapper(io.BytesIO(contenido), encoding="utf-8-sig", errors="replace", newline="") as fichero:
        return _leer_exportacion(fichero)


def construir_fichas_actividad(filas: Iterable[Dict[str, str]]) -> List[Dict]:
    """Agrupa las filas por actividad y área, sin mezclar cuotas compartidas.

    La misma actividad puede aparecer una vez por cada profesor y también en
    varias áreas. La ficha devuelta es la unidad que se debe crear en
    ``actividades``; ``area_codigo_externo`` se resuelve contra la tabla áreas
    durante una futura importación transaccional.
    """
    agrupadas: dict[tuple[str, str, str, str], list[Dict[str, str]]] = defaultdict(list)
    for fila in filas:
        clave = (
            fila["COD.ASIGNATURA"], fila["ID.ACTIVIDAD"], fila["ID.GRUPO"],
            fila["COD.AMBITO/AREA"],
        )
        if not all(clave):
            raise ErrorImportacionDocente(f"Fila sin identidad completa de actividad: {clave!r}")
        agrupadas[clave].append(fila)

    fichas: List[Dict] = []
    for clave, repetidas in agrupadas.items():
        fila = repetidas[0]
        for columna in ("HORAS ASIGNATURA", "HORAS ACTIVIDAD", "HORAS AMBITO/AREA"):
            valores = {_texto(r[columna]) for r in repetidas}
            if len(valores) != 1:
                raise ErrorImportacionDocente(
                    f"La actividad {clave!r} tiene valores incompatibles en «{columna}»."
                )
        requiere_horario = requiere_horario_fijo(fila)
        horario_sintetico = (
            generar_horario_sintetico(
                fila["COD.ASIGNATURA"], normalizar_tipo_actividad(fila["ID.ACTIVIDAD"]),
                fila["ID.GRUPO"], normalizar_turno(fila["TURNO"]),
            )
            if requiere_horario
            else {"dias": None, "horario": None, "origen_horario": "NO_APLICA"}
        )
        fichas.append({
            "codigo": fila["COD.ASIGNATURA"],
            "curso_academico": fila.get("AÑO ACADEMICO") or None,
            "nombre_asignatura": fila["NOM.ASIGNATURA"],
            "tipo": normalizar_tipo_actividad(fila["ID.ACTIVIDAD"]),
            "actividad_oficial_id": fila["COD.ACTIVIDAD"],
            "nombre_actividad": fila["NOM.ACTIVIDAD"],
            "codigo_grupo": fila["ID.GRUPO"],
            "codigo_grupo_oficial": fila["COD.GRUPO"],
            "grupo": fila["NOM.GRUPO"],
            "idioma": fila.get("IDIOMA.GRUPO") or None,
            "duracion": fila["DURACION"],
            "turno": normalizar_turno(fila["TURNO"]),
            "dias": horario_sintetico["dias"],
            "horario": horario_sintetico["horario"],
            "requiere_horario": requiere_horario,
            "horario_confirmado": False,
            "origen_horario": horario_sintetico["origen_horario"],
            "horas_asignatura": _horas(fila["HORAS ASIGNATURA"], "HORAS ASIGNATURA"),
            "horas_actividad": _horas(fila["HORAS ACTIVIDAD"], "HORAS ACTIVIDAD"),
            "horas_area": _horas(fila["HORAS AMBITO/AREA"], "HORAS AMBITO/AREA"),
            "area_codigo_externo": fila["COD.AMBITO/AREA"],
            "departamento_codigo_externo": fila["COD.DEPARTAMENTO"],
            "tipo_estudio": fila.get("TIPO.ESTUDIO") or None,
            "codigo_plan": fila.get("COD.PLAN") or None,
            "nombre_plan": fila.get("NOM.PLAN") or None,
            "codigo_centro": fila.get("COD.CENTRO") or None,
            "nombre_centro": fila.get("NOM.CENTRO") or None,
            "ciclo": fila.get("CICLO") or None,
            "curso": fila.get("CURSO") or None,
            "caracter": fila.get("CARACTER") or None,
        })
    return sorted(fichas, key=lambda ficha: (
        ficha["area_codigo_externo"], ficha["codigo"], ficha["tipo"], ficha["codigo_grupo"]
    ))


def construir_profesores_origen(filas: Iterable[Dict[str, str]]) -> List[Dict]:
    """Obtiene profesores de origen sin inventar categorías, antigüedad o usuarios."""
    agrupados: dict[str, list[Dict[str, str]]] = defaultdict(list)
    for fila in filas:
        identificador = fila.get("NIF.PROFESOR", "")
        if identificador:
            agrupados[identificador].append(fila)

    profesores: List[Dict] = []
    for identificador, apariciones in agrupados.items():
        nombres = {fila.get("NOM.PROFESOR", "") for fila in apariciones}
        activos = {fila.get("PROF.ACTIVO", "") for fila in apariciones}
        if len(nombres) != 1 or len(activos) != 1:
            raise ErrorImportacionDocente(
                f"El profesor de origen {identificador!r} tiene datos incompatibles."
            )
        profesores.append({
            "identificador_origen": identificador,
            "nombre_origen": nombres.pop(),
            "activo_origen": activos.pop().upper() == "S",
            "areas_origen": sorted({fila["COD.AMBITO/AREA"] for fila in apariciones}),
        })
    return sorted(profesores, key=lambda profesor: profesor["identificador_origen"])


def construir_perfiles_sinteticos(filas: Iterable[Dict[str, str]]) -> List[Dict]:
    """Crea perfiles equilibrados, sin conservar ninguna relación con grupos.

    La carga se usa únicamente como capacidad global para que cada área sea
    viable. Los grupos de la exportación nunca se incorporan a estos perfiles.
    """
    filas = list(filas)
    por_profesor: dict[str, list[Dict[str, str]]] = defaultdict(list)
    for fila in filas:
        if fila.get("NIF.PROFESOR"):
            por_profesor[fila["NIF.PROFESOR"]].append(fila)

    categorias = ("Catedrático", "Titular", "Contratado", "Ayudante", "Asociado")
    perfiles: List[Dict] = []
    for indice, identificador in enumerate(sorted(por_profesor)):
        apariciones = por_profesor[identificador]
        areas = {fila["COD.AMBITO/AREA"] for fila in apariciones}
        if len(areas) != 1:
            raise ErrorImportacionDocente(
                f"El profesor {identificador!r} pertenece a varias áreas; requiere revisión manual."
            )
        nombre_origen = apariciones[0].get("NOM.PROFESOR") or identificador
        if "," in nombre_origen:
            apellidos, nombre = (trozo.strip() for trozo in nombre_origen.split(",", 1))
        else:
            nombre, apellidos = nombre_origen, "Importado"
        categoria = categorias[indice % len(categorias)]
        # Mayor prioridad de categoría implica una fecha de entrada más antigua.
        antiguedad_base = {"Catedrático": 1988, "Titular": 1996, "Contratado": 2005, "Ayudante": 2013, "Asociado": 2018}
        anio = antiguedad_base[categoria] + (indice // len(categorias)) % 6
        alias = re.sub(r"[^a-z0-9]+", "-", identificador.lower()).strip("-")
        perfiles.append({
            "identificador_origen": identificador,
            "nombre": nombre[:100],
            "apellidos": apellidos[:200],
            "email": f"{alias}@ordenacion.local",
            "area_codigo": areas.pop(),
            "categoria": categoria,
            "fecha_ingreso": date(anio, 9, 1),
            "carga_docente": round(sum(_horas(fila["HORAS PROFESOR"], "HORAS PROFESOR") for fila in apariciones), 1),
            "activo_origen": apariciones[0].get("PROF.ACTIVO", "").upper() == "S",
        })
    # La exportación puede incluir una diferencia de una décima entre la suma
    # de sus líneas de reparto y la cuota de actividad del área. Como estas
    # cargas son artificiales y sirven para ensayar el reparto, se aplica esa
    # diferencia de redondeo al primer perfil de cada área. Así el solver puede
    # cubrir exactamente la cuota institucional sin inventar un grupo asignado.
    cuotas_por_area: dict[str, float] = defaultdict(float)
    for ficha in construir_fichas_actividad(filas):
        cuotas_por_area[ficha["area_codigo_externo"]] += ficha["horas_area"]
    for area_codigo, cuota in cuotas_por_area.items():
        perfiles_area = [perfil for perfil in perfiles if perfil["area_codigo"] == area_codigo]
        carga_actual = round(sum(perfil["carga_docente"] for perfil in perfiles_area), 1)
        ajuste = round(cuota - carga_actual, 1)
        if not ajuste:
            continue
        # Una previsualización sin columnas de profesor sigue siendo válida:
        # simplemente no puede crear perfiles. Los desfases grandes, en cambio,
        # son datos inconsistentes y no deben maquillarse como capacidad.
        if not perfiles_area:
            continue
        if abs(ajuste) > 0.1 or perfiles_area[0]["carga_docente"] + ajuste <= 0:
            raise ErrorImportacionDocente(
                f"La carga de perfiles y la cuota del área {area_codigo!r} difieren en {ajuste:.1f} h."
            )
        perfiles_area[0]["carga_docente"] = round(perfiles_area[0]["carga_docente"] + ajuste, 1)
    return perfiles


def _huella_importacion(filas: List[Dict[str, str]]) -> str:
    contenido = json.dumps(filas, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(contenido.encode()).hexdigest()


def _validar_perfiles_personalizados(
    perfiles: Iterable[Dict], fichas: List[Dict], filas: List[Dict[str, str]],
) -> List[Dict]:
    """Comprueba un perfilado manual sin alterar la identidad del CSV.

    La importación automática cubre el caso de demostración. Para una carga
    piloto es útil ajustar categorías, antigüedad o responsables sin convertir
    la relación publicada profesor--grupo en adjudicaciones iniciales.
    """
    perfiles = [dict(perfil) for perfil in perfiles]
    origen = {profesor["identificador_origen"] for profesor in construir_profesores_origen(filas)}
    recibidos = {perfil.get("identificador_origen") for perfil in perfiles}
    if recibidos != origen or len(perfiles) != len(origen):
        raise ErrorImportacionDocente(
            "Los perfiles personalizados deben contener una única entrada para cada profesor de origen."
        )

    cuotas_por_area: dict[str, float] = defaultdict(float)
    for ficha in fichas:
        cuotas_por_area[ficha["area_codigo_externo"]] += float(ficha["horas_area"])

    for perfil in perfiles:
        obligatorios = {
            "identificador_origen", "nombre", "apellidos", "email", "area_codigo",
            "categoria", "fecha_ingreso", "carga_docente", "activo_origen",
        }
        if obligatorios - set(perfil):
            raise ErrorImportacionDocente("Un perfil personalizado no contiene todos los campos necesarios.")
        if perfil["area_codigo"] not in cuotas_por_area:
            raise ErrorImportacionDocente("Un perfil personalizado apunta a un área que no figura en el CSV.")
        try:
            carga = float(perfil["carga_docente"])
        except (TypeError, ValueError) as exc:
            raise ErrorImportacionDocente("La carga de un perfil personalizado no es válida.") from exc
        if carga <= 0:
            raise ErrorImportacionDocente("La carga de un perfil personalizado debe ser positiva.")
        perfil["carga_docente"] = round(carga, 1)
        perfil["es_psi"] = bool(perfil.get("es_psi", False))

    for area_codigo, cuota in cuotas_por_area.items():
        capacidad = round(sum(
            perfil["carga_docente"] for perfil in perfiles if perfil["area_codigo"] == area_codigo
        ), 1)
        if abs(capacidad - round(cuota, 1)) > 0.01:
            raise ErrorImportacionDocente(
                f"La capacidad de perfiles del área {area_codigo!r} ({capacidad:.1f} h) "
                f"no coincide con su cuota ({cuota:.1f} h)."
            )
    return perfiles


def importar_escenario_sintetico(
    filas: Iterable[Dict[str, str]], password_temporal: str,
    perfiles_personalizados: Iterable[Dict] | None = None,
    roles_personalizados: Dict[str, str] | None = None,
    pesos_personalizados: Dict[str, int] | None = None,
    contexto_huella: str = "",
    conexion=None,
) -> Dict[str, object]:
    """Crea un escenario de prueba completo y atómico, sin repartir grupos.

    Requiere una contraseña temporal elegida por el administrador. Si algo no
    cuadra, la transacción completa se revierte y no queda ninguna carga parcial.
    """
    filas = list(filas)
    if len(password_temporal) < 12:
        raise ErrorImportacionDocente("La contraseña temporal debe tener al menos 12 caracteres.")
    fichas = construir_fichas_actividad(filas)
    perfiles = (
        _validar_perfiles_personalizados(perfiles_personalizados, fichas, filas)
        if perfiles_personalizados is not None
        else construir_perfiles_sinteticos(filas)
    )
    cursos = {ficha["curso_academico"] for ficha in fichas}
    if len(cursos) != 1 or not next(iter(cursos)):
        raise ErrorImportacionDocente("El CSV debe contener un único curso académico válido.")
    # La misma exportación puede alimentar un catálogo sintético previo y una
    # reconstrucción con horarios oficiales. Ambos lotes son auditables y no
    # deben bloquearse mutuamente por compartir CSV.
    huella_base = _huella_importacion(filas)
    huella = hashlib.sha256(f"{huella_base}|{contexto_huella}".encode()).hexdigest()

    departamentos_csv = {fila["COD.DEPARTAMENTO"]: fila["NOM.DEPARTAMENTO"] for fila in filas}
    areas_csv = {fila["COD.AMBITO/AREA"]: (fila["DES.AMBITO/AREA"], fila["COD.DEPARTAMENTO"]) for fila in filas}
    pesos = {"Catedrático": 1, "Titular": 2, "Contratado": 3, "Ayudante": 4, "Asociado": 5}
    if pesos_personalizados is not None:
        if any(not isinstance(peso, int) or peso < 1 for peso in pesos_personalizados.values()):
            raise ErrorImportacionDocente("Los pesos personalizados deben ser enteros positivos.")
        pesos.update(pesos_personalizados)
    for perfil in perfiles:
        pesos.setdefault(perfil["categoria"], max(pesos.values()) + 1)
    password_hash = get_password_hash(password_temporal)
    roles_personalizados = roles_personalizados or {}
    roles_validos = {"profesor", "psi", "responsable_area", "responsable_departamento"}
    if any(rol not in roles_validos for rol in roles_personalizados.values()):
        raise ErrorImportacionDocente("Uno de los roles personalizados no es válido.")

    # Las cargas oficiales pueden componer el reseteo, la creación del
    # catálogo y la vinculación de horarios en una sola transacción externa.
    # El camino habitual conserva la transacción propia de siempre.
    with (nullcontext(conexion) if conexion is not None else conexion_ctx()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM importaciones_catalogo WHERE huella=%s", (huella,))
        if cur.fetchone():
            raise ErrorImportacionDocente("Este CSV ya se importó como escenario de prueba.")

        for categoria, peso in pesos.items():
            cur.execute(
                "INSERT INTO categoria_pesos (categoria, peso) VALUES (%s, %s) ON CONFLICT (categoria) DO NOTHING",
                (categoria, peso),
            )

        departamentos: Dict[str, int] = {}
        for codigo, nombre in departamentos_csv.items():
            cur.execute("SELECT id, nombre FROM departamentos WHERE codigo=%s", (codigo,))
            existente = cur.fetchone()
            if existente:
                if existente[1] != nombre:
                    raise ErrorImportacionDocente(f"Conflicto de nombre en departamento {codigo}.")
                departamentos[codigo] = existente[0]
            else:
                cur.execute("INSERT INTO departamentos (codigo, nombre) VALUES (%s, %s) RETURNING id", (codigo, nombre))
                departamentos[codigo] = cur.fetchone()[0]

        areas: Dict[str, int] = {}
        for codigo, (nombre, codigo_departamento) in areas_csv.items():
            departamento_id = departamentos[codigo_departamento]
            cur.execute("SELECT id, nombre, departamento_id FROM areas WHERE codigo=%s", (codigo,))
            existente = cur.fetchone()
            if existente:
                if existente[1] != nombre or existente[2] != departamento_id:
                    raise ErrorImportacionDocente(f"Conflicto de catálogo en área {codigo}.")
                areas[codigo] = existente[0]
            else:
                cur.execute(
                    "INSERT INTO areas (codigo, nombre, departamento_id) VALUES (%s, %s, %s) RETURNING id",
                    (codigo, nombre, departamento_id),
                )
                areas[codigo] = cur.fetchone()[0]

        # Se seleccionan docentes de referencia, pero sus cuentas personales
        # siempre se crean como PROFESOR/PSI. Las cuentas institucionales se
        # generan después, una por departamento o área.
        responsable_departamento = None
        responsable_area: Dict[str, dict] = {}
        usados_responsables: set[str] = set()
        cuentas_responsables = []

        for perfil in perfiles:
            cur.execute("SELECT id FROM profesores WHERE identificador_origen=%s", (perfil["identificador_origen"],))
            if cur.fetchone():
                raise ErrorImportacionDocente(f"Ya existe el profesor de origen {perfil['identificador_origen']!r}.")
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (perfil["email"],))
            if cur.fetchone():
                raise ErrorImportacionDocente(f"Ya existe el correo de prueba {perfil['email']!r}.")

            rol = roles_personalizados.get(perfil["identificador_origen"], "profesor")
            if perfiles_personalizados is None and responsable_departamento is None:
                rol = "responsable_departamento"
                usados_responsables.add(perfil["identificador_origen"])
            elif (
                perfiles_personalizados is None
                and perfil["area_codigo"] not in responsable_area
                and perfil["identificador_origen"] not in usados_responsables
            ):
                rol = "responsable_area"
                usados_responsables.add(perfil["identificador_origen"])
            rol_docente = "psi" if (perfil.get("es_psi", False) or rol == "psi") else "profesor"
            cur.execute("""
                INSERT INTO usuarios (nombre, apellidos, email, password_hash, rol, activo)
                VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id
            """, (perfil["nombre"], perfil["apellidos"], perfil["email"], password_hash, rol_docente))
            usuario_id = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO profesores (usuario_id, nombre, apellidos, categoria, fecha_ingreso,
                                        carga_docente, area_id, es_psi, identificador_origen, activo_origen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (usuario_id, perfil["nombre"], perfil["apellidos"], perfil["categoria"], perfil["fecha_ingreso"],
                  perfil["carga_docente"], areas[perfil["area_codigo"]], perfil.get("es_psi", False),
                  perfil["identificador_origen"], perfil["activo_origen"]))
            profesor_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO profesor_areas (profesor_id, area_id, horas_objetivo) VALUES (%s, %s, %s)",
                (profesor_id, areas[perfil["area_codigo"]], perfil["carga_docente"]),
            )
            if rol == "responsable_departamento":
                responsable_departamento = perfil
                usados_responsables.add(perfil["identificador_origen"])
            elif rol == "responsable_area":
                responsable_area[perfil["area_codigo"]] = perfil
                usados_responsables.add(perfil["identificador_origen"])

        if perfiles_personalizados is not None:
            if responsable_departamento is None or set(responsable_area) != set(areas):
                raise ErrorImportacionDocente(
                    "Los perfiles personalizados deben designar un responsable de departamento y uno por cada área."
                )

        def crear_cuenta_responsable(rol_cuenta: str, etiqueta: str, codigo: str, nombre_alcance: str, perfil: dict) -> int:
            slug = re.sub(r"[^a-z0-9]+", "-", codigo.lower()).strip("-") or "gestion"
            email = f"responsable.{etiqueta.lower()}.{slug}@gestual.local"
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            existente = cur.fetchone()
            if existente:
                return existente[0]
            cur.execute(
                """
                INSERT INTO usuarios (nombre, apellidos, email, password_hash, rol, activo)
                VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id
                """,
                ("Responsable", f"{etiqueta.title()} {nombre_alcance}", email, password_hash, rol_cuenta),
            )
            cuentas_responsables.append({
                "nombre": f"Responsable {etiqueta.title()} {nombre_alcance}", "email": email,
                "rol": rol_cuenta, "area_codigo": perfil.get("area_codigo"),
            })
            return cur.fetchone()[0]

        for codigo, area_id in areas.items():
            perfil = responsable_area.get(codigo)
            if perfil:
                usuario_id = crear_cuenta_responsable("responsable_area", "área", codigo, areas_csv[codigo][0], perfil)
                cur.execute("UPDATE areas SET responsable_area_id=%s WHERE id=%s", (usuario_id, area_id))
        for codigo_departamento, departamento_id in departamentos.items():
            if responsable_departamento:
                usuario_id = crear_cuenta_responsable(
                    "responsable_departamento", "departamento", codigo_departamento,
                    departamentos_csv[codigo_departamento], responsable_departamento,
                )
                cur.execute("UPDATE departamentos SET responsable_departamento_id=%s WHERE id=%s", (usuario_id, departamento_id))

        for ficha in fichas:
            area_id = areas[ficha["area_codigo_externo"]]
            cur.execute("""
                SELECT id FROM actividades
                WHERE codigo=%s AND tipo=%s AND codigo_grupo=%s AND area_id=%s
                  AND curso_academico IS NOT DISTINCT FROM %s
            """, (ficha["codigo"], ficha["tipo"], ficha["codigo_grupo"], area_id, ficha["curso_academico"]))
            if cur.fetchone():
                raise ErrorImportacionDocente(
                    f"La actividad {ficha['codigo']} / {ficha['codigo_grupo']} ya existe para ese área y curso."
                )
            cur.execute("""
                INSERT INTO actividades (
                    codigo, tipo, codigo_grupo, grupo, idioma, duracion, turno, dias, horario,
                    requiere_horario, horario_confirmado, origen_horario, horas_asignatura, horas_actividad, horas_area, area_id,
                    nombre_asignatura, tipo_estudio, codigo_plan, nombre_plan, codigo_centro, nombre_centro,
                    ciclo, curso, caracter, actividad_oficial_id, nombre_actividad, codigo_grupo_oficial,
                    curso_academico
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (ficha["codigo"], ficha["tipo"], ficha["codigo_grupo"], ficha["grupo"], ficha["idioma"],
                  ficha["duracion"], ficha["turno"], ficha["dias"], ficha["horario"], ficha["requiere_horario"], False,
                  ficha["origen_horario"], ficha["horas_asignatura"], ficha["horas_actividad"], ficha["horas_area"], area_id,
                  ficha["nombre_asignatura"], ficha["tipo_estudio"], ficha["codigo_plan"], ficha["nombre_plan"],
                  ficha["codigo_centro"], ficha["nombre_centro"], ficha["ciclo"], ficha["curso"], ficha["caracter"],
                  ficha["actividad_oficial_id"], ficha["nombre_actividad"], ficha["codigo_grupo_oficial"], ficha["curso_academico"]))
            actividad_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO actividad_areas (actividad_id, area_id) VALUES (%s, %s)",
                (actividad_id, area_id),
            )

        cur.execute("""
            INSERT INTO importaciones_catalogo (huella, curso_academico, filas_csv, actividades_creadas, profesores_creados)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (huella, next(iter(cursos)), len(filas), len(fichas), len(perfiles)))
        lote_id = cur.fetchone()[0]

    return {
        "ok": True, "lote_id": lote_id, "curso_academico": next(iter(cursos)),
        "departamentos": len(departamentos), "areas": len(areas), "actividades": len(fichas),
        "profesores": len(perfiles), "repartos_confirmados": 0,
        "cuentas_responsables": cuentas_responsables,
        "mensaje": "Escenario creado sin adjudicaciones; la ordenación empieza desde cero.",
    }


def construir_lineas_reparto_referencia(filas: Iterable[Dict[str, str]]) -> List[Dict]:
    """Lee el resultado publicado solo para comparación; no es una asignación.

    Estas líneas nunca se deben insertar en ``reparto_docente`` durante la
    carga inicial. La relación profesor-actividad se construye después de la
    ordenación por medio del borrador y de la confirmación de turnos.
    """
    lineas: List[Dict] = []
    for fila in filas:
        if not fila.get("NIF.PROFESOR"):
            continue
        lineas.append({
            "profesor_identificador_origen": fila["NIF.PROFESOR"],
            "actividad_clave_origen": (
                fila["COD.ASIGNATURA"], fila["ID.ACTIVIDAD"], fila["ID.GRUPO"],
                fila["COD.AMBITO/AREA"],
            ),
            "horas_asignadas": _horas(fila.get("HORAS PROFESOR"), "HORAS PROFESOR"),
            "codigo_plaza_origen": fila.get("COD.PLAZA") or None,
            "id_plaza_origen": fila.get("ID.PLAZA") or None,
            "es_profesor_principal": fila.get("PROF.PRINCIPAL", "").upper() == "S",
            "coordinador_origen": fila.get("COORDINADOR") or None,
            "origen_reparto": "CSV_PUBLICADO",
        })
    return lineas


def resumen_importacion(filas: Iterable[Dict[str, str]]) -> Dict[str, object]:
    """Resume el contenido y deja explícitas las decisiones pendientes antes de importar."""
    filas = list(filas)
    fichas = construir_fichas_actividad(filas)
    profesores = construir_profesores_origen(filas)
    lineas = construir_lineas_reparto_referencia(filas)
    horas_por_profesor: dict[str, set[str]] = defaultdict(set)
    for fila in filas:
        if fila.get("NIF.PROFESOR"):
            horas_por_profesor[fila["NIF.PROFESOR"]].add(fila.get("HORAS PROFESOR", ""))
    profesores_con_horas_variables = sum(
        len(horas) > 1 for horas in horas_por_profesor.values()
    )
    return {
        "filas_csv": len(filas),
        "departamentos": sorted({fila["COD.DEPARTAMENTO"] for fila in filas}),
        "cursos_academicos": sorted({fila.get("AÑO ACADEMICO", "") for fila in filas if fila.get("AÑO ACADEMICO")}),
        "areas": sorted({fila["COD.AMBITO/AREA"] for fila in filas}),
        "actividades_por_area": len(fichas),
        "profesores_origen": len(profesores),
        "lineas_resultado_referencia": len(lineas),
        "horarios_sinteticos": sum(ficha["requiere_horario"] for ficha in fichas),
        "actividades_sin_horario_fijo": sum(not ficha["requiere_horario"] for ficha in fichas),
        "horarios_pendientes_de_confirmar": sum(ficha["requiere_horario"] for ficha in fichas),
        "profesores_con_horas_de_reparto_variables": profesores_con_horas_variables,
        "requiere_revision_humana": [
            "Vincular cada profesor de origen con una persona/categoría/antigüedad reales.",
            "Cargar la carga docente objetivo de cada profesor desde su fuente oficial; «HORAS PROFESOR» es una línea de reparto.",
            "Resolver códigos de departamento y área contra los catálogos definitivos.",
            "Confirmar días y franjas horarias antes de activar comprobación de solapes.",
            "Decidir si el reparto publicado se importa como histórico o como ordenación confirmada.",
        ],
    }


def planificar_importacion(
    filas: Iterable[Dict[str, str]],
    departamentos_actuales: Iterable[Dict],
    areas_actuales: Iterable[Dict],
    actividades_actuales: Iterable[Dict],
) -> Dict[str, object]:
    """Compara una exportación con el catálogo actual sin escribir en la BD."""
    filas = list(filas)
    fichas = construir_fichas_actividad(filas)
    departamentos_csv = {
        fila["COD.DEPARTAMENTO"]: fila["NOM.DEPARTAMENTO"]
        for fila in filas
    }
    areas_csv = {
        fila["COD.AMBITO/AREA"]: (fila["DES.AMBITO/AREA"], fila["COD.DEPARTAMENTO"])
        for fila in filas
    }
    departamentos_por_codigo = {d["codigo"]: d for d in departamentos_actuales}
    areas_por_codigo = {a["codigo"]: a for a in areas_actuales}

    def estado(nombre_csv: str, actual: Dict | None, campo: str = "nombre") -> str:
        if actual is None:
            return "CREAR"
        return "EXISTENTE" if actual.get(campo) == nombre_csv else "CONFLICTO"

    departamentos = [
        {"codigo": codigo, "nombre": nombre, "estado": estado(nombre, departamentos_por_codigo.get(codigo))}
        for codigo, nombre in sorted(departamentos_csv.items())
    ]
    areas = []
    estado_area_por_codigo: dict[str, str] = {}
    for codigo, (nombre, departamento_codigo) in sorted(areas_csv.items()):
        actual = areas_por_codigo.get(codigo)
        departamento_actual = departamentos_por_codigo.get(departamento_codigo)
        estado_area = estado(nombre, actual)
        if (
            estado_area == "EXISTENTE"
            and (departamento_actual is None or actual.get("departamento_id") != departamento_actual["id"])
        ):
            estado_area = "CONFLICTO"
        areas.append({
            "codigo": codigo,
            "nombre": nombre,
            "departamento_codigo": departamento_codigo,
            "estado": estado_area,
        })
        estado_area_por_codigo[codigo] = estado_area

    actividades_por_clave = {
        (
            actividad["codigo"], actividad["tipo"], actividad["codigo_grupo"],
            actividad.get("area_id"), actividad.get("curso_academico"),
        ): actividad
        for actividad in actividades_actuales
    }
    actividades = {"CREAR": 0, "EXISTENTE": 0, "PENDIENTE_AREA": 0}
    for ficha in fichas:
        area = areas_por_codigo.get(ficha["area_codigo_externo"])
        if not area:
            # El área puede no existir aún porque también forma parte del
            # mismo plan. En ese caso la importación transaccional la crea
            # antes que sus actividades, por lo que la acción correcta es
            # CREAR y no una falsa dependencia pendiente.
            estado_area = estado_area_por_codigo.get(ficha["area_codigo_externo"])
            actividades["CREAR" if estado_area == "CREAR" else "PENDIENTE_AREA"] += 1
            continue
        clave = (
            ficha["codigo"], ficha["tipo"], ficha["codigo_grupo"],
            area["id"], ficha["curso_academico"],
        )
        actividades["EXISTENTE" if clave in actividades_por_clave else "CREAR"] += 1

    return {
        "resumen": resumen_importacion(filas),
        "departamentos": departamentos,
        "areas": areas,
        "actividades": actividades,
        "profesores_a_crear_sin_asignacion": len(construir_perfiles_sinteticos(filas)),
        "lineas_resultado_referencia": len(construir_lineas_reparto_referencia(filas)),
        "repartos_confirmados_a_crear": 0,
        "modo": "CATALOGO_BASE",
        "importacion_habilitada": True,
        "motivo_bloqueo": (
            "Se crearán perfiles, categorías, cuentas y horarios sintéticos para probar el flujo. "
            "No se importará ninguna adjudicación profesor--grupo del CSV."
        ),
    }
