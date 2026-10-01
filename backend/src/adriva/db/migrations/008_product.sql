ALTER TABLE scoring_run ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
CREATE TABLE worker_heartbeat (
 owner text PRIMARY KEY, last_seen timestamptz NOT NULL DEFAULT now(), state text NOT NULL
);
ALTER TABLE judgment ADD COLUMN data_origin text NOT NULL DEFAULT 'LEGACY_UNSPECIFIED'
 CHECK(data_origin IN ('ACTUAL_HUMAN','TEST_FIXTURE','LEGACY_UNSPECIFIED'));
CREATE INDEX ix_scoring_latest ON scoring_run(run_id,created_at DESC);
CREATE INDEX ix_run_project_created ON run(project_id,created_at DESC);
CREATE INDEX ix_failure_response ON failure_finding(response_id);
