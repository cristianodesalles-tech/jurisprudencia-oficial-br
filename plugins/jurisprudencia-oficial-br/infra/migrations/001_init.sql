CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id text PRIMARY KEY,
  court text NOT NULL,
  case_number text NOT NULL,
  document_type text NOT NULL,
  title text NOT NULL,
  full_text text NOT NULL,
  panel text NOT NULL DEFAULT '',
  rapporteur text NOT NULL DEFAULT '',
  judgment_date text NOT NULL DEFAULT '',
  publication_date text NOT NULL DEFAULT '',
  state text NOT NULL DEFAULT '',
  branch text NOT NULL DEFAULT '',
  outcome text NOT NULL DEFAULT '',
  precedent_kind text NOT NULL DEFAULT 'ordinary',
  binding integer NOT NULL DEFAULT 0 CHECK (binding IN (0,1)),
  themes jsonb NOT NULL DEFAULT '[]'::jsonb,
  statutes jsonb NOT NULL DEFAULT '[]'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL CHECK (status IN ('PISTA','LOCALIZADO','CONFIRMADO','VALIDADO','REJEITADO','NÃO VALIDADO')),
  source_id text NOT NULL,
  source_url text NOT NULL,
  retrieved_at timestamptz NOT NULL,
  content_sha256 char(64) NOT NULL,
  source_role text NOT NULL CHECK (source_role IN ('discovery','validation')),
  http_status integer NOT NULL,
  content_type text NOT NULL,
  final_url text NOT NULL,
  fingerprint char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id text PRIMARY KEY,
  document_id text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ordinal integer NOT NULL,
  text text NOT NULL,
  text_sha256 char(64) NOT NULL,
  embedding vector(768),
  search_vector tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', coalesce(text,''))) STORED,
  UNIQUE(document_id, ordinal)
);

CREATE TABLE IF NOT EXISTS source_health (
  source_id text PRIMARY KEY,
  status text NOT NULL,
  checked_at timestamptz NOT NULL,
  http_status integer,
  final_url text,
  error_class text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  id bigserial PRIMARY KEY,
  source_id text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  status text NOT NULL,
  discovered integer NOT NULL DEFAULT 0,
  inserted integer NOT NULL DEFAULT 0,
  rejected integer NOT NULL DEFAULT 0,
  cursor jsonb NOT NULL DEFAULT '{}'::jsonb,
  error text
);

CREATE TABLE IF NOT EXISTS audit_events (
  sequence bigserial PRIMARY KEY,
  at timestamptz NOT NULL DEFAULT now(),
  event text NOT NULL,
  payload jsonb NOT NULL,
  previous_hash char(64) NOT NULL,
  event_hash char(64) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS legal_reviews (
  id bigserial PRIMARY KEY,
  document_id text NOT NULL REFERENCES documents(id),
  reviewer text NOT NULL,
  reviewed_at timestamptz NOT NULL,
  checklist jsonb NOT NULL,
  notes text NOT NULL DEFAULT '',
  resulting_status text NOT NULL CHECK (resulting_status IN ('VALIDADO','NÃO VALIDADO'))
);

CREATE INDEX IF NOT EXISTS idx_documents_court ON documents(court);
CREATE INDEX IF NOT EXISTS idx_documents_case_number ON documents(case_number);
CREATE INDEX IF NOT EXISTS idx_documents_dates ON documents(judgment_date, publication_date);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_precedent ON documents(precedent_kind, binding);
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON chunks USING gin(search_vector);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);
