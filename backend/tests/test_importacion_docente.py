import importlib.util
from pathlib import Path
import sys


_RAIZ_BACKEND = Path(__file__).parents[1]
sys.path.insert(0, str(_RAIZ_BACKEND))
_RUTA_IMPORTADOR = _RAIZ_BACKEND / "services" / "importacion_docente.py"
_SPEC = importlib.util.spec_from_file_location("importacion_docente_test", _RUTA_IMPORTADOR)
assert _SPEC and _SPEC.loader
_IMPORTADOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_IMPORTADOR)

construir_fichas_actividad = _IMPORTADOR.construir_fichas_actividad
construir_lineas_reparto_referencia = _IMPORTADOR.construir_lineas_reparto_referencia
construir_profesores_origen = _IMPORTADOR.construir_profesores_origen
construir_perfiles_sinteticos = _IMPORTADOR.construir_perfiles_sinteticos
resumen_importacion = _IMPORTADOR.resumen_importacion
planificar_importacion = _IMPORTADOR.planificar_importacion
generar_horario_sintetico = _IMPORTADOR.generar_horario_sintetico


def _fila(**cambios):
    fila = {
        "COD.DEPARTAMENTO": "S145", "NOM.DEPARTAMENTO": "Informática",
        "COD.AMBITO/AREA": "AR570", "DES.AMBITO/AREA": "Área 1",
        "COD.ASIGNATURA": "4191106", "NOM.ASIGNATURA": "Programación",
        "COD.ACTIVIDAD": "83756", "ID.ACTIVIDAD": "GD", "NOM.ACTIVIDAD": "Grupo docente",
        "COD.GRUPO": "A", "ID.GRUPO": "153531", "NOM.GRUPO": "GRUPO A",
        "IDIOMA.GRUPO": "Español", "DURACION": "A", "TURNO": "Mañana",
        "HORAS ASIGNATURA": "120", "HORAS ACTIVIDAD": "41", "HORAS AMBITO/AREA": "20,5",
        "TIPO.ESTUDIO": "GRA", "COD.PLAN": "419", "NOM.PLAN": "Grado",
        "COD.CENTRO": "E01", "NOM.CENTRO": "Centro", "CICLO": "1", "CURSO": "1",
        "CARACTER": "Básica",
    }
    fila.update(cambios)
    return fila


def test_agrupa_repeticiones_y_conserva_cuota_del_area():
    fichas = construir_fichas_actividad([_fila(), _fila(**{"NOM.PROFESOR": "Otra persona"})])
    assert len(fichas) == 1
    assert fichas[0]["horas_actividad"] == 41
    assert fichas[0]["horas_area"] == 20.5
    assert fichas[0]["horario_confirmado"] is False
    assert fichas[0]["horario"] in {"09:00-10:30", "10:45-12:15", "12:30-14:00"}
    assert fichas[0]["origen_horario"] == "SINTETICO"


def test_no_mezcla_la_misma_actividad_en_dos_areas():
    fichas = construir_fichas_actividad([_fila(), _fila(**{"COD.AMBITO/AREA": "AR571"})])
    assert len(fichas) == 2


def test_preserva_trazabilidad_de_profesor_y_reparto():
    filas = [_fila(**{
        "NIF.PROFESOR": "DNI_30", "NOM.PROFESOR": "Profesor_6", "PROF.ACTIVO": "S",
        "HORAS PROFESOR": "20,5", "PROF.PRINCIPAL": "S", "COD.PLAZA": "P1",
        "ID.PLAZA": "100", "COORDINADOR": "Profesor_42",
    })]
    profesor = construir_profesores_origen(filas)[0]
    reparto = construir_lineas_reparto_referencia(filas)[0]
    resumen = resumen_importacion(filas)
    assert profesor["activo_origen"] is True
    assert reparto["es_profesor_principal"] is True
    assert reparto["horas_asignadas"] == 20.5
    assert resumen["horarios_sinteticos"] == 1
    assert resumen["horarios_pendientes_de_confirmar"] == 1
    assert resumen["profesores_con_horas_de_reparto_variables"] == 0
    assert resumen["lineas_resultado_referencia"] == 1


def test_plan_identifica_catalogo_pendiente_y_actividad_nueva():
    plan = planificar_importacion(
        [_fila()],
        [{"id": 1, "codigo": "S145", "nombre": "Informática"}],
        [{"id": 2, "codigo": "AR570", "nombre": "Área 1", "departamento_id": 1}],
        [],
    )
    assert plan["departamentos"][0]["estado"] == "EXISTENTE"
    assert plan["areas"][0]["estado"] == "EXISTENTE"
    assert plan["actividades"]["CREAR"] == 1
    assert plan["importacion_habilitada"] is True
    assert plan["repartos_confirmados_a_crear"] == 0


def test_plan_detecta_area_en_departamento_incorrecto():
    plan = planificar_importacion(
        [_fila()],
        [{"id": 1, "codigo": "S145", "nombre": "Informática"}],
        [{"id": 2, "codigo": "AR570", "nombre": "Área 1", "departamento_id": 99}],
        [],
    )
    assert plan["areas"][0]["estado"] == "CONFLICTO"


def test_plan_preve_actividades_cuando_su_area_tambien_se_creara():
    plan = planificar_importacion([_fila()], [], [], [])
    assert plan["areas"][0]["estado"] == "CREAR"
    assert plan["actividades"] == {"CREAR": 1, "EXISTENTE": 0, "PENDIENTE_AREA": 0}


def test_horario_sintetico_es_estable_y_respeta_duracion_por_tipo():
    teoria = generar_horario_sintetico("A1", "GD", "G1", "Mañana")
    practica = generar_horario_sintetico("A1", "GT", "G1", "Tarde")
    assert teoria == generar_horario_sintetico("A1", "GD", "G1", "Mañana")
    assert teoria["horario"] in {"09:00-10:30", "10:45-12:15", "12:30-14:00"}
    assert practica["horario"] in {"15:30-17:30", "17:45-19:45"}


def test_practicas_externas_se_importan_sin_horario_fijo_ni_solape_sintetico():
    fichas = construir_fichas_actividad([_fila(**{
        "NOM.ASIGNATURA": "Prácticas Externas en Empresa",
        "CARACTER": "Prácticas Externas",
    })])
    ficha = fichas[0]
    assert ficha["requiere_horario"] is False
    assert ficha["dias"] is None
    assert ficha["horario"] is None
    assert ficha["origen_horario"] == "NO_APLICA"

    resumen = resumen_importacion([_fila(**{
        "NOM.ASIGNATURA": "Prácticas Externas en Empresa",
        "CARACTER": "Prácticas Externas",
    })])
    assert resumen["horarios_sinteticos"] == 0
    assert resumen["actividades_sin_horario_fijo"] == 1


def test_perfiles_sinteticos_usar_carga_total_del_profesor_sin_grupos():
    filas = [
        _fila(**{"NIF.PROFESOR": "DNI_1", "NOM.PROFESOR": "Ana Uno", "PROF.ACTIVO": "S", "HORAS PROFESOR": "12,4"}),
        _fila(**{"NIF.PROFESOR": "DNI_1", "NOM.PROFESOR": "Ana Uno", "PROF.ACTIVO": "S", "HORAS PROFESOR": "8,1"}),
    ]
    perfiles = construir_perfiles_sinteticos(filas)
    assert perfiles == [
        {
            "identificador_origen": "DNI_1", "nombre": "Ana Uno", "apellidos": "Importado",
            "email": "dni-1@ordenacion.local", "area_codigo": "AR570", "categoria": "Catedrático",
            "fecha_ingreso": _IMPORTADOR.date(1988, 9, 1), "carga_docente": 20.5, "activo_origen": True,
        }
    ]


def test_perfiles_sinteticos_corrigen_solo_el_redondeo_para_cerrar_el_area():
    filas = [
        _fila(**{"NIF.PROFESOR": "DNI_1", "NOM.PROFESOR": "Ana", "PROF.ACTIVO": "S", "HORAS PROFESOR": "20,4"}),
    ]
    perfiles = construir_perfiles_sinteticos(filas)
    assert perfiles[0]["carga_docente"] == 20.5
