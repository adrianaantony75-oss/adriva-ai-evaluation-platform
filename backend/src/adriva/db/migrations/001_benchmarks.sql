CREATE TABLE project (
 id uuid PRIMARY KEY, slug text NOT NULL UNIQUE, name text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), CHECK (length(name)>0)
);
CREATE TABLE user_account (
 id uuid PRIMARY KEY, external_subject text NOT NULL UNIQUE, display_name text NOT NULL,
 active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE membership (
 project_id uuid NOT NULL REFERENCES project, user_id uuid NOT NULL REFERENCES user_account,
 role text NOT NULL CHECK (role IN ('ADMIN','ENGINEER','REVIEWER','ANNOTATION_LEAD','RELEASE_OWNER','READ_ONLY')),
 PRIMARY KEY (project_id,user_id,role)
);
CREATE TABLE dependency_cluster (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, stable_key text NOT NULL,
 reason text NOT NULL, UNIQUE(id,project_id), UNIQUE(project_id,stable_key)
);
CREATE TABLE intent_family (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, cluster_id uuid NOT NULL,
 stable_key text NOT NULL, primary_task text NOT NULL,
 UNIQUE(id,project_id), UNIQUE(project_id,stable_key),
 FOREIGN KEY(cluster_id,project_id) REFERENCES dependency_cluster(id,project_id),
 CHECK(primary_task IN ('GROUNDED_QA','EXTRACTION','TRANSLATION','SUMMARIZATION','INSTRUCTION','REASONING'))
);
CREATE TABLE case_item (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, family_id uuid NOT NULL,
 stable_key text NOT NULL, UNIQUE(id,project_id), UNIQUE(project_id,stable_key),
 FOREIGN KEY(family_id,project_id) REFERENCES intent_family(id,project_id)
);
CREATE TABLE case_revision (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, case_item_id uuid NOT NULL,
 revision_no integer NOT NULL CHECK(revision_no>0), prompt text NOT NULL CHECK(length(prompt)>0),
 context text NOT NULL, input_profile jsonb NOT NULL, output_profile jsonb NOT NULL,
 expected_contract jsonb NOT NULL CHECK(jsonb_typeof(expected_contract)='object'),
 usage_class text NOT NULL CHECK(usage_class IN ('FIXTURE','PILOT','EVALUATION')),
 creation_origin text NOT NULL CHECK(creation_origin IN ('HUMAN_CREATED','SYNTHETIC','PUBLIC_DATASET')),
 digest text NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,project_id), UNIQUE(case_item_id,revision_no),
 FOREIGN KEY(case_item_id,project_id) REFERENCES case_item(id,project_id)
);
CREATE TABLE source_record (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, source_kind text NOT NULL,
 uri text NOT NULL, external_revision text, license text NOT NULL CHECK(length(license)>0),
 sensitivity text NOT NULL DEFAULT 'PUBLIC' CHECK(sensitivity IN ('PUBLIC','INTERNAL','SENSITIVE')),
 UNIQUE(id,project_id)
);
CREATE TABLE case_source (
 project_id uuid NOT NULL REFERENCES project, case_revision_id uuid NOT NULL, source_id uuid NOT NULL,
 role text NOT NULL DEFAULT 'PROVENANCE', PRIMARY KEY(case_revision_id,source_id,role),
 FOREIGN KEY(case_revision_id,project_id) REFERENCES case_revision(id,project_id),
 FOREIGN KEY(source_id,project_id) REFERENCES source_record(id,project_id)
);
CREATE TABLE derivation_event (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, child_revision_id uuid NOT NULL,
 parent_revision_id uuid NOT NULL, operator_revision text NOT NULL, relation text NOT NULL,
 invariant text NOT NULL CHECK(length(invariant)>0), parameters jsonb NOT NULL,
 UNIQUE(child_revision_id), CHECK(child_revision_id<>parent_revision_id),
 CHECK(relation IN ('INVARIANT','DIRECTIONAL')),
 FOREIGN KEY(child_revision_id,project_id) REFERENCES case_revision(id,project_id),
 FOREIGN KEY(parent_revision_id,project_id) REFERENCES case_revision(id,project_id)
);
CREATE TABLE rubric_revision (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, name text NOT NULL,
 version text NOT NULL, dimensions jsonb NOT NULL, digest text NOT NULL,
 UNIQUE(id,project_id), UNIQUE(project_id,name,version)
);
CREATE TABLE case_review (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, case_revision_id uuid NOT NULL,
 reviewer_id uuid NOT NULL REFERENCES user_account, rubric_revision_id uuid NOT NULL,
 review_kind text NOT NULL CHECK(review_kind IN ('CONTENT','TRANSFORMATION')),
 verdict text NOT NULL CHECK(verdict IN ('VERIFIED','REJECTED','REVIEW_REQUIRED')),
 rationale text NOT NULL CHECK(length(rationale)>0), submitted_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(case_revision_id,project_id) REFERENCES case_revision(id,project_id),
 FOREIGN KEY(rubric_revision_id,project_id) REFERENCES rubric_revision(id,project_id)
);
CREATE TABLE benchmark (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, name text NOT NULL,
 UNIQUE(id,project_id), UNIQUE(project_id,name)
);
CREATE TABLE benchmark_release (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, benchmark_id uuid NOT NULL,
 version text NOT NULL CHECK(version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
 state text NOT NULL DEFAULT 'DRAFT' CHECK(state IN ('DRAFT','FROZEN')),
 manifest_digest text, manifest jsonb, schema_version text NOT NULL DEFAULT '1',
 taxonomy_version text NOT NULL DEFAULT '1', published_at timestamptz,
 UNIQUE(id,project_id), UNIQUE(benchmark_id,version),
 FOREIGN KEY(benchmark_id,project_id) REFERENCES benchmark(id,project_id),
 CHECK((state='DRAFT' AND manifest_digest IS NULL AND published_at IS NULL) OR
       (state='FROZEN' AND manifest_digest ~ '^[0-9a-f]{64}$' AND manifest IS NOT NULL AND published_at IS NOT NULL))
);
CREATE TABLE release_case (
 project_id uuid NOT NULL REFERENCES project, release_id uuid NOT NULL, case_revision_id uuid NOT NULL,
 split text NOT NULL CHECK(split IN ('development','calibration','evaluation')),
 weight numeric NOT NULL DEFAULT 1 CHECK(weight>0 AND weight<='1000000'), ordinal integer NOT NULL CHECK(ordinal>=0),
 PRIMARY KEY(release_id,case_revision_id), UNIQUE(release_id,ordinal),
 FOREIGN KEY(release_id,project_id) REFERENCES benchmark_release(id,project_id),
 FOREIGN KEY(case_revision_id,project_id) REFERENCES case_revision(id,project_id)
);
CREATE TABLE quality_issue (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, release_id uuid NOT NULL,
 case_revision_id uuid, rule_revision text NOT NULL, severity text NOT NULL CHECK(severity IN ('MINOR','MAJOR','CRITICAL')),
 state text NOT NULL CHECK(state IN ('OPEN','RESOLVED')), evidence jsonb NOT NULL,
 FOREIGN KEY(release_id,project_id) REFERENCES benchmark_release(id,project_id),
 FOREIGN KEY(case_revision_id,project_id) REFERENCES case_revision(id,project_id)
);
CREATE TABLE audit_event (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, actor_id uuid REFERENCES user_account,
 action text NOT NULL, target_id uuid, metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_case_family ON case_item(family_id);
CREATE INDEX ix_release_split ON release_case(release_id,split);
CREATE INDEX ix_quality_open ON quality_issue(release_id,severity) WHERE state='OPEN';

CREATE FUNCTION reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'append-only evidence cannot be updated or deleted' USING ERRCODE='23514'; END $$;
CREATE TRIGGER immutable_case BEFORE UPDATE OR DELETE ON case_revision FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_source BEFORE UPDATE OR DELETE ON source_record FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_family BEFORE UPDATE OR DELETE ON intent_family FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_cluster BEFORE UPDATE OR DELETE ON dependency_cluster FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_item BEFORE UPDATE OR DELETE ON case_item FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_derivation BEFORE UPDATE OR DELETE ON derivation_event FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_review BEFORE UPDATE OR DELETE ON case_review FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_rubric BEFORE UPDATE OR DELETE ON rubric_revision FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit_event FOR EACH ROW EXECUTE FUNCTION reject_mutation();

CREATE FUNCTION protect_release_membership() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rid uuid; status text;
BEGIN
 rid := CASE WHEN TG_OP='DELETE' THEN OLD.release_id ELSE NEW.release_id END;
 SELECT state INTO status FROM benchmark_release WHERE id=rid FOR UPDATE;
 IF status='FROZEN' THEN RAISE EXCEPTION 'frozen release membership' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND OLD.release_id<>NEW.release_id THEN
  SELECT state INTO status FROM benchmark_release WHERE id=OLD.release_id FOR UPDATE;
  IF status='FROZEN' THEN RAISE EXCEPTION 'frozen source release' USING ERRCODE='23514'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER release_member_guard BEFORE INSERT OR UPDATE OR DELETE ON release_case FOR EACH ROW EXECUTE FUNCTION protect_release_membership();

CREATE FUNCTION protect_release() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.state='FROZEN' THEN RAISE EXCEPTION 'frozen benchmark release' USING ERRCODE='23514'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 IF NEW.state='FROZEN' THEN
  IF NOT EXISTS(SELECT 1 FROM release_case WHERE release_id=NEW.id) THEN
   RAISE EXCEPTION 'empty release' USING ERRCODE='23514'; END IF;
  IF EXISTS(SELECT 1 FROM quality_issue WHERE release_id=NEW.id AND state='OPEN' AND severity='CRITICAL') THEN
   RAISE EXCEPTION 'unresolved quality issues' USING ERRCODE='23514'; END IF;
  IF EXISTS(SELECT f.cluster_id FROM release_case rc JOIN case_revision c ON c.id=rc.case_revision_id
      JOIN case_item i ON i.id=c.case_item_id JOIN intent_family f ON f.id=i.family_id
      WHERE rc.release_id=NEW.id GROUP BY f.cluster_id HAVING count(DISTINCT rc.split)>1) THEN
   RAISE EXCEPTION 'cluster split leakage' USING ERRCODE='23514'; END IF;
  IF EXISTS(SELECT 1 FROM release_case rc JOIN case_revision c ON c.id=rc.case_revision_id
      WHERE rc.release_id=NEW.id AND (NOT EXISTS(SELECT 1 FROM case_source cs WHERE cs.case_revision_id=c.id)
      OR (c.usage_class<>'FIXTURE' AND NOT EXISTS(SELECT 1 FROM case_review r WHERE r.case_revision_id=c.id AND r.review_kind='CONTENT' AND r.verdict='VERIFIED')))) THEN
   RAISE EXCEPTION 'missing provenance or human verification' USING ERRCODE='23514'; END IF;
  IF EXISTS(SELECT 1 FROM release_case rc JOIN case_revision c ON c.id=rc.case_revision_id JOIN derivation_event d ON d.child_revision_id=c.id
      WHERE rc.release_id=NEW.id AND c.usage_class<>'FIXTURE' AND NOT EXISTS(SELECT 1 FROM case_review r WHERE r.case_revision_id=c.id AND r.review_kind='TRANSFORMATION' AND r.verdict='VERIFIED')) THEN
   RAISE EXCEPTION 'unverified transformation' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER release_guard BEFORE UPDATE OR DELETE ON benchmark_release FOR EACH ROW EXECUTE FUNCTION protect_release();

CREATE FUNCTION protect_lineage() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE child_family uuid; parent_family uuid;
BEGIN
 SELECT i.family_id INTO child_family FROM case_revision c JOIN case_item i ON i.id=c.case_item_id WHERE c.id=NEW.child_revision_id;
 SELECT i.family_id INTO parent_family FROM case_revision c JOIN case_item i ON i.id=c.case_item_id WHERE c.id=NEW.parent_revision_id;
 IF child_family IS DISTINCT FROM parent_family THEN RAISE EXCEPTION 'cross-family derivation' USING ERRCODE='23514'; END IF;
 -- Serialize graph insertions per project to prevent concurrent cycles.
 PERFORM 1 FROM project WHERE id=NEW.project_id FOR UPDATE;
 IF EXISTS(WITH RECURSIVE ancestors(id) AS (
  SELECT NEW.parent_revision_id UNION SELECT d.parent_revision_id FROM derivation_event d JOIN ancestors a ON a.id=d.child_revision_id
 ) SELECT 1 FROM ancestors WHERE id=NEW.child_revision_id) THEN
  RAISE EXCEPTION 'derivation cycle' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM release_case rc JOIN benchmark_release br ON br.id=rc.release_id WHERE rc.case_revision_id=NEW.child_revision_id AND br.state='FROZEN') THEN
  RAISE EXCEPTION 'cannot change frozen lineage' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER lineage_guard BEFORE INSERT ON derivation_event FOR EACH ROW EXECUTE FUNCTION protect_lineage();
