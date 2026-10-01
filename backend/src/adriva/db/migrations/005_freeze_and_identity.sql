CREATE OR REPLACE FUNCTION protect_frozen_provenance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid uuid;
BEGIN
 PERFORM 1 FROM project WHERE id=COALESCE(NEW.project_id,OLD.project_id) FOR UPDATE;
 cid := CASE WHEN TG_OP='DELETE' THEN OLD.case_revision_id ELSE NEW.case_revision_id END;
 IF EXISTS(SELECT 1 FROM release_case rc JOIN benchmark_release r ON r.id=rc.release_id WHERE rc.case_revision_id=cid AND r.state='FROZEN') THEN
  RAISE EXCEPTION 'frozen case provenance' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' OR TG_OP='DELETE' THEN RAISE EXCEPTION 'append-only provenance' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION freeze_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.id<>OLD.id OR NEW.project_id<>OLD.project_id THEN
  RAISE EXCEPTION 'immutable project identity' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER run_identity BEFORE UPDATE ON run FOR EACH ROW EXECUTE FUNCTION freeze_identity();
CREATE TRIGGER run_item_identity BEFORE UPDATE ON run_item FOR EACH ROW EXECUTE FUNCTION freeze_identity();
CREATE TRIGGER release_identity BEFORE UPDATE ON benchmark_release FOR EACH ROW EXECUTE FUNCTION freeze_identity();
CREATE TRIGGER immutable_comparison BEFORE UPDATE OR DELETE ON comparison_unit FOR EACH ROW EXECUTE FUNCTION reject_mutation();

-- Annotation records are foundations only: there is deliberately no annotator API yet.
CREATE VIEW v_blind_assignment AS
 SELECT a.project_id,a.id AS assignment_id,a.reviewer_id,a.state,
 c.prompt,c.context,ra.normalized_text AS response_a,rb.normalized_text AS response_b,
 ru.dimensions AS rubric
 FROM assignment a JOIN assignment_mapping m ON m.assignment_id=a.id
 JOIN comparison_unit cu ON cu.id=a.comparison_unit_id JOIN human_study hs ON hs.id=cu.study_id
 JOIN rubric_revision ru ON ru.id=hs.rubric_revision_id
 JOIN response ra ON ra.id=m.a_response_id JOIN response rb ON rb.id=m.b_response_id
 JOIN run_item i ON i.id=ra.run_item_id JOIN case_revision c ON c.id=i.case_revision_id;

CREATE VIEW v_fixture_free_metric_coverage AS SELECT * FROM v_metric_coverage WHERE usage_class<>'FIXTURE';
