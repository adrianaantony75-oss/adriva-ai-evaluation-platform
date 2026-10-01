CREATE FUNCTION protect_frozen_provenance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid uuid;
BEGIN
 cid := CASE WHEN TG_OP='DELETE' THEN OLD.case_revision_id ELSE NEW.case_revision_id END;
 IF EXISTS(SELECT 1 FROM release_case rc JOIN benchmark_release r ON r.id=rc.release_id WHERE rc.case_revision_id=cid AND r.state='FROZEN') THEN
  RAISE EXCEPTION 'frozen case provenance' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' OR TG_OP='DELETE' THEN RAISE EXCEPTION 'append-only provenance' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER case_source_guard BEFORE INSERT OR UPDATE OR DELETE ON case_source FOR EACH ROW EXECUTE FUNCTION protect_frozen_provenance();

ALTER TABLE metric_result ADD CONSTRAINT finite_metric CHECK(value IS NULL OR (value<>'Infinity'::numeric AND value<>'-Infinity'::numeric));
ALTER TABLE dimension_rating ADD CONSTRAINT rated_value_required CHECK(status<>'RATED' OR ordinal_value IS NOT NULL);
CREATE FUNCTION validate_scoring_target() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM scoring_run s JOIN run_item i ON i.run_id=s.run_id JOIN response r ON r.run_item_id=i.id WHERE s.id=NEW.scoring_run_id AND r.id=NEW.response_id) THEN
  RAISE EXCEPTION 'response outside scoring run' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER score_target_guard BEFORE INSERT ON metric_result FOR EACH ROW EXECUTE FUNCTION validate_scoring_target();

CREATE FUNCTION validate_comparison_unit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM response a JOIN run_item ia ON ia.id=a.run_item_id JOIN run ra ON ra.id=ia.run_id
 JOIN response b ON b.id=NEW.candidate_response_id JOIN run_item ib ON ib.id=b.run_item_id JOIN run rb ON rb.id=ib.run_id
 JOIN case_revision c ON c.id=ia.case_revision_id JOIN case_item i ON i.id=c.case_item_id
 WHERE a.id=NEW.baseline_response_id AND ia.case_revision_id=ib.case_revision_id AND ia.repetition_index=ib.repetition_index
 AND ra.id<>rb.id AND ra.release_id=rb.release_id AND ra.protocol_digest=rb.protocol_digest AND i.family_id=NEW.family_id) THEN
  RAISE EXCEPTION 'unmatched comparison responses' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER comparison_guard BEFORE INSERT ON comparison_unit FOR EACH ROW EXECUTE FUNCTION validate_comparison_unit();

CREATE FUNCTION validate_assignment_mapping() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM assignment a JOIN comparison_unit u ON u.id=a.comparison_unit_id WHERE a.id=NEW.assignment_id AND
 ((u.baseline_response_id=NEW.a_response_id AND u.candidate_response_id=NEW.b_response_id) OR
  (u.baseline_response_id=NEW.b_response_id AND u.candidate_response_id=NEW.a_response_id))) THEN
  RAISE EXCEPTION 'mapping differs from comparison pair' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER mapping_guard BEFORE INSERT ON assignment_mapping FOR EACH ROW EXECUTE FUNCTION validate_assignment_mapping();

CREATE FUNCTION validate_amendment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.amendment_of_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM judgment WHERE id=NEW.amendment_of_id AND assignment_id=NEW.assignment_id) THEN
  RAISE EXCEPTION 'amendment must belong to same assignment' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER amendment_guard BEFORE INSERT ON judgment FOR EACH ROW EXECUTE FUNCTION validate_amendment();
