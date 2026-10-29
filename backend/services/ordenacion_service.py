"""
Servicio de Ordenación Docente.
Orquesta el flujo completo de turnos, borradores y confirmaciones.
"""

from typing import List, Dict, Optional
from decimal import Decimal, InvalidOperation
from models.schemas import (
    EstadoOrdenacionSchema,
    OpcionSchema,
    BorradorSchema,
    EleccionSchema,
    ConfirmacionResultadoSchema,
)

from repositories import (
    ProfesorRepository,
    ActividadRepository,
    RepartoRepository,
    MapeoRepository,
)

from domain.ordenacion import (
    calcular_horas_por_profesor,
    clasificar_profesores,
    obtener_profesor_actual as domain_obtener_profesor_actual,
    detectar_incidencias,
    validar_turno_completo,
    calcular_horas_restantes_actividad,
    calcular_horas_restantes_profesor,
    actividad_en_borrador,
    generar_candidatos_horas,
    construir_opcion_dict,
    priorizar_opciones,
    calcular_riesgo_estado,
    evaluar_riesgo_opcion,
    preparar_contexto_riesgo,
    validar_opcion_con_solver,
    buscar_opciones_viables,
    detectar_solape_en_elecciones,
    detectar_conflicto_en_elecciones,
    confirmar_bloque_con_solver,
)
from solver.engine import resolver_reparto, resolver_reparto_en_area
from solver.reparacion_conflictos import proponer_reparacion_area
from solver.cache import solver_cache
from solver.compatibilidad import construir_incompatibilidades
from domain.ordenacion.disponibilidad import profesor_disponible_para_actividad
from core.exceptions import (
    ProfesorNotFound,
    NotYourTurn,
    NoViableOptions,
    IncompleteTurn,
    ViabilityLost,
    OrdenacionFinished,
    OrdenacionClosed,
    OrdenacionClosureInvalid,
    ConstraintViolation,
)


def _areas_profesor(profesor: Dict) -> set[int]:
    return set(profesor.get("area_ids") or ([profesor["area_id"]] if profesor.get("area_id") else []))


def _puede_cubrir(profesor: Dict, actividad: Dict) -> bool:
    return actividad.get("area_id") is None or actividad["area_id"] in _areas_profesor(profesor)


def _horas_objetivo_en_area(profesor: Dict, area_id: int) -> float:
    cargas = profesor.get("horas_objetivo_por_area") or {}
    valor = cargas.get(area_id, cargas.get(str(area_id)))
    if valor is not None:
        return float(valor)
    # Compatibilidad con perfiles anteriores a la distribución por áreas.
    return float(profesor.get("carga_docente", 0)) if profesor.get("area_id") == area_id else 0.0


def _puede_validar_por_transporte(
    profesores: List[Dict], actividades: List[Dict], area_id: Optional[int], resultado_base: Dict,
) -> bool:
    """Detecta el caso en que una opción se puede validar sin reejecutar el solver.

    En una cola aislada, sin pares con solape confirmado y con compatibilidad
    completa dentro de su área, cualquier cantidad que no exceda ni la carga
    libre del profesor ni la cuota libre de la actividad conserva un problema
    de transporte factible. Es la misma condición que resuelve el camino
    rápido del motor, pero evita repetirlo decenas de veces al mostrar grupos.
    """
    if area_id is None or not resultado_base.get("viable", False) or not actividades:
        return False
    profesores_area = [
        profesor for profesor in profesores
        if area_id in _areas_profesor(profesor) and _horas_objetivo_en_area(profesor, area_id) > 0
    ]
    return bool(profesores_area) and (
        all(_areas_profesor(profesor) == {area_id} for profesor in profesores_area)
        and not construir_incompatibilidades(actividades)
        and all(
            _puede_cubrir(profesor, actividad)
            and profesor_disponible_para_actividad(profesor, actividad)
            for profesor in profesores_area
            for actividad in actividades
        )
    )


class OrdenacionService:
    def __init__(self):
        self.profesor_repo = ProfesorRepository()
        self.actividad_repo = ActividadRepository()
        self.reparto_repo = RepartoRepository()
        self.mapeo_repo = MapeoRepository()

    def _control_abierto(self, area_id: Optional[int]) -> Dict:
        if area_id is None:
            return {"version": 0, "cerrada": False, "estado": "ABIERTA"}
        control = self.reparto_repo.get_control_area(area_id)
        if not control.get('iniciada', True):
            raise OrdenacionClosed('El área está en preparación. Un gestor debe validar e iniciar la ordenación.')
        if control["cerrada"]:
            raise OrdenacionClosed("La ordenación de esta área está cerrada. Reábrela para realizar correcciones.")
        return control
    
    def get_estado(self, area_id: Optional[int] = None) -> EstadoOrdenacionSchema:
        control = (
            self.reparto_repo.get_control_area(area_id)
            if area_id is not None
            else {"version": 0, "cerrada": False, "cerrado_en": None}
        )
        profesores = self.profesor_repo.find_for_ordenacion()
        confirmadas = self.reparto_repo.find_all_confirmadas()
        revision = self.reparto_repo.get_revision_pendiente(area_id) if area_id is not None else None
        if area_id is not None:
            actividades = self.actividad_repo.find_for_ordenacion()
            actividad_ids = {actividad["id"] for actividad in actividades if actividad.get("area_id") == area_id}
            confirmadas = [reparto for reparto in confirmadas if reparto.get("actividad_id") in actividad_ids]
        return self._construir_estado(area_id, profesores, confirmadas, control, revision)

    @staticmethod
    def _construir_estado(
        area_id: Optional[int], profesores_base: List[Dict], confirmadas: List[Dict],
        control: Dict, revision: Optional[Dict],
    ) -> EstadoOrdenacionSchema:
        """Construye el estado de una cola a partir de datos ya cargados.

        Mantener este cálculo separado permite que la vista de todas las áreas
        reutilice el mismo catálogo, profesorado y reparto confirmado, sin
        cambiar la cola ni las reglas que determinan el turno.
        """
        profesores = list(profesores_base)
        # Cada área mantiene su propia cola y consume únicamente la parte de
        # carga que el perfil tiene asignada a esa área.
        if area_id is not None:
            profesores = [
                {**p, "carga_docente": _horas_objetivo_en_area(p, area_id)}
                for p in profesores
                if area_id in _areas_profesor(p) and _horas_objetivo_en_area(p, area_id) > 0
            ]

        horas_por_profesor = calcular_horas_por_profesor(profesores, confirmadas)
        completados, pendientes = clasificar_profesores(profesores, horas_por_profesor)
        if revision:
            # Una devolución no reorganiza la cola ordinaria. Se coloca al
            # docente afectado al frente de la vista para que la corrección
            # sea explícita y el resto de personas conserve su prioridad.
            pendientes = sorted(
                pendientes,
                key=lambda profesor: 0 if profesor.id == revision["profesor_id"] else 1,
            )
            profesor_actual = revision["profesor"]
            incidencia = (
                f"Revisión prioritaria: {revision['profesor']} debe corregir una adjudicación devuelta."
            )
        else:
            profesor_actual = domain_obtener_profesor_actual(pendientes)
            incidencia = detectar_incidencias(pendientes)
        if control["cerrada"]:
            incidencia = "La ordenación de esta área está cerrada; solo se permite consulta."
        en_preparacion = not control.get('iniciada', True)
        if en_preparacion:
            profesor_actual = None
            incidencia = 'Preparación: completa los datos y valida el inicio de esta área.'
        
        return EstadoOrdenacionSchema(
            en_preparacion=en_preparacion,
            profesor_actual=profesor_actual,
            ordenacion_terminada=profesor_actual is None or control["cerrada"],
            profesores_completados=completados,
            profesores_pendientes=pendientes,
            incidencia=incidencia,
            version=control["version"],
            cerrada=control["cerrada"],
            cerrado_en=control.get("cerrado_en"),
        )

    def get_estados_por_area(self, area_ids: List[int]) -> Dict[int, EstadoOrdenacionSchema]:
        """Obtiene varias colas reutilizando las lecturas comunes.

        La pantalla de selección consulta todas las áreas visibles. Antes cada
        una volvía a leer el catálogo, los perfiles y todas las confirmaciones;
        para departamentos grandes eso multiplicaba innecesariamente el coste.
        """
        ids = sorted({int(area_id) for area_id in area_ids})
        if not ids:
            return {}

        profesores = self.profesor_repo.find_for_ordenacion()
        actividades = self.actividad_repo.find_for_ordenacion()
        actividad_area = {actividad["id"]: actividad.get("area_id") for actividad in actividades}
        confirmadas_por_area: Dict[int, List[Dict]] = {area_id: [] for area_id in ids}
        for reparto in self.reparto_repo.find_all_confirmadas():
            area_reparto = actividad_area.get(reparto.get("actividad_id"))
            if area_reparto in confirmadas_por_area:
                confirmadas_por_area[area_reparto].append(reparto)

        estados: Dict[int, EstadoOrdenacionSchema] = {}
        for area_id in ids:
            control = self.reparto_repo.get_control_area(area_id)
            revision = self.reparto_repo.get_revision_pendiente(area_id)
            estados[area_id] = self._construir_estado(
                area_id, profesores, confirmadas_por_area[area_id], control, revision,
            )
        return estados
    
    def get_profesor_actual(self, area_id: Optional[int] = None) -> Optional[str]:
        estado = self.get_estado(area_id)
        return estado.profesor_actual
    
    def get_opciones(
        self,
        nombre_completo: str,
        area_id: Optional[int] = None,
        offset: int = 0,
        limit: Optional[int] = None,
        actividad_evaluada: Optional[int] = None,
        horas_evaluadas: Optional[float] = None,
    ) -> List[OpcionSchema]:
        self._control_abierto(area_id)
        profesor_actual = self.get_profesor_actual(area_id)
        if profesor_actual != nombre_completo:
            raise NotYourTurn(f"No es el turno de '{nombre_completo}'. Turno actual: '{profesor_actual}'.")
        
        profesores = self.profesor_repo.find_for_ordenacion()
        profesor_data = next(
            (p for p in profesores if f"{p['apellidos']}, {p['nombre']}" == nombre_completo), None,
        )
        prioridades_profesor = (profesor_data or {}).get("prioridades_asignaturas") or {}
        actividades_todas = self.actividad_repo.find_for_ordenacion()
        actividades = (
            [actividad for actividad in actividades_todas if actividad.get("area_id") == area_id]
            if area_id is not None else actividades_todas
        )
        if actividad_evaluada is not None:
            actividades = [a for a in actividades if a['id'] == actividad_evaluada]
        # Las prioridades se aplican antes de paginar: una asignatura marcada
        # por el docente no debe quedar fuera del primer bloque solo por su
        # posición alfabética. Dentro de cada prioridad se conserva un orden
        # estable por nombre para que el catálogo sea fácil de revisar.
        actividades.sort(key=lambda actividad: (
            int(prioridades_profesor.get(str(actividad.get("codigo")), 10**6)),
            str(actividad.get("nombre_asignatura") or "").casefold(),
            str(actividad.get("codigo") or ""),
            str(actividad.get("codigo_grupo") or ""),
            str(actividad.get("tipo") or ""),
        ))
        confirmadas = self.reparto_repo.find_all_confirmadas()
        borrador = self.reparto_repo.find_borrador_by_profesor(nombre_completo)
        # Paginar las tarjetas que realmente se devolverán, no el catálogo:
        # excluir después el borrador acortaba la página y ocultaba «Cargar más».
        actividades = [
            actividad for actividad in actividades
            if (not profesor_data or _puede_cubrir(profesor_data, actividad))
            and not actividad_en_borrador(actividad, borrador)
        ]
        if limit is not None:
            inicio = max(0, int(offset))
            actividades = actividades[inicio:inicio + max(1, int(limit))]

        actividad_por_id = {actividad["id"]: actividad for actividad in actividades_todas}
        base = confirmadas + borrador
        if area_id is None:
            horas_rest_prof = calcular_horas_restantes_profesor(nombre_completo, profesores, base)
        else:
            profesor_area = next(
                (p for p in profesores if f"{p['apellidos']}, {p['nombre']}" == nombre_completo), None,
            )
            objetivo_area = _horas_objetivo_en_area(profesor_area or {}, area_id)
            horas_area = sum(
                float(eleccion["horas"])
                for eleccion in base
                if eleccion.get("profesor") == nombre_completo
                and actividad_por_id.get(eleccion.get("actividad_id"), {}).get("area_id") == area_id
            )
            horas_rest_prof = round(objetivo_area - horas_area, 1)
        
        if horas_rest_prof is None or horas_rest_prof <= 0:
            return []
        
        # El riesgo se evalúa en el área activa e incorpora el borrador. El
        # contexto inmutable se reutiliza para todas las alternativas visibles.
        contexto_riesgo = preparar_contexto_riesgo(profesores, actividades_todas, area_id)
        # En la pantalla se valoran muchas tarjetas en una misma petición.
        # El resolvedor rápido solo acepta un reparto cuando ya cumple todas
        # las restricciones; si no logra construirlo, el motor exacto toma el
        # relevo. Así no se degrada la validación y se evita un timeout en
        # áreas grandes.
        resolver_opcion = (
            (lambda elecciones, perfiles, catalogo, usar_cache=True: resolver_reparto_en_area(
                elecciones, perfiles, catalogo, area_id, usar_cache=usar_cache,
                preferir_heuristico=True,
                solo_factibilidad=True,
                tiempo_limite_ms=750,
            ))
            if area_id is not None else
            (lambda elecciones, perfiles, catalogo, usar_cache=True: resolver_reparto(
                elecciones, perfiles, catalogo, usar_cache=usar_cache,
                preferir_heuristico=True,
                solo_factibilidad=True,
                tiempo_limite_ms=750,
            ))
        )
        resultado_base = resolver_opcion(base, profesores, actividades_todas, usar_cache=True)
        riesgo_base = calcular_riesgo_estado(base, contexto_riesgo)
        opciones_dict = {}
        validacion_por_transporte = _puede_validar_por_transporte(
            profesores, actividades, area_id, resultado_base,
        )

        # Área del profesor actual (pre-filtro para evitar llamadas al solver innecesarias)
        areas_profesor = _areas_profesor(profesor_data) if profesor_data else set()

        for actividad in actividades:
            if profesor_data and not _puede_cubrir(profesor_data, actividad):
                continue

            if actividad_en_borrador(actividad, borrador):
                continue
            
            horas_disp = calcular_horas_restantes_actividad(actividad, base)
            if horas_disp <= 0:
                # Una cuota agotada no es seleccionable, pero debe aparecer
                # como no viable. Ocultarla impedía entender por qué un turno
                # se había quedado sin salida y contradecía el criterio de
                # mostrar también las alternativas descartadas.
                opcion = construir_opcion_dict(
                    nombre_completo, actividad, 0.0, horas_rest_prof,
                    0.0, resultado_base, riesgo_base,
                )
                opcion["viable"] = False
                opcion["motivo_no_viable"] = (
                    "La cuota de esta actividad ya está completamente asignada."
                )
                opcion["bloqueada_por_solape"] = False
                opciones_dict[actividad["id"]] = opcion
                continue
            
            candidatos = generar_candidatos_horas(horas_disp, horas_rest_prof)
            if horas_evaluadas is not None:
                if horas_evaluadas > min(horas_disp, horas_rest_prof):
                    raise ConstraintViolation('La cantidad supera las horas disponibles de la actividad o del profesor en esta área.')
                candidatos = [horas_evaluadas]
            if not candidatos:
                continue
            
            resultado_busqueda = buscar_opciones_viables(
                nombre_completo, actividad, candidatos,
                confirmadas, borrador, profesores, actividades_todas, resolver_opcion,
                resultado_rapido=resultado_base if validacion_por_transporte else None,
            )
            
            if resultado_busqueda:
                horas = resultado_busqueda["horas"]
                resultado_solver = resultado_busqueda["resultado_solver"]
                horas_tras = round(horas_rest_prof - horas, 1)
                eleccion_simulada = {
                    "profesor": nombre_completo,
                    "actividad_id": actividad.get("id"),
                    "codigo": actividad["codigo"],
                    "tipo": actividad["tipo"],
                    "tipo_actividad": actividad["tipo"],
                    "codigo_grupo": actividad["codigo_grupo"],
                    "grupo": actividad["grupo"],
                    "horas": horas,
                }
                riesgo_opcion = evaluar_riesgo_opcion(
                    base + [eleccion_simulada],
                    resultado_solver,
                    contexto_riesgo,
                    riesgo_base,
                    resultado_base,
                )
                opcion = construir_opcion_dict(
                    nombre_completo, actividad, horas, horas_tras,
                    horas_disp, resultado_solver, riesgo_opcion,
                )
                opcion["viable"] = resultado_busqueda.get("viable", False)
                opcion["motivo_no_viable"] = resultado_busqueda.get("motivo_no_viable")
                opcion["bloqueada_por_solape"] = resultado_busqueda.get("bloqueada_por_solape", False)
                opciones_dict[actividad["id"]] = opcion
        
        opciones_ordenadas = priorizar_opciones(list(opciones_dict.values()))
        for item in opciones_ordenadas:
            valor = prioridades_profesor.get(str(item["opcion"].get("codigo")))
            try:
                item["prioridad_asignatura"] = int(valor) if valor is not None else None
            except (TypeError, ValueError):
                item["prioridad_asignatura"] = None
        opciones_ordenadas.sort(key=lambda item: (
            item["prioridad_asignatura"] is None,
            item["prioridad_asignatura"] or 10**6,
            str(item["opcion"].get("nombre_asignatura") or item["opcion"].get("codigo") or "").casefold(),
        ))
        
        return [
            OpcionSchema(
                opcion=EleccionSchema(**item["opcion"]),
                horas_restantes=item["horas_restantes"],
                horas_maximas_actividad=item["horas_maximas_actividad"],
                categoria=item["categoria"],
                total_repartos=item["total_repartos"],
                actividades_divididas=item.get("actividades_divididas", 0),
                riesgo=item.get("riesgo", 0),
                riesgo_nivel=item.get("riesgo_nivel", "BAJO"),
                riesgo_impacto=item.get("riesgo_impacto", 0),
                riesgo_motivos=item.get("riesgo_motivos", []),
                riesgo_desglose=item.get("riesgo_desglose", {}),
                viable=item.get("viable", True),
                motivo_no_viable=item.get("motivo_no_viable"),
                bloqueada_por_solape=item.get("bloqueada_por_solape", False),
                cached=item.get("cached", False),
                prioridad_asignatura=item.get("prioridad_asignatura"),
            )
            for item in opciones_ordenadas
        ]
    
    def get_borrador(self, nombre_completo: str, area_id: Optional[int] = None) -> BorradorSchema:
        profesores = self.profesor_repo.find_for_ordenacion()
        
        # Buscar profesor por nombre completo
        profesor = None
        for p in profesores:
            nc = f"{p['apellidos']}, {p['nombre']}"
            if nc == nombre_completo:
                profesor = p
                break
        
        if not profesor:
            raise ProfesorNotFound(f"Profesor '{nombre_completo}' no encontrado.")
        
        seleccion = self.reparto_repo.find_borrador_by_profesor(nombre_completo, area_id)
        confirmadas = self.reparto_repo.find_all_confirmadas()

        if area_id is not None:
            actividades = {a["id"]: a for a in self.actividad_repo.find_for_ordenacion()}
            conf_horas = sum(
                float(e["horas"]) for e in confirmadas
                if e["profesor"] == nombre_completo
                and actividades.get(e.get("actividad_id"), {}).get("area_id") == area_id
            )
            carga_docente = _horas_objetivo_en_area(profesor, area_id)
        else:
            conf_horas = sum(float(e["horas"]) for e in confirmadas if e["profesor"] == nombre_completo)
            carga_docente = float(profesor["carga_docente"])
        sel_horas = sum(float(e["horas"]) for e in seleccion)
        horas_rest = round(carga_docente - conf_horas - sel_horas, 1)

        # Al devolver una línea, esta se incorpora al borrador para que se
        # pueda confirmar de nuevo sin reconstruir todo el turno. La
        # interfaz necesita saberlo para permitir sustituirla de forma
        # explícita: primero retira solo esa línea y después muestra las
        # alternativas compatibles para las horas liberadas.
        revisiones_pendientes = (
            self.reparto_repo.find_revisiones_pendientes_profesor(area_id, profesor["id"])
            if area_id is not None
            else []
        )
        
        return BorradorSchema(
            profesor=nombre_completo,
            seleccion=[EleccionSchema(**e) for e in seleccion],
            horas_confirmadas=conf_horas,
            horas_seleccionadas=sel_horas,
            carga_docente=carga_docente,
            horas_restantes=horas_rest,
            turno_completo=abs(horas_rest) < 0.01,
            version=(self.reparto_repo.get_control_area(area_id)["version"] if area_id is not None else 0),
            cerrada=(self.reparto_repo.get_control_area(area_id)["cerrada"] if area_id is not None else False),
            revisiones_pendientes=revisiones_pendientes,
        )
    
    def add_to_borrador(self, nombre_completo: str, codigo: str, codigo_grupo: str,
                        tipo: str, horas: float, actividad_id: Optional[int] = None,
                        area_id: Optional[int] = None, version_ordenacion: Optional[int] = None,
                        usuario_id: Optional[int] = None) -> Dict:
        control = self._control_abierto(area_id)
        try:
            valor_horas = Decimal(str(horas))
            if not valor_horas.is_finite() or valor_horas <= 0 or valor_horas * 10 != (valor_horas * 10).to_integral_value():
                raise ValueError()
        except (ValueError, InvalidOperation):
            raise ConstraintViolation("Introduce horas positivas en pasos de 0,1 (por ejemplo, 6,1; no 6,01).")
        profesor_actual = self.get_profesor_actual(area_id)
        if profesor_actual != nombre_completo:
            raise NotYourTurn(f"No es el turno de '{nombre_completo}'. Turno actual: '{profesor_actual}'.")
        
        profesores = self.profesor_repo.find_for_ordenacion()
        actividades_todas = self.actividad_repo.find_for_ordenacion()
        actividades = (
            [actividad for actividad in actividades_todas if actividad.get("area_id") == area_id]
            if area_id is not None else actividades_todas
        )
        profesor = next((p for p in profesores if f"{p['apellidos']}, {p['nombre']}" == nombre_completo), None)
        actividad = next((a for a in actividades if a["id"] == actividad_id), None) if actividad_id else None
        if actividad is None:
            candidatas = [a for a in actividades if (a["codigo"], a["codigo_grupo"], a["tipo"]) == (codigo, codigo_grupo, tipo)]
            if profesor:
                candidatas = [a for a in candidatas if _puede_cubrir(profesor, a)]
            actividad = candidatas[0] if len(candidatas) == 1 else None
        if actividad is None or (profesor and not _puede_cubrir(profesor, actividad)):
            raise ViabilityLost("La actividad no está disponible para el área de este profesor.")
        nueva_eleccion = {
            "profesor": nombre_completo, "actividad_id": actividad["id"],
            "codigo": actividad["codigo"], "codigo_grupo": actividad["codigo_grupo"],
            "tipo": actividad["tipo"], "tipo_actividad": actividad["tipo"], "horas": horas,
        }
        confirmadas = self.reparto_repo.find_all_confirmadas()
        borrador = self.reparto_repo.find_borrador_by_profesor(nombre_completo)

        # Solo el horario del profesor que está eligiendo puede cambiar. Las
        # adjudicaciones del resto ya se validaron al confirmarse y no deben
        # rehacerse aquí, especialmente en áreas con un catálogo grande.
        elecciones_horario = [
            eleccion for eleccion in confirmadas + borrador
            if eleccion.get("profesor") == nombre_completo
        ] + [nueva_eleccion]
        motivo_solape = detectar_solape_en_elecciones(elecciones_horario, actividades_todas)
        if motivo_solape:
            raise ViabilityLost(motivo_solape)
        
        resolver_borrador = (
            (lambda elecciones, perfiles, catalogo, usar_cache=True: resolver_reparto_en_area(
                elecciones, perfiles, catalogo, area_id, usar_cache=usar_cache,
                preferir_heuristico=True, solo_factibilidad=True, tiempo_limite_ms=15000,
            ))
            if area_id is not None else
            (lambda elecciones, perfiles, catalogo, usar_cache=True: resolver_reparto(
                elecciones, perfiles, catalogo, usar_cache=usar_cache,
                preferir_heuristico=True,
            ))
        )
        resultado = validar_opcion_con_solver(
            nueva_eleccion, confirmadas, borrador, profesores, actividades_todas,
            resolver_borrador,
        )
        
        if not resultado["viable"]:
            diagnostico = resultado.get("diagnostico") or []
            detalle = " ".join(diagnostico[:2]) if diagnostico else "La opción no mantiene la viabilidad global."
            raise ViabilityLost(detalle)
        
        mapeos = self.mapeo_repo.get_mapeos()
        profesor_id = mapeos["prof_a_id"][nombre_completo]
        actividad_id = actividad["id"]
        
        version = self.reparto_repo.upsert_borrador(
            profesor_id, actividad_id, horas, area_id,
            control["version"] if version_ordenacion is None else version_ordenacion,
            usuario_id,
        )
        
        return {
            "ok": True,
            "borrador": self.get_borrador(nombre_completo, area_id),
            "cached": resultado.get("cached", False),
            "version": version,
        }
    
    def remove_from_borrador(self, nombre_completo: str, codigo: str, codigo_grupo: str,
                             tipo: str, actividad_id: Optional[int] = None,
                             area_id: Optional[int] = None, version_ordenacion: Optional[int] = None,
                             usuario_id: Optional[int] = None) -> Dict:
        control = self._control_abierto(area_id)
        profesor_actual = self.get_profesor_actual(area_id)
        if profesor_actual != nombre_completo:
            raise NotYourTurn(f"No es el turno de '{nombre_completo}'.")
        
        mapeos = self.mapeo_repo.get_mapeos()
        try:
            profesor_id = mapeos["prof_a_id"][nombre_completo]
            actividad_id = actividad_id or mapeos["actividad_a_id"][(codigo, codigo_grupo, tipo)]
            version = self.reparto_repo.delete_borrador_linea(
                profesor_id, actividad_id, area_id,
                control["version"] if version_ordenacion is None else version_ordenacion,
                usuario_id,
            )
        except KeyError:
            version = control["version"]
        
        return {"ok": True, "borrador": self.get_borrador(nombre_completo, area_id), "version": version}
    
    def clear_borrador(self, nombre_completo: str, area_id: Optional[int] = None,
                       version_ordenacion: Optional[int] = None, usuario_id: Optional[int] = None) -> Dict:
        control = self._control_abierto(area_id)
        profesor_actual = self.get_profesor_actual(area_id)
        if profesor_actual != nombre_completo:
            raise NotYourTurn(f"No es el turno de '{nombre_completo}'.")
        
        mapeos = self.mapeo_repo.get_mapeos()
        profesor_id = mapeos["prof_a_id"][nombre_completo]
        version = self.reparto_repo.clear_borrador_profesor(
            profesor_id, area_id,
            control["version"] if version_ordenacion is None else version_ordenacion,
            usuario_id,
        )
        
        return {"ok": True, "mensaje": f"Borrador de '{nombre_completo}' limpiado.", "version": version}
    
    def confirmar_turno(self, area_id: Optional[int] = None,
                        version_ordenacion: Optional[int] = None,
                        usuario_id: Optional[int] = None) -> ConfirmacionResultadoSchema:
        control = self._control_abierto(area_id)
        profesor_actual = self.get_profesor_actual(area_id)
        if profesor_actual is None:
            raise OrdenacionFinished("La ordenacion ya ha terminado.")
        
        profesores = self.profesor_repo.find_for_ordenacion()
        actividades = self.actividad_repo.find_for_ordenacion()
        confirmadas = self.reparto_repo.find_all_confirmadas()
        borrador = self.reparto_repo.find_borrador_by_profesor(profesor_actual, area_id)
        
        if not borrador:
            raise IncompleteTurn("El borrador esta vacio. No hay nada que confirmar.")

        todas = confirmadas + borrador
        # La confirmación solo incorpora el borrador del turno actual. Se
        # comprueba su agenda completa sin recalcular los horarios ya
        # confirmados de los demás docentes.
        elecciones_horario = [
            eleccion for eleccion in todas
            if eleccion.get("profesor") == profesor_actual
        ]
        motivo_solape = detectar_solape_en_elecciones(elecciones_horario, actividades)
        if motivo_solape:
            raise ViabilityLost(motivo_solape)
        if area_id is None:
            completo, horas_rest, error = validar_turno_completo(profesor_actual, profesores, todas)
        else:
            profesor = next(
                (p for p in profesores if f"{p['apellidos']}, {p['nombre']}" == profesor_actual), None,
            )
            objetivo = _horas_objetivo_en_area(profesor or {}, area_id)
            horas_borrador = sum(float(eleccion["horas"]) for eleccion in borrador)
            horas_confirmadas = sum(
                float(eleccion["horas"])
                for eleccion in confirmadas
                if eleccion["profesor"] == profesor_actual
                and next((a for a in actividades if a["id"] == eleccion.get("actividad_id")), {}).get("area_id") == area_id
            )
            horas_rest = round(objetivo - horas_confirmadas - horas_borrador, 1)
            completo = abs(horas_rest) < 0.01
            error = None if completo else f"Faltan {horas_rest}h por asignar."
        
        if not completo:
            raise IncompleteTurn(error or f"Faltan {horas_rest}h por asignar.")
        
        # La cola se confirma dentro de su área. Revalidarla con el catálogo
        # completo obliga a resolver simultáneamente todas las áreas (aunque
        # sus colas sean independientes) y, con datos reales, puede agotar el
        # tiempo de la petición. El mismo resolvedor local ya se utiliza al
        # mostrar y añadir opciones. Si un profesor comparte carga entre áreas,
        # ``resolver_reparto_en_area`` delega automáticamente en el global.
        resolver_confirmacion = (
            (lambda elecciones, perfiles, catalogo, usar_cache=True: resolver_reparto_en_area(
                elecciones, perfiles, catalogo, area_id, usar_cache=usar_cache,
                preferir_heuristico=True, solo_factibilidad=True, tiempo_limite_ms=15000,
            ))
            if area_id is not None else
            (lambda elecciones, perfiles, catalogo, usar_cache=True: resolver_reparto(
                elecciones, perfiles, catalogo, usar_cache=usar_cache,
                preferir_heuristico=True,
            ))
        )
        resultado = confirmar_bloque_con_solver(
            todas, profesores, actividades, resolver_confirmacion,
        )
        if not resultado["viable"]:
            diagnostico = resultado.get("diagnostico") or []
            detalle = " ".join(diagnostico[:2]) if diagnostico else "El bloque no mantiene la viabilidad global."
            raise ViabilityLost(detalle)
        
        mapeos = self.mapeo_repo.get_mapeos()
        profesor_id = mapeos["prof_a_id"][profesor_actual]
        
        version = self.reparto_repo.confirmar_borrador(
            profesor_id, borrador, mapeos["actividad_a_id"], area_id,
            control["version"] if version_ordenacion is None else version_ordenacion,
            usuario_id,
        )

        # El calendario semanal es una proyección de las adjudicaciones, nunca
        # una condición para confirmar el turno. Si todavía no se ha aplicado
        # la migración de planificación, la adjudicación ya confirmada sigue
        # siendo válida y se podrá regenerar después desde administración.
        try:
            from services.planificacion_docente_service import PlanificacionDocenteService
            PlanificacionDocenteService().regenerar_actividades(
                [eleccion["actividad_id"] for eleccion in borrador if eleccion.get("actividad_id")]
            )
        except Exception:
            pass
        
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
        
        nuevo_estado = self.get_estado(area_id)
        siguiente = nuevo_estado.profesor_actual
        
        return ConfirmacionResultadoSchema(
            ok=True,
            profesor_confirmado=profesor_actual,
            siguiente_profesor=siguiente,
            ordenacion_terminada=siguiente is None,
            version=version or 0,
        )
    
    def reset_ordenacion(self) -> Dict:
        self.reparto_repo.reset_all()
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
        return {"ok": True, "mensaje": "Ordenacion reiniciada."}

    def reset_ordenacion_por_areas(self, area_ids: List[int]) -> Dict:
        """Reinicia una o varias colas de área sin tocar el resto del curso."""
        resultado = self.reparto_repo.reset_por_areas(area_ids)
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
        return {"ok": True, **resultado}

    def devolver_adjudicacion(
        self, actividad_id: int, profesor_id: int, area_id: int, motivo: str,
        usuario_id: Optional[int] = None, version_ordenacion: Optional[int] = None,
    ) -> Dict:
        """Inicia una revisión puntual sin reiniciar el área.

        La línea confirmada se mueve a borrador y el profesor afectado pasa a
        ser el turno activo de revisión. El solver y los mapeos se invalidan
        para que las siguientes opciones reflejen inmediatamente la cuota
        liberada.
        """
        resultado = self.reparto_repo.devolver_adjudicacion(
            actividad_id=actividad_id,
            profesor_id=profesor_id,
            area_id=area_id,
            motivo=motivo,
            usuario_id=usuario_id,
            version_esperada=version_ordenacion,
        )
        try:
            from services.planificacion_docente_service import PlanificacionDocenteService
            PlanificacionDocenteService().regenerar_actividad(actividad_id)
        except Exception:
            pass
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
        return resultado

    def crear_propuesta_conflicto(self, area_id: int, usuario_id: Optional[int] = None) -> Dict:
        """Calcula una alternativa supervisable cuando el turno no tiene salida.

        La propuesta no cambia la ordenación. Solo se persiste para que un
        responsable pueda revisarla, aprobarla o rechazarla desde Conflictos.
        """
        control = self._control_abierto(area_id)
        profesor_actual = self.get_profesor_actual(area_id)
        if not profesor_actual:
            raise ConstraintViolation("No hay un turno bloqueado en esta área.")
        opciones = self.get_opciones(profesor_actual, area_id)
        if any(opcion.viable for opcion in opciones):
            raise ConstraintViolation(
                "El turno aún dispone de opciones viables; no es necesario reorganizar adjudicaciones."
            )
        profesores = self.profesor_repo.find_for_ordenacion()
        profesor = next(
            (item for item in profesores if f"{item['apellidos']}, {item['nombre']}" == profesor_actual),
            None,
        )
        if profesor is None:
            raise ProfesorNotFound(f"Profesor '{profesor_actual}' no encontrado.")
        actividades = self.actividad_repo.find_for_ordenacion()
        confirmadas = self.reparto_repo.find_all_confirmadas()
        profesores_por_id = {item["id"]: item for item in profesores}
        actividades_por_id = {item["id"]: item for item in actividades}
        profesor_por_nombre = {
            f"{item['apellidos']}, {item['nombre']}": item["id"]
            for item in profesores
        }
        prohibiciones_horarias = set()
        anteriores = self.reparto_repo.find_propuestas_conflicto(area_id, limite=None)
        planes_excluidos = [
            fila['propuesta']['plan'] for fila in anteriores
            if fila['version_base'] == control['version']
            and fila['profesor_bloqueado_id'] == profesor['id']
            and fila.get('propuesta', {}).get('plan')
        ]
        propuesta = None

        # Una actividad compartida puede ocupar distintas sesiones según el
        # orden de sus adjudicaciones. Revalidamos el calendario exacto y, si
        # aparece un par incompatible, lo prohibimos solo a ese profesor y
        # pedimos al solver una alternativa. El límite evita bucles en datos
        # físicamente imposibles.
        for _intento in range(24):
            propuesta = proponer_reparacion_area(
                area_id, profesor["id"], profesores, actividades, confirmadas,
                prohibiciones_horarias=prohibiciones_horarias,
                planes_excluidos=planes_excluidos, max_profesores=None,
            )
            if not propuesta.get("viable"):
                raise ViabilityLost(propuesta.get("motivo") or "No se encontró un intercambio que resuelva el conflicto.")

            elecciones = []
            for linea in propuesta["plan"]:
                perfil = profesores_por_id.get(linea["profesor_id"])
                actividad = actividades_por_id.get(linea["actividad_id"])
                if perfil is None or actividad is None:
                    raise ViabilityLost("La propuesta contiene una referencia que ya no existe.")
                elecciones.append({
                    "profesor": f"{perfil['apellidos']}, {perfil['nombre']}",
                    "actividad_id": actividad["id"], "codigo": actividad["codigo"],
                    "tipo": actividad["tipo"], "tipo_actividad": actividad["tipo"],
                    "codigo_grupo": actividad["codigo_grupo"], "grupo": actividad["grupo"],
                    "horas": linea["horas"],
                })
            conflicto_horario = detectar_conflicto_en_elecciones(elecciones, actividades)
            if not conflicto_horario:
                break

            profesor_id = profesor_por_nombre.get(conflicto_horario.get("profesor"))
            actividad_id = conflicto_horario.get("actividad_id")
            otra_actividad_id = conflicto_horario.get("otra_actividad_id")
            if profesor_id is None or actividad_id is None or otra_actividad_id is None:
                raise ViabilityLost(
                    f"La propuesta calculada no es aplicable: {conflicto_horario['motivo']}"
                )
            prohibicion = (profesor_id, min(int(actividad_id), int(otra_actividad_id)), max(int(actividad_id), int(otra_actividad_id)))
            if prohibicion in prohibiciones_horarias:
                raise ViabilityLost(
                    f"La propuesta calculada no es aplicable: {conflicto_horario['motivo']}"
                )
            prohibiciones_horarias.add(prohibicion)
        else:
            raise ViabilityLost(
                "No se encontró una redistribución sin solapes tras revisar las sesiones oficiales."
            )

        if propuesta is None:
            raise ViabilityLost("No se pudo calcular una propuesta de redistribución.")
        return self.reparto_repo.crear_propuesta_conflicto(
            area_id, profesor["id"], control["version"], propuesta, usuario_id,
        )

    def get_propuestas_conflicto(self, area_id: int) -> List[Dict]:
        return self.reparto_repo.find_propuestas_conflicto(area_id)

    def decidir_propuesta_conflicto(
        self, propuesta_id: int, area_id: int, aprobar: bool, usuario_id: Optional[int],
        motivo_rechazo: Optional[str] = None,
    ) -> Dict:
        resultado = self.reparto_repo.decidir_propuesta_conflicto(
            propuesta_id, area_id, aprobar, usuario_id, motivo_rechazo,
        )
        if aprobar:
            try:
                actividades = self.actividad_repo.find_for_ordenacion()
                from services.planificacion_docente_service import PlanificacionDocenteService
                PlanificacionDocenteService().regenerar_actividades([
                    actividad["id"] for actividad in actividades if actividad.get("area_id") == area_id
                ])
            except Exception:
                # La propuesta ya es una ordenación válida. El calendario es
                # una proyección regenerable desde administración si fallase.
                resultado['advertencia_calendario'] = 'Adjudicaciones actualizadas, pero no se pudo regenerar el calendario. Es necesario regenerarlo antes de utilizarlo.'
            solver_cache.clear()
            self.mapeo_repo.clear_cache()
        return resultado

    def validar_cierre_area(self, area_id: int) -> Dict:
        """Comprueba que un área puede pasar a estado cerrado y exportable."""
        control = self.reparto_repo.get_control_area(area_id)
        estado = self.get_estado(area_id)
        profesores = self.profesor_repo.find_for_ordenacion()
        actividades = self.actividad_repo.find_for_ordenacion()
        actividades_area = [actividad for actividad in actividades if actividad.get("area_id") == area_id]
        confirmadas = self.reparto_repo.find_all_confirmadas()
        asignadas_por_actividad: Dict[int, float] = {}
        for reparto in confirmadas:
            actividad_id = reparto.get("actividad_id")
            asignadas_por_actividad[actividad_id] = asignadas_por_actividad.get(actividad_id, 0.0) + float(reparto["horas"])

        errores: List[str] = []
        advertencias: List[str] = []
        if estado.profesor_actual is not None:
            errores.append("Aún quedan profesores pendientes en la cola del área.")
        borradores = self.reparto_repo.contar_borradores_area(area_id)
        if borradores:
            errores.append(f"Hay {borradores} selección(es) aún en borrador.")
        revisiones = self.reparto_repo.contar_revisiones_pendientes(area_id)
        if revisiones:
            errores.append(f"Hay {revisiones} revisión(es) de adjudicación pendiente(s).")
        incompletas = [
            actividad for actividad in actividades_area
            if abs(asignadas_por_actividad.get(actividad["id"], 0.0) - float(actividad["horas_totales"])) > 0.01
        ]
        if incompletas:
            errores.append(f"Hay {len(incompletas)} actividad(es) cuya cuota del área no está completamente cubierta.")

        # Cerrar una cola independiente no debe recalcular ni depender de las
        # áreas ajenas pendientes. El resolvedor de área conserva el modelo
        # global cuando hay profesores compartidos; solo buscamos factibilidad.
        resultado = resolver_reparto_en_area(
            confirmadas, profesores, actividades, area_id, usar_cache=True,
            solo_factibilidad=True, tiempo_limite_ms=5000,
        )
        if not resultado.get("viable", False):
            diagnostico = resultado.get("diagnostico") or []
            if resultado.get("indeterminado"):
                errores.append("El solver no ha podido completar la validación a tiempo. No se ha cerrado el área; vuelve a intentarlo.")
            else:
                errores.append("La validación del área y sus dependencias no es viable." + (f" {' '.join(diagnostico[:2])}" if diagnostico else ""))
        horarios_pendientes = [
            actividad for actividad in actividades_area
            if actividad.get("requiere_horario", True)
            and not actividad.get("horario_confirmado", False)
        ]
        if horarios_pendientes:
            advertencias.append(
                f"{len(horarios_pendientes)} actividad(es) conservan horario provisional; no bloquean el cierre, pero deben confirmarse antes de publicar horarios oficiales."
            )

        return {
            "ok": not errores,
            "area_id": area_id,
            "version": control["version"],
            "cerrada": control["cerrada"],
            "errores": errores,
            "advertencias": advertencias,
        }

    def cerrar_area(self, area_id: int, version_ordenacion: Optional[int], usuario_id: Optional[int]) -> Dict:
        validacion = self.validar_cierre_area(area_id)
        if validacion["cerrada"]:
            raise OrdenacionClosed("La ordenación de esta área ya está cerrada.")
        if not validacion["ok"]:
            raise OrdenacionClosureInvalid(
                "No se puede cerrar la ordenación: " + " ".join(validacion["errores"]),
                validacion,
            )
        resultado = self.reparto_repo.cerrar_area(
            area_id,
            validacion["version"] if version_ordenacion is None else version_ordenacion,
            usuario_id,
        )
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
        return {"ok": True, **resultado, "advertencias": validacion["advertencias"]}

    def reabrir_area(self, area_id: int, version_ordenacion: Optional[int], usuario_id: Optional[int], motivo: str) -> Dict:
        resultado = self.reparto_repo.reabrir_area(area_id, version_ordenacion, usuario_id, motivo)
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
        return {"ok": True, **resultado}
