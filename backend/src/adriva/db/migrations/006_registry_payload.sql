ALTER TABLE case_revision ADD COLUMN registry_payload jsonb NOT NULL DEFAULT '{}';
ALTER TABLE source_record ADD COLUMN item_key text;
ALTER TABLE source_record ADD COLUMN permission_note text;

CREATE FUNCTION parent_in_release() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.state='FROZEN' AND EXISTS(SELECT 1 FROM release_case rc JOIN derivation_event d ON d.child_revision_id=rc.case_revision_id
 WHERE rc.release_id=NEW.id AND NOT EXISTS(SELECT 1 FROM release_case p WHERE p.release_id=NEW.id AND p.case_revision_id=d.parent_revision_id)) THEN
  RAISE EXCEPTION 'transformed parent revision missing from release' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER parent_release_guard BEFORE UPDATE ON benchmark_release FOR EACH ROW EXECUTE FUNCTION parent_in_release();
