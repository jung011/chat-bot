-- 관계형 DB 스키마 (§04 §4). 기존 로컬 Postgres 컨테이너에 적용한다.
--   적용: psql / 또는 scripts/init_db.py (idempotent — IF NOT EXISTS)

-- companies — 테넌트 (레지스트리는 configs/tenants.yaml 가 단일 소스, 운영 전환 시 동기화)
CREATE TABLE IF NOT EXISTS companies (
    company_id     varchar PRIMARY KEY,
    name           varchar NOT NULL,
    faq_server_url varchar,
    faq_vector_db  varchar,
    faq_threshold  float DEFAULT 0.85,
    status         varchar NOT NULL DEFAULT 'active',
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- admins — 업체 담당자 계정(고객은 비회원이라 없음)
CREATE TABLE IF NOT EXISTS admins (
    admin_id   varchar PRIMARY KEY,
    company_id varchar NOT NULL REFERENCES companies(company_id),
    role       varchar NOT NULL DEFAULT 'admin',
    created_at timestamptz NOT NULL DEFAULT now()
);

-- sessions — 대화 세션 (비회원)
CREATE TABLE IF NOT EXISTS sessions (
    session_id varchar PRIMARY KEY,
    company_id varchar NOT NULL,
    anon_id    varchar,
    title      varchar,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sessions_company_updated ON sessions (company_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_company_anon ON sessions (company_id, anon_id);

-- messages — 메시지
CREATE TABLE IF NOT EXISTS messages (
    message_id varchar PRIMARY KEY,
    session_id varchar NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    company_id varchar NOT NULL,
    role       varchar NOT NULL,
    content    text NOT NULL,
    route      varchar,
    sources    jsonb,
    usage      jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_session_created ON messages (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_company_route ON messages (company_id, route);

-- message_feedback — 피드백
CREATE TABLE IF NOT EXISTS message_feedback (
    id         bigserial PRIMARY KEY,
    message_id varchar NOT NULL,
    company_id varchar NOT NULL,
    rating     varchar NOT NULL,
    reason     text,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- faq_sources — FAQ 원본/적재 이력
CREATE TABLE IF NOT EXISTS faq_sources (
    id         bigserial PRIMARY KEY,
    company_id varchar NOT NULL,
    question   text NOT NULL,
    answer     text NOT NULL,
    status     varchar NOT NULL DEFAULT 'pending',
    vector_id  varchar,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_faq_sources_company_status ON faq_sources (company_id, status);

-- query_logs — 질문 로그 (자동완성 log 소스/분석)
CREATE TABLE IF NOT EXISTS query_logs (
    id         bigserial PRIMARY KEY,
    company_id varchar NOT NULL,
    anon_id    varchar,
    raw_query  text NOT NULL,
    route      varchar,
    matched    bool NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_query_logs_company_created ON query_logs (company_id, created_at);
CREATE INDEX IF NOT EXISTS idx_query_logs_company_matched ON query_logs (company_id, matched);

-- index_jobs — 인덱싱 작업
CREATE TABLE IF NOT EXISTS index_jobs (
    job_id      varchar PRIMARY KEY,
    company_id  varchar NOT NULL,
    type        varchar NOT NULL,
    scope       varchar NOT NULL,
    status      varchar NOT NULL DEFAULT 'queued',
    stats       jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
