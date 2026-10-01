-- Conservative foundation policy: a negative content/transformation review blocks freeze.
-- Resolution requires a new case revision; no silent overwrite or invented adjudication.
CREATE FUNCTION veto_negative_review() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.state='FROZEN' AND EXISTS(SELECT 1 FROM release_case rc JOIN case_revision c ON c.id=rc.case_revision_id
 JOIN case_review r ON r.case_revision_id=c.id WHERE rc.release_id=NEW.id AND c.usage_class<>'FIXTURE'
 AND r.verdict IN ('REJECTED','REVIEW_REQUIRED')) THEN
  RAISE EXCEPTION 'negative human review requires a revised case' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER review_veto BEFORE UPDATE ON benchmark_release FOR EACH ROW EXECUTE FUNCTION veto_negative_review();
