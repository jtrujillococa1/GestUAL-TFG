"""Pruebas aisladas del ciclo de decisión de propuestas de conflicto."""
from contextlib import contextmanager
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class CursorConflictos:
    """Cursor mínimo que permite probar el repositorio sin una base de datos."""

    def __init__(self, propuesta):
        self.propuesta = propuesta
        self.ejecutadas = []
        self.lotes = []
        self._una = None
        self._varias = []

    def execute(self, sql, parametros=None):
        consulta = " ".join(sql.split())
        self.ejecutadas.append((consulta, parametros))
        if consulta.startswith("SELECT estado, version_base, propuesta"):
            self._una = ("PENDIENTE", 7, self.propuesta)
        elif consulta.startswith("SELECT id, horas_area FROM actividades"):
            self._varias = [(101, 6.0)]
        elif "SELECT profesor.id," in consulta:
            self._varias = [(201, 6.0)]
        else:
            self._una = None
            self._varias = []

    def executemany(self, sql, parametros):
        self.lotes.append((" ".join(sql.split()), list(parametros)))

    def fetchone(self):
        return self._una

    def fetchall(self):
        return self._varias


class ConexionConflictos:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


@contextmanager
def conexion_falsa(cursor):
    yield ConexionConflictos(cursor)


def preparar_repositorio(monkeypatch, propuesta):
    """Configura una transacción falsa y registra sus bloqueos/eventos."""
    import repositories.reparto_repository as modulo
    from repositories.reparto_repository import RepartoRepository

    cursor = CursorConflictos(propuesta)
    bloqueos = []
    eventos = []

    def bloquear(_cur, area_id, version_esperada=None, permitir_cerrada=False):
        bloqueos.append((area_id, version_esperada, permitir_cerrada))
        return {"version": 7, "estado": "ABIERTA"}

    def avanzar(_cur, area_id):
        assert area_id == 77
        return 8

    def registrar(_cur, area_id, tipo, usuario_id=None, detalle=None):
        eventos.append((area_id, tipo, usuario_id, detalle))

    monkeypatch.setattr(modulo, "conexion_ctx", lambda: conexion_falsa(cursor))
    monkeypatch.setattr(RepartoRepository, "_bloquear_control_area", staticmethod(bloquear))
    monkeypatch.setattr(RepartoRepository, "_avanzar_version", staticmethod(avanzar))
    monkeypatch.setattr(RepartoRepository, "_registrar_evento", staticmethod(registrar))
    return RepartoRepository(), cursor, bloqueos, eventos


def test_rechazar_propuesta_bloquea_solo_el_area_y_no_toca_repartos(monkeypatch):
    repositorio, cursor, bloqueos, eventos = preparar_repositorio(monkeypatch, {"plan": []})

    resultado = repositorio.decidir_propuesta_conflicto(
        propuesta_id=41, area_id=77, aprobar=False, usuario_id=9, motivo_rechazo="Horario incompatible",
    )

    assert resultado == {"id": 41, "area_id": 77, "estado": "RECHAZADA", "version": 7}
    assert bloqueos == [(77, None, True), (77, 7, True)]
    assert any("SET estado='RECHAZADA'" in consulta for consulta, _ in cursor.ejecutadas)
    assert not any("DELETE FROM reparto_docente" in consulta for consulta, _ in cursor.ejecutadas)
    assert eventos == [(77, "CONFLICTO_RECHAZADO", 9, {
        "propuesta_id": 41, "motivo": "Horario incompatible",
    })]


def test_aprobar_propuesta_sustituye_reparto_y_registra_la_decision(monkeypatch):
    propuesta = {
        "plan": [{"profesor_id": 201, "actividad_id": 101, "horas": 6.0}],
        "impacto": {"movimientos": 1, "profesores_afectados": 2},
    }
    repositorio, cursor, bloqueos, eventos = preparar_repositorio(monkeypatch, propuesta)

    resultado = repositorio.decidir_propuesta_conflicto(
        propuesta_id=42, area_id=77, aprobar=True, usuario_id=9,
    )

    assert resultado == {"id": 42, "area_id": 77, "estado": "APROBADA", "version": 8}
    assert bloqueos == [(77, None, True), (77, 7, True)]
    assert cursor.lotes == [(
        "INSERT INTO reparto_docente (profesor_id, actividad_id, horas_asignadas) VALUES (%s, %s, %s)",
        [(201, 101, 6.0)],
    )]
    assert any("DELETE FROM reparto_docente AS reparto" in consulta for consulta, _ in cursor.ejecutadas)
    assert any("SET estado='APROBADA'" in consulta for consulta, _ in cursor.ejecutadas)
    assert eventos == [(77, "CONFLICTO_APROBADO", 9, {
        "propuesta_id": 42, "movimientos": 1, "profesores_afectados": 2,
    })]


def test_servicio_aprobado_regenera_calendario_e_invalida_caches(monkeypatch):
    from services.ordenacion_service import OrdenacionService
    import services.ordenacion_service as modulo_servicio
    import services.planificacion_docente_service as modulo_planificacion

    llamadas = {"reparto": [], "calendario": [], "solver": 0, "mapeo": 0}

    class RepartoFalso:
        def decidir_propuesta_conflicto(self, *args):
            llamadas["reparto"].append(args)
            return {"id": 42, "area_id": 77, "estado": "APROBADA", "version": 8}

    class ActividadesFalsas:
        def find_for_ordenacion(self):
            return [{"id": 101, "area_id": 77}, {"id": 102, "area_id": 78}]

    class MapeoFalso:
        def clear_cache(self):
            llamadas["mapeo"] += 1

    class PlanificacionFalsa:
        def regenerar_actividades(self, actividad_ids):
            llamadas["calendario"].append(actividad_ids)

    servicio = OrdenacionService()
    servicio.reparto_repo = RepartoFalso()
    servicio.actividad_repo = ActividadesFalsas()
    servicio.mapeo_repo = MapeoFalso()
    monkeypatch.setattr(modulo_planificacion, "PlanificacionDocenteService", PlanificacionFalsa)
    monkeypatch.setattr(modulo_servicio.solver_cache, "clear", lambda: llamadas.__setitem__("solver", 1))

    resultado = servicio.decidir_propuesta_conflicto(42, 77, True, 9)

    assert resultado["estado"] == "APROBADA"
    assert llamadas["reparto"] == [(42, 77, True, 9, None)]
    assert llamadas["calendario"] == [[101]]
    assert llamadas["solver"] == 1
    assert llamadas["mapeo"] == 1
