CREATE TABLE model_configuration (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, provider text NOT NULL,
 requested_model text NOT NULL, model_version text NOT NULL, endpoint_ref text,
 credential_ref text, parameters jsonb NOT NULL, capabilities jsonb NOT NULL,
 usage_class text NOT NULL CHECK(usage_class IN ('FIXTURE','REAL')),
 digest text NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'), UNIQUE(id,project_id), UNIQUE(project_id,digest)
);
CREATE TABLE run (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, release_id uuid NOT NULL,
 model_config_id uuid NOT NULL, protocol_digest text NOT NULL CHECK(protocol_digest ~ '^[0-9a-f]{64}$'),
 state text NOT NULL CHECK(state IN ('QUEUED','RUNNING','COMPLETED','PARTIAL','FAILED','CANCELLED')),
 usage_class text NOT NULL CHECK(usage_class IN ('FIXTURE','PILOT','EVALUATION')),
 repetitions integer NOT NULL CHECK(repetitions BETWEEN 1 AND 10),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(id,project_id),
 FOREIGN KEY(release_id,project_id) REFERENCES benchmark_release(id,project_id),
 FOREIGN KEY(model_config_id,project_id) REFERENCES model_configuration(id,project_id)
);
CREATE TABLE run_item (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, run_id uuid NOT NULL,
 case_revision_id uuid NOT NULL, repetition_index integer NOT NULL CHECK(repetition_index>=0),
 request_digest text NOT NULL, state text NOT NULL CHECK(state IN ('PENDING','SUCCEEDED','FAILED','CANCELLED')),
 UNIQUE(id,project_id), UNIQUE(run_id,case_revision_id,repetition_index),
 FOREIGN KEY(run_id,project_id) REFERENCES run(id,project_id),
 FOREIGN KEY(case_revision_id,project_id) REFERENCES case_revision(id,project_id)
);
CREATE TABLE execution_attempt (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, run_item_id uuid NOT NULL,
 attempt_no integer NOT NULL CHECK(attempt_no>0), lease_token uuid NOT NULL,
 started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
 outcome text NOT NULL CHECK(outcome IN ('RUNNING','SUCCEEDED','FAILED','STALE')),
 error_class text, provider_request_id text, returned_model text, usage jsonb,
 estimated_cost numeric CHECK(estimated_cost>=0), cost_basis text,
 UNIQUE(id,project_id), UNIQUE(id,run_item_id,project_id), UNIQUE(run_item_id,attempt_no),
 FOREIGN KEY(run_item_id,project_id) REFERENCES run_item(id,project_id)
);
CREATE TABLE artifact (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, content_hash text NOT NULL,
 storage_key text NOT NULL, size_bytes bigint NOT NULL CHECK(size_bytes>=0), media_type text NOT NULL,
 UNIQUE(id,project_id), UNIQUE(project_id,content_hash)
);
CREATE TABLE response (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, run_item_id uuid NOT NULL UNIQUE,
 attempt_id uuid NOT NULL, raw_artifact_id uuid NOT NULL, normalized_text text NOT NULL,
 finish_reason text NOT NULL, digest text NOT NULL, selected_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,project_id),
 FOREIGN KEY(run_item_id,project_id) REFERENCES run_item(id,project_id),
 FOREIGN KEY(attempt_id,run_item_id,project_id) REFERENCES execution_attempt(id,run_item_id,project_id),
 FOREIGN KEY(raw_artifact_id,project_id) REFERENCES artifact(id,project_id)
);
CREATE TABLE job (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, run_item_id uuid NOT NULL UNIQUE,
 state text NOT NULL CHECK(state IN ('PENDING','LEASED','SUCCEEDED','FAILED','CANCELLED')),
 available_at timestamptz NOT NULL DEFAULT now(), lease_owner text, lease_token uuid,
 lease_until timestamptz, attempt_count integer NOT NULL DEFAULT 0 CHECK(attempt_count>=0),
 max_attempts integer NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 10),
 FOREIGN KEY(run_item_id,project_id) REFERENCES run_item(id,project_id),
 CHECK((state='LEASED' AND lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR state<>'LEASED')
);
CREATE TABLE scorer_revision (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, name text NOT NULL,
 version text NOT NULL, code_digest text NOT NULL, config jsonb NOT NULL, direction text NOT NULL CHECK(direction IN ('HIGHER','LOWER')),
 UNIQUE(id,project_id), UNIQUE(project_id,name,version)
);
CREATE TABLE scoring_run (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, run_id uuid NOT NULL,
 scorer_set_digest text NOT NULL, protocol_digest text NOT NULL,
 state text NOT NULL CHECK(state IN ('RUNNING','COMPLETED','FAILED')),
 UNIQUE(id,project_id), FOREIGN KEY(run_id,project_id) REFERENCES run(id,project_id)
);
CREATE TABLE metric_result (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, scoring_run_id uuid NOT NULL,
 response_id uuid NOT NULL, scorer_revision_id uuid NOT NULL, dimension text NOT NULL,
 status text NOT NULL CHECK(status IN ('VALUE','NOT_APPLICABLE','INSUFFICIENT_EVIDENCE','SCORER_ERROR')),
 value numeric, unit text NOT NULL, evidence jsonb NOT NULL, failure_reason text,
 UNIQUE(scoring_run_id,response_id,scorer_revision_id,dimension),
 FOREIGN KEY(scoring_run_id,project_id) REFERENCES scoring_run(id,project_id),
 FOREIGN KEY(response_id,project_id) REFERENCES response(id,project_id),
 FOREIGN KEY(scorer_revision_id,project_id) REFERENCES scorer_revision(id,project_id),
 CHECK((status='VALUE' AND value IS NOT NULL AND value<>'NaN'::numeric) OR (status<>'VALUE' AND value IS NULL))
);
CREATE INDEX ix_run_item_state ON run_item(run_id,state);
CREATE INDEX ix_attempt_item ON execution_attempt(run_item_id,attempt_no);
CREATE INDEX ix_job_available ON job(available_at,id) WHERE state IN ('PENDING','LEASED');
CREATE INDEX ix_metric_slice ON metric_result(scoring_run_id,scorer_revision_id,response_id);
CREATE TRIGGER immutable_model BEFORE UPDATE OR DELETE ON model_configuration FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_response BEFORE UPDATE OR DELETE ON response FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_metric BEFORE UPDATE OR DELETE ON metric_result FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_scorer BEFORE UPDATE OR DELETE ON scorer_revision FOR EACH ROW EXECUTE FUNCTION reject_mutation();

CREATE FUNCTION validate_run_item() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rid uuid; reps integer;
BEGIN
 SELECT release_id,repetitions INTO rid,reps FROM run WHERE id=NEW.run_id;
 IF NOT EXISTS(SELECT 1 FROM release_case WHERE release_id=rid AND case_revision_id=NEW.case_revision_id) OR NEW.repetition_index>=reps THEN
  RAISE EXCEPTION 'case or repetition outside run manifest' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND (NEW.run_id<>OLD.run_id OR NEW.case_revision_id<>OLD.case_revision_id OR NEW.request_digest<>OLD.request_digest OR NEW.repetition_index<>OLD.repetition_index) THEN
  RAISE EXCEPTION 'immutable run item identity' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER run_item_guard BEFORE INSERT OR UPDATE ON run_item FOR EACH ROW EXECUTE FUNCTION validate_run_item();

CREATE FUNCTION validate_run() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE release_state text;
BEGIN
 SELECT state INTO release_state FROM benchmark_release WHERE id=NEW.release_id;
 IF release_state IS DISTINCT FROM 'FROZEN' THEN RAISE EXCEPTION 'run requires frozen release' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND (NEW.release_id<>OLD.release_id OR NEW.model_config_id<>OLD.model_config_id OR NEW.protocol_digest<>OLD.protocol_digest OR NEW.repetitions<>OLD.repetitions OR NEW.usage_class<>OLD.usage_class) THEN
  RAISE EXCEPTION 'immutable run configuration' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER run_guard BEFORE INSERT OR UPDATE ON run FOR EACH ROW EXECUTE FUNCTION validate_run();
