-- Local identities are self-attested; this enforces distinct records, not qualifications.
CREATE FUNCTION require_review_quorum() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.state='FROZEN' AND EXISTS(
  SELECT 1 FROM release_case rc JOIN case_revision c ON c.id=rc.case_revision_id
  WHERE rc.release_id=NEW.id AND c.usage_class<>'FIXTURE' AND (
   (SELECT count(DISTINCT reviewer_id) FROM case_review v WHERE v.case_revision_id=c.id AND v.review_kind='CONTENT' AND v.verdict='VERIFIED')<2
   OR (EXISTS(SELECT 1 FROM derivation_event d WHERE d.child_revision_id=c.id)
       AND (SELECT count(DISTINCT reviewer_id) FROM case_review v WHERE v.case_revision_id=c.id AND v.review_kind='TRANSFORMATION' AND v.verdict='VERIFIED')<2)
  )
 ) THEN RAISE EXCEPTION 'two distinct reviewers required for content and transformations' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER review_quorum BEFORE UPDATE ON benchmark_release FOR EACH ROW EXECUTE FUNCTION require_review_quorum();

CREATE VIEW v_case_review_readiness AS
SELECT c.id,c.project_id,
 (SELECT count(DISTINCT reviewer_id) FROM case_review v WHERE v.case_revision_id=c.id AND v.review_kind='CONTENT' AND v.verdict='VERIFIED') AS content_reviewers,
 (SELECT count(DISTINCT reviewer_id) FROM case_review v WHERE v.case_revision_id=c.id AND v.review_kind='TRANSFORMATION' AND v.verdict='VERIFIED') AS transformation_reviewers,
 ((SELECT count(DISTINCT reviewer_id) FROM case_review v WHERE v.case_revision_id=c.id AND v.review_kind='CONTENT' AND v.verdict='VERIFIED')>=2
 AND NOT EXISTS(SELECT 1 FROM case_review v WHERE v.case_revision_id=c.id AND v.verdict<>'VERIFIED')
 AND (NOT EXISTS(SELECT 1 FROM derivation_event d WHERE d.child_revision_id=c.id)
 OR (SELECT count(DISTINCT reviewer_id) FROM case_review v WHERE v.case_revision_id=c.id AND v.review_kind='TRANSFORMATION' AND v.verdict='VERIFIED')>=2)) AS ready
FROM case_revision c;
