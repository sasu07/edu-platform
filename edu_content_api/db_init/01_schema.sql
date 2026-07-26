--
-- PostgreSQL database dump
--

\restrict NTFIEwA8tkONdzknRPJvCrTYc8a3mRHdz70Kg7S3gXjtJrmZmk7KPvVzaqgDg78

-- Dumped from database version 17.10 (2947584)
-- Dumped by pg_dump version 17.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: asset_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.asset_type_enum AS ENUM (
    'figure',
    'image',
    'diagram',
    'graph',
    'table'
);


--
-- Name: exam_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.exam_type_enum AS ENUM (
    'EN',
    'BAC',
    'bacalaureat',
    'evaluare_nationala',
    'simulare',
    'olimpiada',
    'alta'
);


--
-- Name: exercise_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.exercise_status_enum AS ENUM (
    'DRAFT',
    'REVIEW',
    'READY',
    'ARCHIVED'
);


--
-- Name: extraction_method_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.extraction_method_enum AS ENUM (
    'pdf-text',
    'ocr',
    'manual',
    'pix2text',
    'mathpix',
    'other',
    'MANUAL'
);


--
-- Name: item_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.item_type_enum AS ENUM (
    'grila',
    'short',
    'open',
    'subiect_1',
    'subiect_2',
    'subiect_3',
    'problema',
    'exercitiu'
);


--
-- Name: segment_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.segment_status_enum AS ENUM (
    'EXTRACTED',
    'CLEANED',
    'LINKED',
    'PROCESSED',
    'FAILED'
);


--
-- Name: source_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.source_type_enum AS ENUM (
    'pdf',
    'oficial',
    'culegere'
);


--
-- Name: subject_part_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.subject_part_enum AS ENUM (
    'I',
    'II',
    'III',
    'algebra',
    'geometrie',
    'analiza',
    'trigonometrie',
    'variante'
);


--
-- Name: update_variants_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_variants_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
                    BEGIN
                        NEW.updated_at = CURRENT_TIMESTAMP;
                        RETURN NEW;
                    END;
                    $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    exercise_id uuid NOT NULL,
    type public.asset_type_enum NOT NULL,
    file_path character varying(512) NOT NULL,
    caption text,
    latex_ref character varying(255),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    actor_user_id uuid,
    actor_role character varying(20),
    action character varying(80) NOT NULL,
    method character varying(8),
    path text,
    resource_type character varying(40),
    resource_id character varying(64),
    ip character varying(64),
    user_agent text,
    status integer,
    details jsonb
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: class_group_memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.class_group_memberships (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    class_id uuid NOT NULL,
    student_id uuid NOT NULL,
    pseudonym character varying(80),
    is_anonymous boolean DEFAULT false NOT NULL,
    joined_at timestamp without time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: class_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.class_groups (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    teacher_id uuid NOT NULL,
    name character varying(120) NOT NULL,
    class_code character varying(16) NOT NULL,
    allow_anonymous boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: diagnostic_exercises; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.diagnostic_exercises (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    test_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    subiect_num integer,
    topic_key character varying(100),
    topic_label character varying(200),
    user_answer text,
    is_correct boolean,
    answered_at timestamp without time zone,
    options jsonb,
    correct_option_index integer,
    selected_option integer
);


--
-- Name: diagnostic_tests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.diagnostic_tests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    total_exercises integer DEFAULT 0 NOT NULL,
    correct_count integer DEFAULT 0 NOT NULL,
    score_pct integer DEFAULT 0 NOT NULL,
    weak_topics jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    completed_at timestamp without time zone,
    solution_file_path text
);


--
-- Name: exam_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exam_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    rules jsonb NOT NULL,
    scoring_rules jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: exercise_generation_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exercise_generation_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: exercise_hints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exercise_hints (
    exercise_id uuid NOT NULL,
    hints jsonb NOT NULL,
    source character varying(20) DEFAULT 'ai'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: exercise_review_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exercise_review_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    student_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    source_reason character varying(30) DEFAULT 'failed'::character varying NOT NULL,
    fail_count integer DEFAULT 0 NOT NULL,
    revisit_count integer DEFAULT 0 NOT NULL,
    first_flagged_at timestamp without time zone DEFAULT now() NOT NULL,
    last_flagged_at timestamp without time zone DEFAULT now() NOT NULL,
    resolved_at timestamp without time zone
);


--
-- Name: exercise_source_segments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exercise_source_segments (
    exercise_id uuid NOT NULL,
    source_segment_id uuid NOT NULL,
    role character varying(50)
);


--
-- Name: exercise_submissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exercise_submissions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    self_eval character varying(20) DEFAULT 'complete'::character varying NOT NULL,
    photo_path character varying(512),
    photo_uploaded_at timestamp without time zone,
    teacher_status character varying(20) DEFAULT NULL::character varying,
    reviewed_by uuid,
    reviewed_at timestamp without time zone,
    teacher_note text,
    xp_self_eval integer DEFAULT 0 NOT NULL,
    xp_photo integer DEFAULT 0 NOT NULL,
    xp_teacher integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    teacher_file_path character varying(512),
    assigned_teacher_id uuid
);


--
-- Name: exercise_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exercise_tags (
    exercise_id uuid NOT NULL,
    tag_id uuid NOT NULL,
    weight real DEFAULT 1.0 NOT NULL,
    created_by character varying(50) NOT NULL,
    confidence real,
    created_by_user_id uuid
);


--
-- Name: exercises; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exercises (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    exam_type public.exam_type_enum NOT NULL,
    profile character varying(50),
    subject_part public.subject_part_enum,
    item_type public.item_type_enum,
    statement_latex text NOT NULL,
    statement_text text,
    answer_latex text,
    solution_latex text,
    scoring_guide_latex text,
    scoring_guide_text text,
    difficulty smallint,
    estimated_time_sec integer,
    points integer,
    metadata jsonb,
    status public.exercise_status_enum DEFAULT 'DRAFT'::public.exercise_status_enum NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id uuid,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    answer_numeric_value double precision,
    answer_numeric_expression text,
    CONSTRAINT exercises_difficulty_check CHECK (((difficulty >= 1) AND (difficulty <= 10)))
);


--
-- Name: help_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.help_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    student_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    flag_type character varying(50) NOT NULL,
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    notes text,
    assigned_teacher_id uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    scheduled_at timestamp with time zone,
    zoom_link character varying(512),
    scheduled_by uuid
);


--
-- Name: help_responses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.help_responses (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    request_id uuid NOT NULL,
    teacher_id uuid NOT NULL,
    content_text text,
    video_path character varying(512),
    zoom_link character varying(512),
    scheduled_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: learning_path_nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.learning_path_nodes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    path_id uuid NOT NULL,
    topic_key character varying(100) NOT NULL,
    topic_label character varying(200) NOT NULL,
    subiect_num integer NOT NULL,
    priority integer DEFAULT 3 NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    exercises_seen integer DEFAULT 0 NOT NULL,
    exercises_correct integer DEFAULT 0 NOT NULL,
    target_exercises integer DEFAULT 8 NOT NULL,
    score_pct integer DEFAULT 0 NOT NULL,
    diagnostic_score_pct integer,
    sort_order integer DEFAULT 0 NOT NULL
);


--
-- Name: learning_paths; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.learning_paths (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    diagnostic_test_id uuid,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    total_nodes integer DEFAULT 0 NOT NULL,
    completed_nodes integer DEFAULT 0 NOT NULL,
    generated_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    ai_plan jsonb,
    ai_plan_text text
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    type character varying(50) NOT NULL,
    title character varying(255) NOT NULL,
    body text,
    is_read boolean DEFAULT false NOT NULL,
    related_id uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: parent_student; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parent_student (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    parent_id uuid NOT NULL,
    student_id uuid NOT NULL,
    linked_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    filename character varying(255) NOT NULL,
    applied_at timestamp with time zone DEFAULT now()
);


--
-- Name: segment_regions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.segment_regions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_segment_id uuid NOT NULL,
    page_number integer NOT NULL,
    bbox jsonb NOT NULL
);


--
-- Name: source_segments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_segments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_id uuid NOT NULL,
    page_start integer NOT NULL,
    page_end integer NOT NULL,
    raw_extraction text,
    checksum character varying(64),
    status public.segment_status_enum DEFAULT 'EXTRACTED'::public.segment_status_enum NOT NULL,
    extraction_method public.extraction_method_enum NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sources (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    type public.source_type_enum NOT NULL,
    year integer,
    session character varying(50),
    url_file_path character varying(512),
    notes text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    profile character varying(100),
    url_barem_path character varying(512)
);


--
-- Name: spaced_repetition_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.spaced_repetition_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    interval_days integer DEFAULT 1 NOT NULL,
    repetitions integer DEFAULT 0 NOT NULL,
    ease_factor double precision DEFAULT 2.5 NOT NULL,
    next_review_date date DEFAULT CURRENT_DATE NOT NULL,
    last_reviewed_at timestamp without time zone
);


--
-- Name: student_badges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student_badges (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    badge_key character varying(100) NOT NULL,
    earned_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: student_gamification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student_gamification (
    user_id uuid NOT NULL,
    xp_total integer DEFAULT 0 NOT NULL,
    streak_current integer DEFAULT 0 NOT NULL,
    streak_max integer DEFAULT 0 NOT NULL,
    last_active_date date,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: student_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student_progress (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    student_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    completed boolean DEFAULT false NOT NULL,
    last_seen_at timestamp without time zone DEFAULT now() NOT NULL,
    completed_at timestamp without time zone
);


--
-- Name: study_plan_days; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.study_plan_days (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    plan_date date NOT NULL,
    session_type character varying(20) DEFAULT 'test_scurt'::character varying NOT NULL,
    filters jsonb DEFAULT '{}'::jsonb NOT NULL,
    note text,
    created_by character varying(20) DEFAULT 'student'::character varying NOT NULL,
    teacher_id uuid,
    session_id uuid,
    completed boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: study_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.study_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    session_type character varying(20) DEFAULT 'test_scurt'::character varying NOT NULL,
    filters jsonb DEFAULT '{}'::jsonb NOT NULL,
    exercise_set_id uuid,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    started_at timestamp without time zone DEFAULT now() NOT NULL,
    completed_at timestamp without time zone,
    duration_sec integer,
    exercises_total integer DEFAULT 0 NOT NULL,
    exercises_completed integer DEFAULT 0 NOT NULL,
    avg_difficulty numeric(4,2),
    xp_gained integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subscriptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    plan_type character varying(50) DEFAULT 'free'::character varying NOT NULL,
    status character varying(50) DEFAULT 'active'::character varying NOT NULL,
    expires_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tags (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    namespace character varying(100) NOT NULL,
    key character varying(100) NOT NULL,
    label character varying(255) NOT NULL,
    parent_id uuid,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: user_exercise_set_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_exercise_set_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    set_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    sort_order integer DEFAULT 0
);


--
-- Name: user_exercise_sets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_exercise_sets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    name character varying(255),
    linked_plan character varying(50),
    filters jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_seen_exercises; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_seen_exercises (
    user_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255) NOT NULL,
    role character varying(50) DEFAULT 'student'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: variant_exercises; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.variant_exercises (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    variant_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    order_index integer NOT NULL,
    section_name character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: variant_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.variant_items (
    variant_id uuid NOT NULL,
    "position" character varying(50) NOT NULL,
    exercise_id uuid NOT NULL
);


--
-- Name: variants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.variants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    exam_type character varying(50) NOT NULL,
    profile character varying(50),
    year integer,
    session character varying(50),
    total_points integer,
    duration_minutes integer,
    instructions text,
    status character varying(20) DEFAULT 'DRAFT'::character varying,
    created_by_user_id uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    fingerprint character varying(64),
    created_by_user_id_fk uuid
);


--
-- Name: weekly_class_challenges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weekly_class_challenges (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    class_id uuid NOT NULL,
    title character varying(160) NOT NULL,
    description text,
    target_count integer DEFAULT 1 NOT NULL,
    filters jsonb DEFAULT '{}'::jsonb NOT NULL,
    week_start date NOT NULL,
    week_end date NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: xp_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.xp_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    xp_gained integer NOT NULL,
    reason character varying(100) NOT NULL,
    reference_id uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: assets assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: class_group_memberships class_group_memberships_class_id_student_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_group_memberships
    ADD CONSTRAINT class_group_memberships_class_id_student_id_key UNIQUE (class_id, student_id);


--
-- Name: class_group_memberships class_group_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_group_memberships
    ADD CONSTRAINT class_group_memberships_pkey PRIMARY KEY (id);


--
-- Name: class_groups class_groups_class_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_groups
    ADD CONSTRAINT class_groups_class_code_key UNIQUE (class_code);


--
-- Name: class_groups class_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_groups
    ADD CONSTRAINT class_groups_pkey PRIMARY KEY (id);


--
-- Name: diagnostic_exercises diagnostic_exercises_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnostic_exercises
    ADD CONSTRAINT diagnostic_exercises_pkey PRIMARY KEY (id);


--
-- Name: diagnostic_exercises diagnostic_exercises_test_id_exercise_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnostic_exercises
    ADD CONSTRAINT diagnostic_exercises_test_id_exercise_id_key UNIQUE (test_id, exercise_id);


--
-- Name: diagnostic_tests diagnostic_tests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnostic_tests
    ADD CONSTRAINT diagnostic_tests_pkey PRIMARY KEY (id);


--
-- Name: exam_templates exam_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exam_templates
    ADD CONSTRAINT exam_templates_pkey PRIMARY KEY (id);


--
-- Name: exercise_generation_logs exercise_generation_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_generation_logs
    ADD CONSTRAINT exercise_generation_logs_pkey PRIMARY KEY (id);


--
-- Name: exercise_hints exercise_hints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_hints
    ADD CONSTRAINT exercise_hints_pkey PRIMARY KEY (exercise_id);


--
-- Name: exercise_review_items exercise_review_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_review_items
    ADD CONSTRAINT exercise_review_items_pkey PRIMARY KEY (id);


--
-- Name: exercise_review_items exercise_review_items_student_id_exercise_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_review_items
    ADD CONSTRAINT exercise_review_items_student_id_exercise_id_key UNIQUE (student_id, exercise_id);


--
-- Name: exercise_source_segments exercise_source_segments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_source_segments
    ADD CONSTRAINT exercise_source_segments_pkey PRIMARY KEY (exercise_id, source_segment_id);


--
-- Name: exercise_submissions exercise_submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_submissions
    ADD CONSTRAINT exercise_submissions_pkey PRIMARY KEY (id);


--
-- Name: exercise_submissions exercise_submissions_user_id_exercise_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_submissions
    ADD CONSTRAINT exercise_submissions_user_id_exercise_id_key UNIQUE (user_id, exercise_id);


--
-- Name: exercise_tags exercise_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_tags
    ADD CONSTRAINT exercise_tags_pkey PRIMARY KEY (exercise_id, tag_id);


--
-- Name: exercises exercises_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercises
    ADD CONSTRAINT exercises_pkey PRIMARY KEY (id);


--
-- Name: help_requests help_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.help_requests
    ADD CONSTRAINT help_requests_pkey PRIMARY KEY (id);


--
-- Name: help_responses help_responses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.help_responses
    ADD CONSTRAINT help_responses_pkey PRIMARY KEY (id);


--
-- Name: learning_path_nodes learning_path_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.learning_path_nodes
    ADD CONSTRAINT learning_path_nodes_pkey PRIMARY KEY (id);


--
-- Name: learning_paths learning_paths_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.learning_paths
    ADD CONSTRAINT learning_paths_pkey PRIMARY KEY (id);


--
-- Name: learning_paths learning_paths_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.learning_paths
    ADD CONSTRAINT learning_paths_user_id_key UNIQUE (user_id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: parent_student parent_student_parent_id_student_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_student
    ADD CONSTRAINT parent_student_parent_id_student_id_key UNIQUE (parent_id, student_id);


--
-- Name: parent_student parent_student_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_student
    ADD CONSTRAINT parent_student_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (filename);


--
-- Name: segment_regions segment_regions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segment_regions
    ADD CONSTRAINT segment_regions_pkey PRIMARY KEY (id);


--
-- Name: segment_regions segment_regions_source_segment_id_page_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segment_regions
    ADD CONSTRAINT segment_regions_source_segment_id_page_number_key UNIQUE (source_segment_id, page_number);


--
-- Name: source_segments source_segments_checksum_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_segments
    ADD CONSTRAINT source_segments_checksum_key UNIQUE (checksum);


--
-- Name: source_segments source_segments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_segments
    ADD CONSTRAINT source_segments_pkey PRIMARY KEY (id);


--
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (id);


--
-- Name: spaced_repetition_items spaced_repetition_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spaced_repetition_items
    ADD CONSTRAINT spaced_repetition_items_pkey PRIMARY KEY (id);


--
-- Name: spaced_repetition_items spaced_repetition_items_user_id_exercise_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spaced_repetition_items
    ADD CONSTRAINT spaced_repetition_items_user_id_exercise_id_key UNIQUE (user_id, exercise_id);


--
-- Name: student_badges student_badges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_badges
    ADD CONSTRAINT student_badges_pkey PRIMARY KEY (id);


--
-- Name: student_badges student_badges_user_id_badge_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_badges
    ADD CONSTRAINT student_badges_user_id_badge_key_key UNIQUE (user_id, badge_key);


--
-- Name: student_gamification student_gamification_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_gamification
    ADD CONSTRAINT student_gamification_pkey PRIMARY KEY (user_id);


--
-- Name: student_progress student_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_progress
    ADD CONSTRAINT student_progress_pkey PRIMARY KEY (id);


--
-- Name: student_progress student_progress_student_id_exercise_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_progress
    ADD CONSTRAINT student_progress_student_id_exercise_id_key UNIQUE (student_id, exercise_id);


--
-- Name: study_plan_days study_plan_days_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_plan_days
    ADD CONSTRAINT study_plan_days_pkey PRIMARY KEY (id);


--
-- Name: study_sessions study_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_sessions
    ADD CONSTRAINT study_sessions_pkey PRIMARY KEY (id);


--
-- Name: subscriptions subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (id);


--
-- Name: tags tags_namespace_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_namespace_key_key UNIQUE (namespace, key);


--
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);


--
-- Name: user_exercise_set_items user_exercise_set_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_exercise_set_items
    ADD CONSTRAINT user_exercise_set_items_pkey PRIMARY KEY (id);


--
-- Name: user_exercise_sets user_exercise_sets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_exercise_sets
    ADD CONSTRAINT user_exercise_sets_pkey PRIMARY KEY (id);


--
-- Name: user_seen_exercises user_seen_exercises_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_seen_exercises
    ADD CONSTRAINT user_seen_exercises_pkey PRIMARY KEY (user_id, exercise_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: variant_exercises variant_exercises_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variant_exercises
    ADD CONSTRAINT variant_exercises_pkey PRIMARY KEY (id);


--
-- Name: variant_exercises variant_exercises_variant_id_exercise_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variant_exercises
    ADD CONSTRAINT variant_exercises_variant_id_exercise_id_key UNIQUE (variant_id, exercise_id);


--
-- Name: variant_exercises variant_exercises_variant_id_order_index_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variant_exercises
    ADD CONSTRAINT variant_exercises_variant_id_order_index_key UNIQUE (variant_id, order_index);


--
-- Name: variant_items variant_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variant_items
    ADD CONSTRAINT variant_items_pkey PRIMARY KEY (variant_id, "position");


--
-- Name: variants variants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variants
    ADD CONSTRAINT variants_pkey PRIMARY KEY (id);


--
-- Name: weekly_class_challenges weekly_class_challenges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_class_challenges
    ADD CONSTRAINT weekly_class_challenges_pkey PRIMARY KEY (id);


--
-- Name: xp_log xp_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.xp_log
    ADD CONSTRAINT xp_log_pkey PRIMARY KEY (id);


--
-- Name: idx_assets_exercise_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assets_exercise_id ON public.assets USING btree (exercise_id);


--
-- Name: idx_audit_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_action ON public.audit_log USING btree (action, created_at DESC);


--
-- Name: idx_audit_actor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_actor ON public.audit_log USING btree (actor_user_id, created_at DESC);


--
-- Name: idx_audit_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_created ON public.audit_log USING btree (created_at DESC);


--
-- Name: idx_audit_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_status ON public.audit_log USING btree (status, created_at DESC);


--
-- Name: idx_class_group_memberships_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_class_group_memberships_class ON public.class_group_memberships USING btree (class_id);


--
-- Name: idx_class_group_memberships_student; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_class_group_memberships_student ON public.class_group_memberships USING btree (student_id);


--
-- Name: idx_class_groups_teacher; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_class_groups_teacher ON public.class_groups USING btree (teacher_id);


--
-- Name: idx_diag_ex_test; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_diag_ex_test ON public.diagnostic_exercises USING btree (test_id);


--
-- Name: idx_diagnostic_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_diagnostic_user ON public.diagnostic_tests USING btree (user_id, created_at DESC);


--
-- Name: idx_ex_set_items_set; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ex_set_items_set ON public.user_exercise_set_items USING btree (set_id, sort_order);


--
-- Name: idx_ex_sets_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ex_sets_user ON public.user_exercise_sets USING btree (user_id, created_at DESC);


--
-- Name: idx_exercise_tags_exercise; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_exercise_tags_exercise ON public.exercise_tags USING btree (exercise_id);


--
-- Name: idx_exercises_answer_numeric_value; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_exercises_answer_numeric_value ON public.exercises USING btree (answer_numeric_value) WHERE (answer_numeric_value IS NOT NULL);


--
-- Name: idx_exercises_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_exercises_created_at ON public.exercises USING btree (created_at DESC);


--
-- Name: idx_exercises_difficulty; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_exercises_difficulty ON public.exercises USING btree (difficulty);


--
-- Name: idx_exercises_exam_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_exercises_exam_type ON public.exercises USING btree (exam_type);


--
-- Name: idx_exercises_metadata_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_exercises_metadata_gin ON public.exercises USING gin (metadata jsonb_path_ops);


--
-- Name: idx_exercises_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_exercises_status ON public.exercises USING btree (status);


--
-- Name: idx_exgen_logs_user_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_exgen_logs_user_month ON public.exercise_generation_logs USING btree (user_id, created_at);


--
-- Name: idx_help_requests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_help_requests_status ON public.help_requests USING btree (status);


--
-- Name: idx_help_requests_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_help_requests_student_id ON public.help_requests USING btree (student_id);


--
-- Name: idx_help_requests_teacher_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_help_requests_teacher_id ON public.help_requests USING btree (assigned_teacher_id);


--
-- Name: idx_help_responses_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_help_responses_request_id ON public.help_responses USING btree (request_id);


--
-- Name: idx_lpn_path; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lpn_path ON public.learning_path_nodes USING btree (path_id, sort_order);


--
-- Name: idx_notifications_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_unread ON public.notifications USING btree (user_id, is_read) WHERE (is_read = false);


--
-- Name: idx_notifications_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_user_id ON public.notifications USING btree (user_id);


--
-- Name: idx_parent_student_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parent_student_parent ON public.parent_student USING btree (parent_id);


--
-- Name: idx_parent_student_student; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parent_student_student ON public.parent_student USING btree (student_id);


--
-- Name: idx_review_items_last_flagged; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_items_last_flagged ON public.exercise_review_items USING btree (last_flagged_at);


--
-- Name: idx_review_items_student_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_items_student_status ON public.exercise_review_items USING btree (student_id, status);


--
-- Name: idx_seen_ex_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_seen_ex_user ON public.user_seen_exercises USING btree (user_id);


--
-- Name: idx_segment_regions_segment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_segment_regions_segment_id ON public.segment_regions USING btree (source_segment_id);


--
-- Name: idx_source_segments_source_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_source_segments_source_id ON public.source_segments USING btree (source_id);


--
-- Name: idx_sr_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sr_user_date ON public.spaced_repetition_items USING btree (user_id, next_review_date);


--
-- Name: idx_student_badges_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_student_badges_user ON public.student_badges USING btree (user_id);


--
-- Name: idx_student_progress_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_student_progress_student_id ON public.student_progress USING btree (student_id);


--
-- Name: idx_study_plan_teacher; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_study_plan_teacher ON public.study_plan_days USING btree (teacher_id);


--
-- Name: idx_study_plan_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_study_plan_user_date ON public.study_plan_days USING btree (user_id, plan_date);


--
-- Name: idx_study_sessions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_study_sessions_status ON public.study_sessions USING btree (status);


--
-- Name: idx_study_sessions_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_study_sessions_user ON public.study_sessions USING btree (user_id);


--
-- Name: idx_submissions_assigned; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_assigned ON public.exercise_submissions USING btree (assigned_teacher_id);


--
-- Name: idx_submissions_exercise; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_exercise ON public.exercise_submissions USING btree (exercise_id);


--
-- Name: idx_submissions_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_pending ON public.exercise_submissions USING btree (user_id, teacher_status);


--
-- Name: idx_submissions_teacher_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_teacher_status ON public.exercise_submissions USING btree (teacher_status);


--
-- Name: idx_submissions_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_user ON public.exercise_submissions USING btree (user_id);


--
-- Name: idx_subscriptions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_subscriptions_user_id ON public.subscriptions USING btree (user_id);


--
-- Name: idx_tags_ns_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tags_ns_key ON public.tags USING btree (namespace, key);


--
-- Name: idx_tags_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tags_parent_id ON public.tags USING btree (parent_id);


--
-- Name: idx_variant_exercises_exercise_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variant_exercises_exercise_id ON public.variant_exercises USING btree (exercise_id);


--
-- Name: idx_variant_exercises_variant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variant_exercises_variant_id ON public.variant_exercises USING btree (variant_id);


--
-- Name: idx_variant_items_exercise_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variant_items_exercise_id ON public.variant_items USING btree (exercise_id);


--
-- Name: idx_variants_exam_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variants_exam_type ON public.variants USING btree (exam_type);


--
-- Name: idx_variants_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variants_status ON public.variants USING btree (status);


--
-- Name: idx_variants_user_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_variants_user_fingerprint ON public.variants USING btree (created_by_user_id_fk, fingerprint) WHERE ((fingerprint IS NOT NULL) AND (created_by_user_id_fk IS NOT NULL));


--
-- Name: idx_variants_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variants_year ON public.variants USING btree (year);


--
-- Name: idx_weekly_class_challenges_class_week; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weekly_class_challenges_class_week ON public.weekly_class_challenges USING btree (class_id, week_start);


--
-- Name: idx_xp_log_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_xp_log_user ON public.xp_log USING btree (user_id);


--
-- Name: variants trigger_update_variants_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_update_variants_updated_at BEFORE UPDATE ON public.variants FOR EACH ROW EXECUTE FUNCTION public.update_variants_updated_at();


--
-- Name: assets assets_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: class_group_memberships class_group_memberships_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_group_memberships
    ADD CONSTRAINT class_group_memberships_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.class_groups(id) ON DELETE CASCADE;


--
-- Name: class_group_memberships class_group_memberships_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_group_memberships
    ADD CONSTRAINT class_group_memberships_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: class_groups class_groups_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_groups
    ADD CONSTRAINT class_groups_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: diagnostic_exercises diagnostic_exercises_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnostic_exercises
    ADD CONSTRAINT diagnostic_exercises_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: diagnostic_exercises diagnostic_exercises_test_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnostic_exercises
    ADD CONSTRAINT diagnostic_exercises_test_id_fkey FOREIGN KEY (test_id) REFERENCES public.diagnostic_tests(id) ON DELETE CASCADE;


--
-- Name: diagnostic_tests diagnostic_tests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnostic_tests
    ADD CONSTRAINT diagnostic_tests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: exercise_hints exercise_hints_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_hints
    ADD CONSTRAINT exercise_hints_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: exercise_review_items exercise_review_items_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_review_items
    ADD CONSTRAINT exercise_review_items_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: exercise_review_items exercise_review_items_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_review_items
    ADD CONSTRAINT exercise_review_items_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: exercise_source_segments exercise_source_segments_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_source_segments
    ADD CONSTRAINT exercise_source_segments_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: exercise_source_segments exercise_source_segments_source_segment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_source_segments
    ADD CONSTRAINT exercise_source_segments_source_segment_id_fkey FOREIGN KEY (source_segment_id) REFERENCES public.source_segments(id) ON DELETE CASCADE;


--
-- Name: exercise_submissions exercise_submissions_assigned_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_submissions
    ADD CONSTRAINT exercise_submissions_assigned_teacher_id_fkey FOREIGN KEY (assigned_teacher_id) REFERENCES public.users(id);


--
-- Name: exercise_submissions exercise_submissions_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_submissions
    ADD CONSTRAINT exercise_submissions_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: exercise_submissions exercise_submissions_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_submissions
    ADD CONSTRAINT exercise_submissions_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: exercise_submissions exercise_submissions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_submissions
    ADD CONSTRAINT exercise_submissions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: exercise_tags exercise_tags_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_tags
    ADD CONSTRAINT exercise_tags_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: exercise_tags exercise_tags_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exercise_tags
    ADD CONSTRAINT exercise_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id) ON DELETE CASCADE;


--
-- Name: help_requests help_requests_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.help_requests
    ADD CONSTRAINT help_requests_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: help_requests help_requests_scheduled_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.help_requests
    ADD CONSTRAINT help_requests_scheduled_by_fkey FOREIGN KEY (scheduled_by) REFERENCES public.users(id);


--
-- Name: help_responses help_responses_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.help_responses
    ADD CONSTRAINT help_responses_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.help_requests(id) ON DELETE CASCADE;


--
-- Name: learning_path_nodes learning_path_nodes_path_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.learning_path_nodes
    ADD CONSTRAINT learning_path_nodes_path_id_fkey FOREIGN KEY (path_id) REFERENCES public.learning_paths(id) ON DELETE CASCADE;


--
-- Name: learning_paths learning_paths_diagnostic_test_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.learning_paths
    ADD CONSTRAINT learning_paths_diagnostic_test_id_fkey FOREIGN KEY (diagnostic_test_id) REFERENCES public.diagnostic_tests(id);


--
-- Name: learning_paths learning_paths_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.learning_paths
    ADD CONSTRAINT learning_paths_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: parent_student parent_student_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_student
    ADD CONSTRAINT parent_student_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: parent_student parent_student_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_student
    ADD CONSTRAINT parent_student_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: segment_regions segment_regions_source_segment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segment_regions
    ADD CONSTRAINT segment_regions_source_segment_id_fkey FOREIGN KEY (source_segment_id) REFERENCES public.source_segments(id) ON DELETE CASCADE;


--
-- Name: source_segments source_segments_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_segments
    ADD CONSTRAINT source_segments_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id) ON DELETE CASCADE;


--
-- Name: spaced_repetition_items spaced_repetition_items_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spaced_repetition_items
    ADD CONSTRAINT spaced_repetition_items_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: spaced_repetition_items spaced_repetition_items_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spaced_repetition_items
    ADD CONSTRAINT spaced_repetition_items_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: student_badges student_badges_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_badges
    ADD CONSTRAINT student_badges_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: student_gamification student_gamification_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_gamification
    ADD CONSTRAINT student_gamification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: student_progress student_progress_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_progress
    ADD CONSTRAINT student_progress_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: study_plan_days study_plan_days_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_plan_days
    ADD CONSTRAINT study_plan_days_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.study_sessions(id) ON DELETE SET NULL;


--
-- Name: study_plan_days study_plan_days_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_plan_days
    ADD CONSTRAINT study_plan_days_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: study_plan_days study_plan_days_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_plan_days
    ADD CONSTRAINT study_plan_days_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: study_sessions study_sessions_exercise_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_sessions
    ADD CONSTRAINT study_sessions_exercise_set_id_fkey FOREIGN KEY (exercise_set_id) REFERENCES public.user_exercise_sets(id) ON DELETE SET NULL;


--
-- Name: study_sessions study_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_sessions
    ADD CONSTRAINT study_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: tags tags_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.tags(id) ON DELETE CASCADE;


--
-- Name: user_exercise_set_items user_exercise_set_items_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_exercise_set_items
    ADD CONSTRAINT user_exercise_set_items_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: user_exercise_set_items user_exercise_set_items_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_exercise_set_items
    ADD CONSTRAINT user_exercise_set_items_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.user_exercise_sets(id) ON DELETE CASCADE;


--
-- Name: user_exercise_sets user_exercise_sets_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_exercise_sets
    ADD CONSTRAINT user_exercise_sets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_seen_exercises user_seen_exercises_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_seen_exercises
    ADD CONSTRAINT user_seen_exercises_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: user_seen_exercises user_seen_exercises_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_seen_exercises
    ADD CONSTRAINT user_seen_exercises_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: variant_exercises variant_exercises_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variant_exercises
    ADD CONSTRAINT variant_exercises_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE;


--
-- Name: variant_exercises variant_exercises_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variant_exercises
    ADD CONSTRAINT variant_exercises_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.variants(id) ON DELETE CASCADE;


--
-- Name: variant_items variant_items_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variant_items
    ADD CONSTRAINT variant_items_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE RESTRICT;


--
-- Name: weekly_class_challenges weekly_class_challenges_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_class_challenges
    ADD CONSTRAINT weekly_class_challenges_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.class_groups(id) ON DELETE CASCADE;


--
-- Name: weekly_class_challenges weekly_class_challenges_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_class_challenges
    ADD CONSTRAINT weekly_class_challenges_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: xp_log xp_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.xp_log
    ADD CONSTRAINT xp_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict NTFIEwA8tkONdzknRPJvCrTYc8a3mRHdz70Kg7S3gXjtJrmZmk7KPvVzaqgDg78

--
-- PostgreSQL database dump
--

\restrict hVFFpjRBka3v1HavNCizKdurcgq1Wtmlt7ULiKeMnVM7rQcU5zKHFRLSfkPuMRB

-- Dumped from database version 17.10 (2947584)
-- Dumped by pg_dump version 17.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.schema_migrations (filename, applied_at) FROM stdin;
001_auth_subscriptions_help.sql	2026-03-28 21:23:12.551542+00
002_school_teacher_variants.sql	2026-03-28 21:23:13.65078+00
003_generation_limits.sql	2026-03-28 21:23:14.426533+00
004_exercise_sets.sql	2026-03-29 20:53:11.12827+00
005_sources_profile_barem.sql	2026-03-30 19:34:49.007877+00
006_parent_student.sql	2026-04-04 18:26:49.015636+00
007_gamification.sql	2026-04-04 20:23:21.785118+00
008_exercise_submissions.sql	2026-04-05 11:31:57.563683+00
009_submission_teacher_file.sql	2026-04-05 15:03:59.289477+00
010_study_sessions.sql	2026-04-05 18:41:09.041473+00
011_liga_bac.sql	2026-04-15 18:54:54.315278+00
012_review_journal.sql	2026-04-15 19:20:47.358988+00
013_numeric_answers.sql	2026-04-15 20:49:56.009681+00
011_teacher_approval_completion.sql	2026-05-30 11:10:32.846582+00
014_learning_path.sql	2026-06-07 18:43:47.123675+00
015_diagnostic_mcq.sql	2026-07-07 20:41:28.847182+00
016_exercise_hints.sql	2026-07-08 16:44:18.983881+00
017_audit_log.sql	2026-07-26 15:07:54.830768+00
\.


--
-- PostgreSQL database dump complete
--

\unrestrict hVFFpjRBka3v1HavNCizKdurcgq1Wtmlt7ULiKeMnVM7rQcU5zKHFRLSfkPuMRB

