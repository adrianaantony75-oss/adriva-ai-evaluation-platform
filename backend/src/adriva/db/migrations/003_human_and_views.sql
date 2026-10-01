CREATE TABLE human_study (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, rubric_revision_id uuid NOT NULL,
 protocol_digest text NOT NULL, sampling_plan jsonb NOT NULL,
 state text NOT NULL CHECK(state IN ('DRAFT','FROZEN','COMPLETED')),
 UNIQUE(id,project_id), FOREIGN KEY(rubric_revision_id,project_id) REFERENCES rubric_revision(id,project_id)
);
CREATE TABLE comparison_unit (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, study_id uuid NOT NULL,
 baseline_response_id uuid NOT NULL, candidate_response_id uuid NOT NULL, family_id uuid NOT NULL,
 sample_probability numeric CHECK(sample_probability>0 AND sample_probability<=1),
 sample_kind text NOT NULL CHECK(sample_kind IN ('RANDOM','DIAGNOSTIC','FIXTURE')),
 UNIQUE(id,project_id), CHECK(baseline_response_id<>candidate_response_id),
 FOREIGN KEY(study_id,project_id) REFERENCES human_study(id,project_id),
 FOREIGN KEY(baseline_response_id,project_id) REFERENCES response(id,project_id),
 FOREIGN KEY(candidate_response_id,project_id) REFERENCES response(id,project_id),
 FOREIGN KEY(family_id,project_id) REFERENCES intent_family(id,project_id),
 CHECK(sample_kind<>'RANDOM' OR sample_probability IS NOT NULL)
);
CREATE TABLE assignment (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, comparison_unit_id uuid NOT NULL,
 reviewer_id uuid NOT NULL REFERENCES user_account,
 state text NOT NULL CHECK(state IN ('ASSIGNED','SUBMITTED','CANCELLED')),
 UNIQUE(id,project_id), UNIQUE(comparison_unit_id,reviewer_id),
 FOREIGN KEY(comparison_unit_id,project_id) REFERENCES comparison_unit(id,project_id)
);
CREATE TABLE assignment_mapping (
 assignment_id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project,
 a_response_id uuid NOT NULL, b_response_id uuid NOT NULL, CHECK(a_response_id<>b_response_id),
 FOREIGN KEY(assignment_id,project_id) REFERENCES assignment(id,project_id),
 FOREIGN KEY(a_response_id,project_id) REFERENCES response(id,project_id),
 FOREIGN KEY(b_response_id,project_id) REFERENCES response(id,project_id)
);
CREATE TABLE judgment (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, assignment_id uuid NOT NULL,
 preference text NOT NULL CHECK(preference IN ('A','B','TIE','CANNOT_JUDGE')),
 rationale text NOT NULL, amendment_of_id uuid, submitted_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,project_id), FOREIGN KEY(assignment_id,project_id) REFERENCES assignment(id,project_id),
 FOREIGN KEY(amendment_of_id,project_id) REFERENCES judgment(id,project_id)
);
CREATE UNIQUE INDEX uq_original_judgment ON judgment(assignment_id) WHERE amendment_of_id IS NULL;
CREATE TABLE dimension_rating (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, judgment_id uuid NOT NULL,
 response_slot text NOT NULL CHECK(response_slot IN ('A','B')), dimension text NOT NULL,
 status text NOT NULL CHECK(status IN ('RATED','NOT_APPLICABLE','CANNOT_JUDGE')),
 ordinal_value integer, evidence jsonb NOT NULL, rationale text NOT NULL,
 UNIQUE(judgment_id,response_slot,dimension), FOREIGN KEY(judgment_id,project_id) REFERENCES judgment(id,project_id),
 CHECK((status='RATED' AND ordinal_value BETWEEN 1 AND 5) OR (status<>'RATED' AND ordinal_value IS NULL)),
 CHECK(dimension IN ('MEANING','NATURALNESS','GRAMMAR','FACTUALITY','INSTRUCTION','CULTURAL_FIT','COMPLETENESS','GROUNDEDNESS'))
);
CREATE TABLE adjudication (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, comparison_unit_id uuid NOT NULL,
 adjudicator_id uuid NOT NULL REFERENCES user_account, resolution jsonb NOT NULL,
 rationale text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(comparison_unit_id,project_id) REFERENCES comparison_unit(id,project_id)
);
CREATE TABLE reviewer_qualification (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, reviewer_id uuid NOT NULL REFERENCES user_account,
 language_profile jsonb NOT NULL, assessment_revision text NOT NULL,
 outcome text NOT NULL CHECK(outcome IN ('QUALIFIED','REVIEW_REQUIRED','NOT_QUALIFIED'))
);
CREATE TABLE failure_label (
 code text NOT NULL, taxonomy_version text NOT NULL, definition text NOT NULL,
 PRIMARY KEY(code,taxonomy_version)
);
INSERT INTO failure_label(code,taxonomy_version,definition) VALUES
 ('MEANING_DRIFT','1','Required proposition or intent altered'),
 ('INSTRUCTION_DRIFT','1','Explicit task constraint not followed'),
 ('HALLUCINATION','1','Unsupported or fabricated assertion under evidence contract'),
 ('FACTUAL_ERROR','1','Claim contradicted by trusted reference'),
 ('ENTITY_PRESERVATION','1','Required identity substituted, lost or mislinked'),
 ('NUMBER_PRESERVATION','1','Required quantity or unit altered'),
 ('OVER_LITERAL_TRANSLATION','1','Literal wording distorts intended function'),
 ('UNNATURAL_LANGUAGE','1','Awkward target-register language'),
 ('GRAMMAR_ERROR','1','Material target-language grammatical issue'),
 ('CODE_SWITCH_FAILURE','1','Switching violates requested mode or coherence'),
 ('TRANSLITERATION_FAILURE','1','Romanization changes meaning or identity'),
 ('CULTURAL_MISINTERPRETATION','1','Context-specific reference misinterpreted'),
 ('OMISSION','1','Required content absent'),
 ('UNSUPPORTED_ADDITION','1','Unpermitted material added'),
 ('FORMAT_FAILURE','1','Output structure constraint violated'),
 ('CONTRADICTION','1','Incompatible assertions'),
 ('INAPPROPRIATE_REFUSAL','1','Answerable allowed task declined');
CREATE TABLE failure_finding (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES project, response_id uuid NOT NULL,
 severity text NOT NULL CHECK(severity IN ('MINOR','MAJOR','CRITICAL')),
 origin_kind text NOT NULL CHECK(origin_kind IN ('DETERMINISTIC','JUDGE','HUMAN')),
 verification_state text NOT NULL CHECK(verification_state IN ('PROPOSED','CONFIRMED','DISPUTED')),
 reviewer_id uuid REFERENCES user_account, evidence jsonb NOT NULL,
 FOREIGN KEY(response_id,project_id) REFERENCES response(id,project_id),
 CHECK(verification_state<>'CONFIRMED' OR reviewer_id IS NOT NULL OR origin_kind='DETERMINISTIC')
);
CREATE TABLE finding_label (
 finding_id uuid NOT NULL REFERENCES failure_finding, code text NOT NULL, taxonomy_version text NOT NULL,
 PRIMARY KEY(finding_id,code,taxonomy_version), FOREIGN KEY(code,taxonomy_version) REFERENCES failure_label(code,taxonomy_version)
);
CREATE INDEX ix_assignment_queue ON assignment(reviewer_id,state);
CREATE INDEX ix_failure_filter ON failure_finding(project_id,verification_state,severity);
CREATE TRIGGER immutable_judgment BEFORE UPDATE OR DELETE ON judgment FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_rating BEFORE UPDATE OR DELETE ON dimension_rating FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_mapping BEFORE UPDATE OR DELETE ON assignment_mapping FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_adjudication BEFORE UPDATE OR DELETE ON adjudication FOR EACH ROW EXECUTE FUNCTION reject_mutation();

CREATE VIEW v_benchmark_coverage AS
 SELECT rc.project_id,rc.release_id,rc.split,f.primary_task,c.input_profile->>'script' AS script,
 c.input_profile->'languages' AS languages,c.usage_class,
 count(*) AS n_cases,count(DISTINCT f.id) AS n_families,count(DISTINCT f.cluster_id) AS n_clusters
 FROM release_case rc JOIN case_revision c ON c.id=rc.case_revision_id
 JOIN case_item i ON i.id=c.case_item_id JOIN intent_family f ON f.id=i.family_id
 GROUP BY rc.project_id,rc.release_id,rc.split,f.primary_task,c.input_profile->>'script',c.input_profile->'languages',c.usage_class;

CREATE VIEW v_run_completion AS
 SELECT r.project_id,r.id AS run_id,r.usage_class,r.state,count(i.id) AS expected_items,
 count(i.id) FILTER(WHERE i.state='SUCCEEDED') AS succeeded,
 count(i.id) FILTER(WHERE i.state='FAILED') AS failed,
 count(i.id) FILTER(WHERE i.state='CANCELLED') AS cancelled,
 count(i.id) FILTER(WHERE i.state='PENDING') AS pending
 FROM run r LEFT JOIN run_item i ON i.run_id=r.id GROUP BY r.project_id,r.id,r.usage_class,r.state;

CREATE VIEW v_metric_coverage AS
 SELECT m.project_id,m.scoring_run_id,m.scorer_revision_id,m.dimension,r.usage_class,
 count(*) AS n_results,count(*) FILTER(WHERE m.status='VALUE') AS n_values,
 count(*) FILTER(WHERE m.status='SCORER_ERROR') AS n_errors,
 count(*) FILTER(WHERE m.status='NOT_APPLICABLE') AS n_not_applicable,
 count(*) FILTER(WHERE m.status='INSUFFICIENT_EVIDENCE') AS n_insufficient
 FROM metric_result m JOIN scoring_run s ON s.id=m.scoring_run_id JOIN run r ON r.id=s.run_id
 GROUP BY m.project_id,m.scoring_run_id,m.scorer_revision_id,m.dimension,r.usage_class;

CREATE VIEW v_annotation_overlap AS
 SELECT cu.project_id,cu.study_id,cu.id AS comparison_unit_id,count(DISTINCT a.reviewer_id) AS n_reviewers
 FROM comparison_unit cu LEFT JOIN assignment a ON a.comparison_unit_id=cu.id
 LEFT JOIN judgment j ON j.assignment_id=a.id AND j.amendment_of_id IS NULL
 WHERE j.id IS NOT NULL GROUP BY cu.project_id,cu.study_id,cu.id;

CREATE VIEW v_provenance_lineage AS
 WITH RECURSIVE lineage(project_id,child_id,ancestor_id,depth,path) AS (
 SELECT project_id,child_revision_id,parent_revision_id,1,ARRAY[child_revision_id,parent_revision_id] FROM derivation_event
 UNION ALL
 SELECT l.project_id,l.child_id,d.parent_revision_id,l.depth+1,l.path||d.parent_revision_id
 FROM lineage l JOIN derivation_event d ON d.child_revision_id=l.ancestor_id
 WHERE NOT d.parent_revision_id=ANY(l.path)
 ) SELECT project_id,child_id,ancestor_id,depth FROM lineage;

-- Long-form paired extract; descriptive only, not an inferential result.
CREATE VIEW v_paired_metric AS
 SELECT a.project_id,sa.run_id AS baseline_run_id,sb.run_id AS candidate_run_id,
 a.scoring_run_id AS baseline_scoring_id,b.scoring_run_id AS candidate_scoring_id,
 ia.case_revision_id,ia.repetition_index,f.id AS family_id,f.cluster_id,
 a.scorer_revision_id,a.dimension,a.value AS baseline_value,b.value AS candidate_value,
 a.status AS baseline_status,b.status AS candidate_status,ra.usage_class
 FROM metric_result a JOIN scoring_run sa ON sa.id=a.scoring_run_id JOIN run ra ON ra.id=sa.run_id
 JOIN response oa ON oa.id=a.response_id JOIN run_item ia ON ia.id=oa.run_item_id
 JOIN metric_result b ON b.project_id=a.project_id AND b.scorer_revision_id=a.scorer_revision_id AND b.dimension=a.dimension
 JOIN scoring_run sb ON sb.id=b.scoring_run_id JOIN run rb ON rb.id=sb.run_id
 JOIN response ob ON ob.id=b.response_id JOIN run_item ib ON ib.id=ob.run_item_id
 JOIN case_revision c ON c.id=ia.case_revision_id JOIN case_item i ON i.id=c.case_item_id JOIN intent_family f ON f.id=i.family_id
 WHERE sa.run_id<>sb.run_id AND ia.case_revision_id=ib.case_revision_id AND ia.repetition_index=ib.repetition_index
 AND ra.release_id=rb.release_id AND ra.protocol_digest=rb.protocol_digest AND sa.protocol_digest=sb.protocol_digest
 AND sa.scorer_set_digest=sb.scorer_set_digest AND ra.usage_class=rb.usage_class;
