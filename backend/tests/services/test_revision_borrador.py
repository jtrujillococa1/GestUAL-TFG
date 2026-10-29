"""Regresiones del resumen de horas durante una devolución."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.ordenacion_service import OrdenacionService


class _Profesores:
    def find_for_ordenacion(self):
        return [{
            "id": 7,
            "nombre": "Marta",
            "apellidos": "Ortega",
            "carga_docente": 6.0,
            "area_id": 16,
            "area_ids": [16],
            "horas_objetivo_por_area": {16: 6.0},
        }]


class _Actividades:
    def find_for_ordenacion(self):
        return [{"id": 100, "area_id": 16}]


class _Repartos:
    def find_borrador_by_profesor(self, _profesor, _area_id):
        return [{
            "actividad_id": 100,
            "profesor": "Ortega, Marta",
            "codigo": "BD101",
            "nombre_asignatura": "Bases de Datos",
            "tipo": "GD",
            "codigo_grupo": "T1",
            "grupo": "Teoría 1",
            "horas": 3.0,
        }]

    def find_all_confirmadas(self):
        return [{"actividad_id": 100, "profesor": "Ortega, Marta", "horas": 3.0}]

    def find_revisiones_pendientes_profesor(self, _area_id, _profesor_id):
        return [{
            "id": 1,
            "actividad_id": 100,
            "horas_devuelta": 3.0,
            "motivo": "Cambiar la distribución",
            "nombre_asignatura": "Bases de Datos",
            "codigo": "BD101",
            "grupo": "Teoría 1",
        }]

    def get_control_area(self, _area_id):
        return {"version": 4, "cerrada": False}


def test_borrador_revision_separa_confirmadas_de_nuevas_y_cierra_la_carga():
    servicio = object.__new__(OrdenacionService)
    servicio.profesor_repo = _Profesores()
    servicio.actividad_repo = _Actividades()
    servicio.reparto_repo = _Repartos()

    borrador = servicio.get_borrador("Ortega, Marta", 16)

    assert borrador.horas_confirmadas == 3.0
    assert borrador.horas_seleccionadas == 3.0
    assert borrador.horas_confirmadas + borrador.horas_seleccionadas == 6.0
    assert borrador.horas_restantes == 0.0
    assert borrador.turno_completo is True
    assert borrador.revisiones_pendientes[0]["actividad_id"] == 100
