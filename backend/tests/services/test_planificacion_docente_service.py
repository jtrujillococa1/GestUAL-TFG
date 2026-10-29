from datetime import date

from services.planificacion_docente_service import PlanificacionDocenteService


def test_fecha_oficial_prevalece_sobre_fin_generico_sin_crear_semanas():
    actividad = {'origen_horario': 'UAL_OFICIAL', 'horario_detallado': [
        {'fecha': '2027-06-03', 'inicio': '16:00', 'fin': '18:00'},
    ]}
    periodos = [{'fecha_inicio': date(2027, 2, 15), 'fecha_fin': date(2027, 5, 28)}]
    servicio = PlanificacionDocenteService()
    resultado = servicio._sesiones_de_horario_oficial(actividad, periodos, set())
    assert [(s['fecha'], s['horas']) for s in resultado] == [(date(2027, 6, 3), 2)]
    assert servicio._sesiones_de_horario_oficial(actividad, periodos, {date(2027, 6, 3)}) == []
    actividad['origen_horario'] = 'UAL_REFERENCIA_2025_26'
    assert servicio._sesiones_de_horario_oficial(actividad, periodos, set()) == []


def test_horario_semanal_no_se_alarga_por_ser_oficial():
    actividad = {'origen_horario': 'UAL_OFICIAL', 'horario': 'Jueves 16:00-18:00', 'dias': 'Jueves'}
    periodos = [{'fecha_inicio': date(2027, 5, 24), 'fecha_fin': date(2027, 5, 28)}]
    sesiones = PlanificacionDocenteService()._sesiones_de_horario_oficial(actividad, periodos, set())
    assert [s['fecha'] for s in sesiones] == [date(2027, 5, 27)]


def test_fechas_festivas_no_se_extienden_a_otras_semanas():
    actividad={'horario':'Lunes 09:00-11:00','dias':'Lunes','horario_detallado':[
        {'fecha':'2026-10-12','inicio':'09:00','fin':'11:00'},
    ]}
    periodos=[{'fecha_inicio':date(2026,9,1),'fecha_fin':date(2026,12,31)}]
    assert PlanificacionDocenteService()._sesiones_de_horario_oficial(actividad,periodos,{date(2026,10,12)})==[]


def test_respeta_semanas_concretas_y_no_duplica_sesiones():
    sesion={'fecha':'2026-10-05','inicio':'09:00','fin':'11:00'}
    actividad={'horario':'Lunes 09:00-11:00','dias':'Lunes','horario_detallado':[sesion,sesion,{'fecha':'2026-10-12','inicio':'09:00','fin':'11:00'}]}
    periodos=[{'fecha_inicio':date(2026,9,1),'fecha_fin':date(2026,12,31)}]
    resultado=PlanificacionDocenteService()._sesiones_de_horario_oficial(actividad,periodos,{date(2026,10,12)})
    assert [(s['fecha'],s['horas']) for s in resultado]==[(date(2026,10,5),2)]


class RepositorioPlanificacionFalso:
    def __init__(self):
        self.borradas = []
        self.guardadas = []

    def get_actividades_logicas(self, actividad_id):
        return [
            {
                "id": 10, "codigo": "4015", "tipo": "GD", "codigo_grupo": "A",
                "curso_academico": "2026/2027", "horas_actividad": 41,
                "duracion": "Primer cuatrimestre", "tipo_estudio": "GRA",
                "requiere_horario": True, "horario_detallado": [
                    {"fecha": "2026-09-15", "inicio": "09:00", "fin": "10:30"},
                ],
            },
            {
                "id": 11, "codigo": "4015", "tipo": "GD", "codigo_grupo": "A",
                "curso_academico": "2026/2027", "horas_actividad": 41,
                "duracion": "Primer cuatrimestre", "tipo_estudio": "GRA",
                "requiere_horario": True, "horario_detallado": [
                    {"fecha": "2026-09-15", "inicio": "09:00", "fin": "10:30"},
                ],
            },
        ]

    def get_repartos_actividades(self, actividad_ids):
        assert list(actividad_ids) == [10, 11]
        return [
            {"reparto_id": 101, "profesor_id": 1, "horas_asignadas": 20},
            {"reparto_id": 102, "profesor_id": 2, "horas_asignadas": 21},
        ]

    def borrar_plan_actividades(self, actividad_ids):
        self.borradas.append(list(actividad_ids))

    def get_cursos_con_calendario(self):
        return ["2026/2027"]

    def get_periodos(self, curso, tipo_estudio):
        assert (curso, tipo_estudio) == ("2026/2027", "GRADO")
        return [{
            "cuatrimestre": "PRIMERO", "fecha_inicio": date(2026, 9, 10),
            "fecha_fin": date(2026, 12, 22),
        }]

    def get_excepciones(self, curso):
        return []

    def guardar_plan(self, actividad_id, curso, sesiones):
        self.guardadas = [actividad_id, curso, list(sesiones)]
        return len(self.guardadas[2])


def test_regenera_una_actividad_compartida_sin_repartir_sus_semanas():
    servicio = PlanificacionDocenteService()
    repo = RepositorioPlanificacionFalso()
    servicio.repo = repo

    resultado = servicio.regenerar_actividad(11)

    assert resultado["actividad_id"] == 10
    assert resultado["actividad_ids"] == [10, 11]
    assert repo.borradas == [[10, 11]]
    # Cada docente recibe la misma franja oficial; su cuota sigue siendo 20/21.
    assert [(fila["profesor_id"], fila["horas"], fila["horas_adjudicadas"])
            for fila in repo.guardadas[2] if fila["estado"] == "PLANIFICADA"] == [
        (1, 1.5, 20.0),
        (2, 1.5, 21.0),
    ]
