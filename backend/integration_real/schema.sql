-- Estructura sin datos extraída de la copia local; aplicar después las migraciones del proyecto.
--
-- PostgreSQL database dump
--


-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: categoria_docente; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.categoria_docente AS ENUM (
    'Catedrático',
    'Titular',
    'Contratado',
    'Ayudante',
    'Asociado',
    'Postdoc',
    'Doctorando',
    'PSI'
);


--
-- Name: tipo_actividad; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tipo_actividad AS ENUM (
    'GD',
    'GT',
    'GL',
    'GA'
);


--
-- Name: tipo_asignatura; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tipo_asignatura AS ENUM (
    'Básica',
    'Obligatoria',
    'Optativa',
    'TFG',
    'TFM',
    'Máster'
);


--
-- Name: turno_horario; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.turno_horario AS ENUM (
    'Mañana',
    'Tarde',
    'Noche'
);


--
-- Name: normalizar_perfil_psi(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.normalizar_perfil_psi() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF upper(trim(NEW.categoria)) = 'PSI' THEN NEW.es_psi := TRUE; END IF;
  RETURN NEW;
END; $$;


--
-- Name: recalcular_prioridades(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.recalcular_prioridades() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE profesores p
    SET orden_prioridad = ranking.rn
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   ORDER BY cp.peso ASC,
                            p2.fecha_ingreso ASC,
                            p2.apellidos ASC,
                            p2.nombre ASC
               ) AS rn
        FROM profesores p2
        JOIN categoria_pesos cp ON cp.categoria = p2.categoria
    ) ranking
    WHERE p.id = ranking.id;
END;
$$;


--
-- Name: sincronizar_cuenta_docente_psi(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sincronizar_cuenta_docente_psi() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  UPDATE usuarios SET rol=CASE WHEN NEW.es_psi THEN 'psi' ELSE 'profesor' END
  WHERE id=NEW.usuario_id AND rol IN ('psi','profesor');
  RETURN NEW;
END; $$;


--
-- Name: trigger_recalcular_prioridades(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trigger_recalcular_prioridades() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM recalcular_prioridades();
    RETURN NULL;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: actividad_areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.actividad_areas (
    actividad_id integer NOT NULL,
    area_id integer NOT NULL
);


--
-- Name: actividades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.actividades (
    id integer NOT NULL,
    codigo character varying(50) NOT NULL,
    tipo character varying(20) NOT NULL,
    codigo_grupo character varying(50) NOT NULL,
    grupo character varying(100) NOT NULL,
    idioma character varying(50),
    duracion character varying(50) NOT NULL,
    turno character varying(30) NOT NULL,
    horas_asignatura numeric(6,2) NOT NULL,
    horas_actividad numeric(6,2) NOT NULL,
    horas_area numeric(6,2) NOT NULL,
    area_id integer,
    dias character varying(100),
    horario character varying(500),
    nombre_asignatura character varying(255),
    tipo_estudio character varying(20),
    codigo_plan character varying(50),
    nombre_plan character varying(255),
    codigo_centro character varying(50),
    nombre_centro character varying(255),
    ciclo character varying(50),
    curso character varying(50),
    caracter character varying(100),
    actividad_oficial_id character varying(50),
    nombre_actividad character varying(255),
    codigo_grupo_oficial character varying(50),
    horario_confirmado boolean DEFAULT false NOT NULL,
    origen_horario character varying(30) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    curso_academico character varying(20),
    requiere_horario boolean DEFAULT true NOT NULL,
    horario_detallado jsonb DEFAULT '[]'::jsonb NOT NULL,
    fuente_horario character varying(500),
    CONSTRAINT actividades_horario_requerido CHECK (((NOT requiere_horario) OR ((btrim((COALESCE(dias, ''::character varying))::text) <> ''::text) AND (btrim((COALESCE(horario, ''::character varying))::text) <> ''::text)))),
    CONSTRAINT actividades_horas_actividad_check CHECK ((horas_actividad > (0)::numeric)),
    CONSTRAINT actividades_horas_area_check CHECK ((horas_area >= (0)::numeric)),
    CONSTRAINT actividades_horas_asignatura_check CHECK ((horas_asignatura >= (0)::numeric))
);


--
-- Name: actividades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.actividades_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: actividades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.actividades_id_seq OWNED BY public.actividades.id;


--
-- Name: areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.areas (
    id integer NOT NULL,
    codigo character varying(50) NOT NULL,
    nombre character varying(200) NOT NULL,
    departamento_id integer NOT NULL,
    responsable_area_id integer
);


--
-- Name: areas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.areas_id_seq OWNED BY public.areas.id;


--
-- Name: avisos_turno_correo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.avisos_turno_correo (
    id bigint NOT NULL,
    area_id integer NOT NULL,
    profesor_id integer NOT NULL,
    generacion bigint NOT NULL,
    estado text DEFAULT 'PENDIENTE'::text NOT NULL,
    intentos integer DEFAULT 0 NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    enviado_en timestamp with time zone,
    proximo_intento timestamp with time zone DEFAULT now() NOT NULL,
    error text
);


--
-- Name: avisos_turno_correo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.avisos_turno_correo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: avisos_turno_correo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.avisos_turno_correo_id_seq OWNED BY public.avisos_turno_correo.id;


--
-- Name: avisos_turno_estado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.avisos_turno_estado (
    area_id integer NOT NULL,
    firma text NOT NULL,
    generacion bigint DEFAULT 0 NOT NULL
);


--
-- Name: calendario_docente_excepciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calendario_docente_excepciones (
    id bigint NOT NULL,
    curso_academico character varying(20) NOT NULL,
    fecha date NOT NULL,
    tipo character varying(30) NOT NULL,
    nombre character varying(300) NOT NULL,
    bloquea_docencia boolean DEFAULT true NOT NULL,
    fuente character varying(500),
    CONSTRAINT calendario_docente_excepciones_tipo_check CHECK (((tipo)::text = ANY ((ARRAY['FESTIVO_NACIONAL'::character varying, 'FESTIVO_AUTONOMICO'::character varying, 'FESTIVO_LOCAL'::character varying, 'NO_LECTIVO_UAL'::character varying, 'PRESENTACION_UAL'::character varying])::text[])))
);


--
-- Name: calendario_docente_excepciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.calendario_docente_excepciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: calendario_docente_excepciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.calendario_docente_excepciones_id_seq OWNED BY public.calendario_docente_excepciones.id;


--
-- Name: calendario_docente_periodos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calendario_docente_periodos (
    id bigint NOT NULL,
    curso_academico character varying(20) NOT NULL,
    tipo_estudio character varying(30) DEFAULT 'GRADO'::character varying NOT NULL,
    cuatrimestre character varying(10) NOT NULL,
    fecha_inicio date NOT NULL,
    fecha_fin date NOT NULL,
    descripcion character varying(300),
    fuente character varying(500),
    CONSTRAINT calendario_docente_periodos_cuatrimestre_check CHECK (((cuatrimestre)::text = ANY ((ARRAY['PRIMERO'::character varying, 'SEGUNDO'::character varying])::text[]))),
    CONSTRAINT calendario_docente_periodos_fechas_validas CHECK ((fecha_fin >= fecha_inicio))
);


--
-- Name: calendario_docente_periodos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.calendario_docente_periodos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: calendario_docente_periodos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.calendario_docente_periodos_id_seq OWNED BY public.calendario_docente_periodos.id;


--
-- Name: categoria_pesos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categoria_pesos (
    categoria character varying(50) NOT NULL,
    peso integer NOT NULL,
    CONSTRAINT categoria_pesos_peso_check CHECK ((peso >= 1))
);


--
-- Name: departamentos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departamentos (
    id integer NOT NULL,
    codigo character varying(50) NOT NULL,
    nombre character varying(200) NOT NULL,
    responsable_departamento_id integer
);


--
-- Name: departamentos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.departamentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: departamentos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.departamentos_id_seq OWNED BY public.departamentos.id;


--
-- Name: importaciones_catalogo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.importaciones_catalogo (
    id integer NOT NULL,
    huella character varying(64) NOT NULL,
    curso_academico character varying(20) NOT NULL,
    filas_csv integer NOT NULL,
    actividades_creadas integer NOT NULL,
    profesores_creados integer NOT NULL,
    creado_en timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: importaciones_catalogo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.importaciones_catalogo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: importaciones_catalogo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.importaciones_catalogo_id_seq OWNED BY public.importaciones_catalogo.id;


--
-- Name: ordenacion_areas_control; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ordenacion_areas_control (
    area_id integer NOT NULL,
    version integer DEFAULT 0 NOT NULL,
    estado character varying(16) DEFAULT 'ABIERTA'::character varying NOT NULL,
    cerrado_por_usuario_id integer,
    cerrado_en timestamp with time zone,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    iniciada boolean DEFAULT false NOT NULL,
    CONSTRAINT ordenacion_areas_control_estado_check CHECK (((estado)::text = ANY ((ARRAY['ABIERTA'::character varying, 'CERRADA'::character varying])::text[]))),
    CONSTRAINT ordenacion_areas_control_version_check CHECK ((version >= 0))
);


--
-- Name: ordenacion_conflictos_propuestas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ordenacion_conflictos_propuestas (
    id bigint NOT NULL,
    area_id integer NOT NULL,
    profesor_bloqueado_id integer NOT NULL,
    version_base integer NOT NULL,
    estado character varying(16) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    propuesta jsonb NOT NULL,
    creada_por_usuario_id integer,
    creada_en timestamp with time zone DEFAULT now() NOT NULL,
    decidida_por_usuario_id integer,
    decidida_en timestamp with time zone,
    motivo_rechazo text,
    CONSTRAINT ordenacion_conflictos_propuestas_estado_check CHECK (((estado)::text = ANY ((ARRAY['PENDIENTE'::character varying, 'APROBADA'::character varying, 'RECHAZADA'::character varying, 'OBSOLETA'::character varying])::text[]))),
    CONSTRAINT ordenacion_conflictos_propuestas_version_base_check CHECK ((version_base >= 0))
);


--
-- Name: ordenacion_conflictos_propuestas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ordenacion_conflictos_propuestas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ordenacion_conflictos_propuestas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ordenacion_conflictos_propuestas_id_seq OWNED BY public.ordenacion_conflictos_propuestas.id;


--
-- Name: ordenacion_eventos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ordenacion_eventos (
    id bigint NOT NULL,
    area_id integer NOT NULL,
    usuario_id integer,
    tipo character varying(40) NOT NULL,
    detalle jsonb DEFAULT '{}'::jsonb NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ordenacion_eventos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ordenacion_eventos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ordenacion_eventos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ordenacion_eventos_id_seq OWNED BY public.ordenacion_eventos.id;


--
-- Name: ordenacion_revisiones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ordenacion_revisiones (
    id bigint NOT NULL,
    area_id integer NOT NULL,
    profesor_id integer NOT NULL,
    actividad_id integer NOT NULL,
    horas_devuelta numeric(10,2) NOT NULL,
    motivo text NOT NULL,
    devuelta_por_usuario_id integer,
    estado character varying(16) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    creada_en timestamp with time zone DEFAULT now() NOT NULL,
    resuelta_en timestamp with time zone,
    resuelta_por_usuario_id integer,
    CONSTRAINT ordenacion_revisiones_estado_check CHECK (((estado)::text = ANY ((ARRAY['PENDIENTE'::character varying, 'RESUELTA'::character varying])::text[]))),
    CONSTRAINT ordenacion_revisiones_horas_devuelta_check CHECK ((horas_devuelta > (0)::numeric)),
    CONSTRAINT ordenacion_revisiones_motivo_check CHECK ((char_length(TRIM(BOTH FROM motivo)) >= 3))
);


--
-- Name: ordenacion_revisiones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ordenacion_revisiones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ordenacion_revisiones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ordenacion_revisiones_id_seq OWNED BY public.ordenacion_revisiones.id;


--
-- Name: planificacion_docente_sesiones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.planificacion_docente_sesiones (
    id bigint NOT NULL,
    actividad_id integer NOT NULL,
    profesor_id integer NOT NULL,
    reparto_id integer,
    curso_academico character varying(20) NOT NULL,
    fecha date,
    hora_inicio time without time zone,
    hora_fin time without time zone,
    horas numeric(8,2) NOT NULL,
    orden_adjudicacion integer NOT NULL,
    orden_sesion integer NOT NULL,
    estado character varying(30) DEFAULT 'PLANIFICADA'::character varying NOT NULL,
    origen character varying(30) DEFAULT 'AUTOMATICO'::character varying NOT NULL,
    observacion text,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    horas_adjudicadas numeric(8,2),
    es_horario_referencia boolean DEFAULT false NOT NULL,
    CONSTRAINT planificacion_docente_sesiones_estado_check CHECK (((estado)::text = ANY ((ARRAY['PLANIFICADA'::character varying, 'AJUSTE_PENDIENTE'::character varying, 'PENDIENTE_HORARIO'::character varying])::text[]))),
    CONSTRAINT planificacion_docente_sesiones_horas_check CHECK ((horas > (0)::numeric)),
    CONSTRAINT planificacion_docente_sesiones_orden_adjudicacion_check CHECK ((orden_adjudicacion > 0)),
    CONSTRAINT planificacion_docente_sesiones_orden_sesion_check CHECK ((orden_sesion > 0)),
    CONSTRAINT planificacion_docente_sesiones_origen_check CHECK (((origen)::text = ANY ((ARRAY['AUTOMATICO'::character varying, 'MANUAL'::character varying])::text[]))),
    CONSTRAINT planificacion_sesion_coherente CHECK (((((estado)::text = 'PLANIFICADA'::text) AND (fecha IS NOT NULL) AND (hora_inicio IS NOT NULL) AND (hora_fin IS NOT NULL) AND (hora_fin > hora_inicio)) OR (((estado)::text <> 'PLANIFICADA'::text) AND (fecha IS NULL) AND (hora_inicio IS NULL) AND (hora_fin IS NULL))))
);


--
-- Name: planificacion_docente_sesiones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.planificacion_docente_sesiones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: planificacion_docente_sesiones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.planificacion_docente_sesiones_id_seq OWNED BY public.planificacion_docente_sesiones.id;


--
-- Name: profesor_areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profesor_areas (
    profesor_id integer NOT NULL,
    area_id integer NOT NULL,
    horas_objetivo numeric(8,1) DEFAULT 0 NOT NULL
);


--
-- Name: profesor_prioridades_asignaturas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profesor_prioridades_asignaturas (
    profesor_id integer NOT NULL,
    asignatura_codigo character varying(100) NOT NULL,
    prioridad integer NOT NULL,
    CONSTRAINT profesor_prioridades_asignaturas_prioridad_check CHECK ((prioridad > 0))
);


--
-- Name: profesores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profesores (
    id integer NOT NULL,
    usuario_id integer,
    nombre character varying(100) NOT NULL,
    apellidos character varying(200) NOT NULL,
    categoria character varying(50) NOT NULL,
    fecha_ingreso date NOT NULL,
    carga_docente numeric(6,2) NOT NULL,
    area_id integer,
    es_psi boolean DEFAULT false NOT NULL,
    creado_en timestamp without time zone DEFAULT now(),
    rol character varying(50) DEFAULT 'profesor'::character varying,
    identificador_origen character varying(100),
    activo_origen boolean,
    disponibilidad_cuatrimestre character varying(10) DEFAULT 'AMBOS'::character varying NOT NULL,
    CONSTRAINT profesores_carga_docente_check CHECK ((carga_docente > (0)::numeric)),
    CONSTRAINT profesores_disponibilidad_cuatrimestre_check CHECK (((disponibilidad_cuatrimestre)::text = ANY ((ARRAY['PRIMERO'::character varying, 'SEGUNDO'::character varying, 'AMBOS'::character varying])::text[])))
);


--
-- Name: profesores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.profesores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: profesores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.profesores_id_seq OWNED BY public.profesores.id;


--
-- Name: reparto_docente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reparto_docente (
    id integer NOT NULL,
    profesor_id integer NOT NULL,
    actividad_id integer NOT NULL,
    horas_asignadas numeric(6,2) NOT NULL,
    asignado_por_usuario_id integer,
    confirmado boolean DEFAULT true NOT NULL,
    creado_en timestamp without time zone DEFAULT now(),
    codigo_plaza_origen character varying(100),
    id_plaza_origen character varying(100),
    es_profesor_principal boolean DEFAULT false NOT NULL,
    coordinador_origen character varying(255),
    origen_reparto character varying(30) DEFAULT 'MANUAL'::character varying NOT NULL,
    CONSTRAINT reparto_docente_horas_asignadas_check CHECK ((horas_asignadas > (0)::numeric))
);


--
-- Name: reparto_docente_borrador; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reparto_docente_borrador (
    id integer NOT NULL,
    profesor_id integer NOT NULL,
    actividad_id integer NOT NULL,
    horas_asignadas numeric(6,2) NOT NULL,
    creado_por_usuario_id integer,
    creado_en timestamp without time zone DEFAULT now(),
    CONSTRAINT reparto_docente_borrador_horas_asignadas_check CHECK ((horas_asignadas > (0)::numeric))
);


--
-- Name: reparto_docente_borrador_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reparto_docente_borrador_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reparto_docente_borrador_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reparto_docente_borrador_id_seq OWNED BY public.reparto_docente_borrador.id;


--
-- Name: reparto_docente_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reparto_docente_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reparto_docente_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reparto_docente_id_seq OWNED BY public.reparto_docente.id;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    apellidos character varying(200) NOT NULL,
    email character varying(255) NOT NULL,
    password_hash text,
    rol character varying(40) NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    creado_en timestamp without time zone DEFAULT now(),
    CONSTRAINT usuarios_rol_check CHECK (((rol)::text = ANY ((ARRAY['admin'::character varying, 'responsable_departamento'::character varying, 'responsable_area'::character varying, 'profesor'::character varying, 'psi'::character varying])::text[])))
);


--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: actividades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades ALTER COLUMN id SET DEFAULT nextval('public.actividades_id_seq'::regclass);


--
-- Name: areas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas ALTER COLUMN id SET DEFAULT nextval('public.areas_id_seq'::regclass);


--
-- Name: avisos_turno_correo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_turno_correo ALTER COLUMN id SET DEFAULT nextval('public.avisos_turno_correo_id_seq'::regclass);


--
-- Name: calendario_docente_excepciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendario_docente_excepciones ALTER COLUMN id SET DEFAULT nextval('public.calendario_docente_excepciones_id_seq'::regclass);


--
-- Name: calendario_docente_periodos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendario_docente_periodos ALTER COLUMN id SET DEFAULT nextval('public.calendario_docente_periodos_id_seq'::regclass);


--
-- Name: departamentos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departamentos ALTER COLUMN id SET DEFAULT nextval('public.departamentos_id_seq'::regclass);


--
-- Name: importaciones_catalogo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.importaciones_catalogo ALTER COLUMN id SET DEFAULT nextval('public.importaciones_catalogo_id_seq'::regclass);


--
-- Name: ordenacion_conflictos_propuestas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_conflictos_propuestas ALTER COLUMN id SET DEFAULT nextval('public.ordenacion_conflictos_propuestas_id_seq'::regclass);


--
-- Name: ordenacion_eventos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_eventos ALTER COLUMN id SET DEFAULT nextval('public.ordenacion_eventos_id_seq'::regclass);


--
-- Name: ordenacion_revisiones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_revisiones ALTER COLUMN id SET DEFAULT nextval('public.ordenacion_revisiones_id_seq'::regclass);


--
-- Name: planificacion_docente_sesiones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planificacion_docente_sesiones ALTER COLUMN id SET DEFAULT nextval('public.planificacion_docente_sesiones_id_seq'::regclass);


--
-- Name: profesores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesores ALTER COLUMN id SET DEFAULT nextval('public.profesores_id_seq'::regclass);


--
-- Name: reparto_docente id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente ALTER COLUMN id SET DEFAULT nextval('public.reparto_docente_id_seq'::regclass);


--
-- Name: reparto_docente_borrador id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente_borrador ALTER COLUMN id SET DEFAULT nextval('public.reparto_docente_borrador_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Name: actividad_areas actividad_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_areas
    ADD CONSTRAINT actividad_areas_pkey PRIMARY KEY (actividad_id, area_id);


--
-- Name: actividades actividades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades
    ADD CONSTRAINT actividades_pkey PRIMARY KEY (id);


--
-- Name: areas areas_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_codigo_key UNIQUE (codigo);


--
-- Name: areas areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_pkey PRIMARY KEY (id);


--
-- Name: avisos_turno_correo avisos_turno_correo_area_id_generacion_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_turno_correo
    ADD CONSTRAINT avisos_turno_correo_area_id_generacion_key UNIQUE (area_id, generacion);


--
-- Name: avisos_turno_correo avisos_turno_correo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_turno_correo
    ADD CONSTRAINT avisos_turno_correo_pkey PRIMARY KEY (id);


--
-- Name: avisos_turno_estado avisos_turno_estado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_turno_estado
    ADD CONSTRAINT avisos_turno_estado_pkey PRIMARY KEY (area_id);


--
-- Name: calendario_docente_excepciones calendario_docente_excepciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendario_docente_excepciones
    ADD CONSTRAINT calendario_docente_excepciones_pkey PRIMARY KEY (id);


--
-- Name: calendario_docente_periodos calendario_docente_periodos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendario_docente_periodos
    ADD CONSTRAINT calendario_docente_periodos_pkey PRIMARY KEY (id);


--
-- Name: categoria_pesos categoria_pesos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria_pesos
    ADD CONSTRAINT categoria_pesos_pkey PRIMARY KEY (categoria);


--
-- Name: departamentos departamentos_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departamentos
    ADD CONSTRAINT departamentos_codigo_key UNIQUE (codigo);


--
-- Name: departamentos departamentos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departamentos
    ADD CONSTRAINT departamentos_pkey PRIMARY KEY (id);


--
-- Name: importaciones_catalogo importaciones_catalogo_huella_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.importaciones_catalogo
    ADD CONSTRAINT importaciones_catalogo_huella_key UNIQUE (huella);


--
-- Name: importaciones_catalogo importaciones_catalogo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.importaciones_catalogo
    ADD CONSTRAINT importaciones_catalogo_pkey PRIMARY KEY (id);


--
-- Name: ordenacion_areas_control ordenacion_areas_control_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_areas_control
    ADD CONSTRAINT ordenacion_areas_control_pkey PRIMARY KEY (area_id);


--
-- Name: ordenacion_conflictos_propuestas ordenacion_conflictos_propuestas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_conflictos_propuestas
    ADD CONSTRAINT ordenacion_conflictos_propuestas_pkey PRIMARY KEY (id);


--
-- Name: ordenacion_eventos ordenacion_eventos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_eventos
    ADD CONSTRAINT ordenacion_eventos_pkey PRIMARY KEY (id);


--
-- Name: ordenacion_revisiones ordenacion_revisiones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_revisiones
    ADD CONSTRAINT ordenacion_revisiones_pkey PRIMARY KEY (id);


--
-- Name: planificacion_docente_sesiones planificacion_docente_sesiones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planificacion_docente_sesiones
    ADD CONSTRAINT planificacion_docente_sesiones_pkey PRIMARY KEY (id);


--
-- Name: profesor_areas profesor_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesor_areas
    ADD CONSTRAINT profesor_areas_pkey PRIMARY KEY (profesor_id, area_id);


--
-- Name: profesor_prioridades_asignaturas profesor_prioridades_asignaturas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesor_prioridades_asignaturas
    ADD CONSTRAINT profesor_prioridades_asignaturas_pkey PRIMARY KEY (profesor_id, asignatura_codigo);


--
-- Name: profesor_prioridades_asignaturas profesor_prioridades_asignaturas_profesor_id_prioridad_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesor_prioridades_asignaturas
    ADD CONSTRAINT profesor_prioridades_asignaturas_profesor_id_prioridad_key UNIQUE (profesor_id, prioridad);


--
-- Name: profesores profesores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesores
    ADD CONSTRAINT profesores_pkey PRIMARY KEY (id);


--
-- Name: profesores profesores_usuario_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesores
    ADD CONSTRAINT profesores_usuario_id_key UNIQUE (usuario_id);


--
-- Name: reparto_docente_borrador reparto_docente_borrador_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente_borrador
    ADD CONSTRAINT reparto_docente_borrador_pkey PRIMARY KEY (id);


--
-- Name: reparto_docente_borrador reparto_docente_borrador_profesor_id_actividad_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente_borrador
    ADD CONSTRAINT reparto_docente_borrador_profesor_id_actividad_id_key UNIQUE (profesor_id, actividad_id);


--
-- Name: reparto_docente reparto_docente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente
    ADD CONSTRAINT reparto_docente_pkey PRIMARY KEY (id);


--
-- Name: calendario_docente_excepciones uq_calendario_docente_excepcion; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendario_docente_excepciones
    ADD CONSTRAINT uq_calendario_docente_excepcion UNIQUE (curso_academico, fecha, tipo, nombre);


--
-- Name: calendario_docente_periodos uq_calendario_docente_periodo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendario_docente_periodos
    ADD CONSTRAINT uq_calendario_docente_periodo UNIQUE (curso_academico, tipo_estudio, cuatrimestre);


--
-- Name: usuarios usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_email_key UNIQUE (email);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: idx_actividad_areas_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_actividad_areas_area ON public.actividad_areas USING btree (area_id, actividad_id);


--
-- Name: idx_actividades_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_actividades_area ON public.actividades USING btree (area_id);


--
-- Name: idx_actividades_horario_detallado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_actividades_horario_detallado ON public.actividades USING gin (horario_detallado);


--
-- Name: idx_actividades_identidad_area_curso; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_actividades_identidad_area_curso ON public.actividades USING btree (codigo, tipo, codigo_grupo, COALESCE(area_id, '-1'::integer), COALESCE(curso_academico, ''::character varying));


--
-- Name: idx_actividades_identificador_oficial; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_actividades_identificador_oficial ON public.actividades USING btree (actividad_oficial_id, codigo_grupo_oficial);


--
-- Name: idx_areas_departamento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_areas_departamento ON public.areas USING btree (departamento_id);


--
-- Name: idx_borrador_actividad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_borrador_actividad ON public.reparto_docente_borrador USING btree (actividad_id);


--
-- Name: idx_borrador_profesor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_borrador_profesor ON public.reparto_docente_borrador USING btree (profesor_id);


--
-- Name: idx_calendario_docente_excepciones_curso_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_calendario_docente_excepciones_curso_fecha ON public.calendario_docente_excepciones USING btree (curso_academico, fecha);


--
-- Name: idx_conflictos_area_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conflictos_area_fecha ON public.ordenacion_conflictos_propuestas USING btree (area_id, creada_en DESC);


--
-- Name: idx_ordenacion_eventos_area_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ordenacion_eventos_area_fecha ON public.ordenacion_eventos USING btree (area_id, creado_en DESC);


--
-- Name: idx_ordenacion_revisiones_area_pendiente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ordenacion_revisiones_area_pendiente ON public.ordenacion_revisiones USING btree (area_id, creada_en) WHERE ((estado)::text = 'PENDIENTE'::text);


--
-- Name: idx_planificacion_docente_actividad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planificacion_docente_actividad ON public.planificacion_docente_sesiones USING btree (actividad_id, orden_adjudicacion, orden_sesion);


--
-- Name: idx_planificacion_docente_profesor_referencia; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planificacion_docente_profesor_referencia ON public.planificacion_docente_sesiones USING btree (profesor_id, curso_academico, es_horario_referencia);


--
-- Name: idx_planificacion_docente_profesor_semana; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planificacion_docente_profesor_semana ON public.planificacion_docente_sesiones USING btree (profesor_id, curso_academico, fecha, hora_inicio);


--
-- Name: idx_profesor_areas_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profesor_areas_area ON public.profesor_areas USING btree (area_id, profesor_id);


--
-- Name: idx_profesor_areas_cola; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profesor_areas_cola ON public.profesor_areas USING btree (area_id, horas_objetivo, profesor_id);


--
-- Name: idx_profesor_prioridades_profesor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profesor_prioridades_profesor ON public.profesor_prioridades_asignaturas USING btree (profesor_id, prioridad);


--
-- Name: idx_profesores_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profesores_area ON public.profesores USING btree (area_id);


--
-- Name: idx_profesores_categoria; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profesores_categoria ON public.profesores USING btree (categoria);


--
-- Name: idx_profesores_identificador_origen; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_profesores_identificador_origen ON public.profesores USING btree (identificador_origen) WHERE (identificador_origen IS NOT NULL);


--
-- Name: idx_profesores_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profesores_usuario ON public.profesores USING btree (usuario_id);


--
-- Name: idx_reparto_actividad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reparto_actividad ON public.reparto_docente USING btree (actividad_id);


--
-- Name: idx_reparto_docente_actividad_profesor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reparto_docente_actividad_profesor ON public.reparto_docente USING btree (actividad_id, profesor_id);


--
-- Name: idx_reparto_docente_profesor_actividad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reparto_docente_profesor_actividad ON public.reparto_docente USING btree (profesor_id, actividad_id);


--
-- Name: idx_reparto_profesor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reparto_profesor ON public.reparto_docente USING btree (profesor_id);


--
-- Name: uq_conflicto_pendiente_area; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_conflicto_pendiente_area ON public.ordenacion_conflictos_propuestas USING btree (area_id) WHERE ((estado)::text = 'PENDIENTE'::text);


--
-- Name: uq_revision_pendiente_actividad_profesor; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_revision_pendiente_actividad_profesor ON public.ordenacion_revisiones USING btree (area_id, profesor_id, actividad_id) WHERE ((estado)::text = 'PENDIENTE'::text);


--
-- Name: profesores normalizar_perfil_psi; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER normalizar_perfil_psi BEFORE INSERT OR UPDATE ON public.profesores FOR EACH ROW EXECUTE FUNCTION public.normalizar_perfil_psi();


--
-- Name: profesores sincronizar_cuenta_docente_psi; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER sincronizar_cuenta_docente_psi AFTER INSERT OR UPDATE ON public.profesores FOR EACH ROW EXECUTE FUNCTION public.sincronizar_cuenta_docente_psi();


--
-- Name: actividad_areas actividad_areas_actividad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_areas
    ADD CONSTRAINT actividad_areas_actividad_id_fkey FOREIGN KEY (actividad_id) REFERENCES public.actividades(id) ON DELETE CASCADE;


--
-- Name: actividad_areas actividad_areas_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_areas
    ADD CONSTRAINT actividad_areas_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE RESTRICT;


--
-- Name: actividades actividades_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades
    ADD CONSTRAINT actividades_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE SET NULL;


--
-- Name: areas areas_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: areas areas_responsable_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_responsable_area_id_fkey FOREIGN KEY (responsable_area_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: avisos_turno_correo avisos_turno_correo_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_turno_correo
    ADD CONSTRAINT avisos_turno_correo_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE CASCADE;


--
-- Name: avisos_turno_correo avisos_turno_correo_profesor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_turno_correo
    ADD CONSTRAINT avisos_turno_correo_profesor_id_fkey FOREIGN KEY (profesor_id) REFERENCES public.profesores(id) ON DELETE CASCADE;


--
-- Name: avisos_turno_estado avisos_turno_estado_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_turno_estado
    ADD CONSTRAINT avisos_turno_estado_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE CASCADE;


--
-- Name: departamentos departamentos_responsable_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departamentos
    ADD CONSTRAINT departamentos_responsable_departamento_id_fkey FOREIGN KEY (responsable_departamento_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: ordenacion_areas_control ordenacion_areas_control_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_areas_control
    ADD CONSTRAINT ordenacion_areas_control_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE CASCADE;


--
-- Name: ordenacion_areas_control ordenacion_areas_control_cerrado_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_areas_control
    ADD CONSTRAINT ordenacion_areas_control_cerrado_por_usuario_id_fkey FOREIGN KEY (cerrado_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: ordenacion_conflictos_propuestas ordenacion_conflictos_propuestas_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_conflictos_propuestas
    ADD CONSTRAINT ordenacion_conflictos_propuestas_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE CASCADE;


--
-- Name: ordenacion_conflictos_propuestas ordenacion_conflictos_propuestas_creada_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_conflictos_propuestas
    ADD CONSTRAINT ordenacion_conflictos_propuestas_creada_por_usuario_id_fkey FOREIGN KEY (creada_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: ordenacion_conflictos_propuestas ordenacion_conflictos_propuestas_decidida_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_conflictos_propuestas
    ADD CONSTRAINT ordenacion_conflictos_propuestas_decidida_por_usuario_id_fkey FOREIGN KEY (decidida_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: ordenacion_conflictos_propuestas ordenacion_conflictos_propuestas_profesor_bloqueado_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_conflictos_propuestas
    ADD CONSTRAINT ordenacion_conflictos_propuestas_profesor_bloqueado_id_fkey FOREIGN KEY (profesor_bloqueado_id) REFERENCES public.profesores(id) ON DELETE CASCADE;


--
-- Name: ordenacion_eventos ordenacion_eventos_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_eventos
    ADD CONSTRAINT ordenacion_eventos_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE CASCADE;


--
-- Name: ordenacion_eventos ordenacion_eventos_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_eventos
    ADD CONSTRAINT ordenacion_eventos_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: ordenacion_revisiones ordenacion_revisiones_actividad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_revisiones
    ADD CONSTRAINT ordenacion_revisiones_actividad_id_fkey FOREIGN KEY (actividad_id) REFERENCES public.actividades(id) ON DELETE CASCADE;


--
-- Name: ordenacion_revisiones ordenacion_revisiones_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_revisiones
    ADD CONSTRAINT ordenacion_revisiones_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE CASCADE;


--
-- Name: ordenacion_revisiones ordenacion_revisiones_devuelta_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_revisiones
    ADD CONSTRAINT ordenacion_revisiones_devuelta_por_usuario_id_fkey FOREIGN KEY (devuelta_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: ordenacion_revisiones ordenacion_revisiones_profesor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_revisiones
    ADD CONSTRAINT ordenacion_revisiones_profesor_id_fkey FOREIGN KEY (profesor_id) REFERENCES public.profesores(id) ON DELETE CASCADE;


--
-- Name: ordenacion_revisiones ordenacion_revisiones_resuelta_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ordenacion_revisiones
    ADD CONSTRAINT ordenacion_revisiones_resuelta_por_usuario_id_fkey FOREIGN KEY (resuelta_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: planificacion_docente_sesiones planificacion_docente_sesiones_actividad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planificacion_docente_sesiones
    ADD CONSTRAINT planificacion_docente_sesiones_actividad_id_fkey FOREIGN KEY (actividad_id) REFERENCES public.actividades(id) ON DELETE CASCADE;


--
-- Name: planificacion_docente_sesiones planificacion_docente_sesiones_profesor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planificacion_docente_sesiones
    ADD CONSTRAINT planificacion_docente_sesiones_profesor_id_fkey FOREIGN KEY (profesor_id) REFERENCES public.profesores(id) ON DELETE CASCADE;


--
-- Name: planificacion_docente_sesiones planificacion_docente_sesiones_reparto_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planificacion_docente_sesiones
    ADD CONSTRAINT planificacion_docente_sesiones_reparto_id_fkey FOREIGN KEY (reparto_id) REFERENCES public.reparto_docente(id) ON DELETE SET NULL;


--
-- Name: profesor_areas profesor_areas_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesor_areas
    ADD CONSTRAINT profesor_areas_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE RESTRICT;


--
-- Name: profesor_areas profesor_areas_profesor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesor_areas
    ADD CONSTRAINT profesor_areas_profesor_id_fkey FOREIGN KEY (profesor_id) REFERENCES public.profesores(id) ON DELETE CASCADE;


--
-- Name: profesor_prioridades_asignaturas profesor_prioridades_asignaturas_profesor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesor_prioridades_asignaturas
    ADD CONSTRAINT profesor_prioridades_asignaturas_profesor_id_fkey FOREIGN KEY (profesor_id) REFERENCES public.profesores(id) ON DELETE CASCADE;


--
-- Name: profesores profesores_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesores
    ADD CONSTRAINT profesores_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE SET NULL;


--
-- Name: profesores profesores_categoria_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesores
    ADD CONSTRAINT profesores_categoria_fkey FOREIGN KEY (categoria) REFERENCES public.categoria_pesos(categoria);


--
-- Name: profesores profesores_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesores
    ADD CONSTRAINT profesores_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: reparto_docente reparto_docente_actividad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente
    ADD CONSTRAINT reparto_docente_actividad_id_fkey FOREIGN KEY (actividad_id) REFERENCES public.actividades(id) ON DELETE CASCADE;


--
-- Name: reparto_docente reparto_docente_asignado_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente
    ADD CONSTRAINT reparto_docente_asignado_por_usuario_id_fkey FOREIGN KEY (asignado_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: reparto_docente_borrador reparto_docente_borrador_actividad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente_borrador
    ADD CONSTRAINT reparto_docente_borrador_actividad_id_fkey FOREIGN KEY (actividad_id) REFERENCES public.actividades(id) ON DELETE CASCADE;


--
-- Name: reparto_docente_borrador reparto_docente_borrador_creado_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente_borrador
    ADD CONSTRAINT reparto_docente_borrador_creado_por_usuario_id_fkey FOREIGN KEY (creado_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: reparto_docente_borrador reparto_docente_borrador_profesor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente_borrador
    ADD CONSTRAINT reparto_docente_borrador_profesor_id_fkey FOREIGN KEY (profesor_id) REFERENCES public.profesores(id) ON DELETE CASCADE;


--
-- Name: reparto_docente reparto_docente_profesor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reparto_docente
    ADD CONSTRAINT reparto_docente_profesor_id_fkey FOREIGN KEY (profesor_id) REFERENCES public.profesores(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

