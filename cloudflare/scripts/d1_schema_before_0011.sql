-- 迁移 0011 之前的正式库结构（只含结构，不含数据），由 extract_schema.py 生成。
CREATE TABLE achievement (
	id INTEGER NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	level INTEGER, 
	description VARCHAR(500), 
	icon VARCHAR(500), 
	trigger_action VARCHAR(50) NOT NULL, 
	trigger_count INTEGER NOT NULL, 
	reward_stars INTEGER, 
	is_preset BOOLEAN, 
	is_active BOOLEAN, 
	deleted BOOLEAN, 
	created_at TIMESTAMP, 
	CONSTRAINT achievement_pkey PRIMARY KEY (id), 
	CONSTRAINT uix_achievement_code_level UNIQUE (code, level)
);
CREATE TABLE achievement_config (
	id INTEGER NOT NULL, 
	achievement_id INTEGER, 
	min_words INTEGER, 
	min_accuracy INTEGER, 
	created_at TIMESTAMP, 
	updated_at TIMESTAMP, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT achievement_config_pkey PRIMARY KEY (id), 
	CONSTRAINT achievement_config_achievement_id_key UNIQUE (achievement_id), 
	CONSTRAINT achievement_config_achievement_id_fkey FOREIGN KEY(achievement_id) REFERENCES achievement (id)
);
CREATE TABLE achievement_progress (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	achievement_id INTEGER NOT NULL, 
	current_count INTEGER, 
	is_unlocked BOOLEAN, 
	unlocked_at TIMESTAMP, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT achievement_progress_pkey PRIMARY KEY (id), 
	CONSTRAINT achievement_progress_achievement_id_fkey FOREIGN KEY(achievement_id) REFERENCES achievement (id), 
	CONSTRAINT uix_user_achievement UNIQUE (user_id, achievement_id)
);
CREATE TABLE error_book (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	subject_id INTEGER NOT NULL, 
	description TEXT, 
	cover_image VARCHAR(500), 
	original_images TEXT, 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP, 
	updated_at TIMESTAMP, 
	CONSTRAINT error_book_pkey PRIMARY KEY (id), 
	CONSTRAINT error_book_subject_id_fkey FOREIGN KEY(subject_id) REFERENCES subject (id)
);
CREATE TABLE error_type (
	id INTEGER NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	subject_id INTEGER, 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP, 
	CONSTRAINT error_type_pkey PRIMARY KEY (id), 
	CONSTRAINT error_type_subject_id_fkey FOREIGN KEY(subject_id) REFERENCES subject (id)
);
CREATE TABLE knowledge_assert (
  id INTEGER PRIMARY KEY CHECK(id=1),
  guard INTEGER NOT NULL DEFAULT 1,
  structure INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE knowledge_point (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	subject_id INTEGER NOT NULL, 
	grade INTEGER, 
	semester INTEGER, 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP, code TEXT, name_key TEXT, level INTEGER, parent_id INTEGER, sort_order INTEGER NOT NULL DEFAULT 0, updated_at TEXT, 
	CONSTRAINT knowledge_point_pkey PRIMARY KEY (id), 
	CONSTRAINT knowledge_point_subject_id_fkey FOREIGN KEY(subject_id) REFERENCES subject (id)
);
CREATE TABLE kp_error_type (
	id INTEGER NOT NULL, 
	knowledge_point_id INTEGER NOT NULL, 
	error_type_id INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT kp_error_type_pkey PRIMARY KEY (id), 
	CONSTRAINT kp_error_type_error_type_id_fkey FOREIGN KEY(error_type_id) REFERENCES error_type (id) ON DELETE CASCADE, 
	CONSTRAINT kp_error_type_knowledge_point_id_fkey FOREIGN KEY(knowledge_point_id) REFERENCES knowledge_point (id) ON DELETE CASCADE
);
CREATE TABLE learning_report (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	subject_id INTEGER, 
	grade INTEGER, 
	time_range_days INTEGER, 
	content TEXT NOT NULL, 
	total_questions INTEGER, 
	total_words INTEGER, 
	overall_accuracy DOUBLE PRECISION, 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP, 
	updated_at TIMESTAMP, 
	CONSTRAINT learning_report_pkey PRIMARY KEY (id), 
	CONSTRAINT learning_report_subject_id_fkey FOREIGN KEY(subject_id) REFERENCES subject (id)
);
CREATE TABLE operation_log (
	id INTEGER NOT NULL, 
	operator VARCHAR(100), 
	operation_type VARCHAR(50) NOT NULL, 
	operation_status VARCHAR(20) NOT NULL, 
	target_type VARCHAR(50), 
	target_id INTEGER, 
	request_data TEXT, 
	response_data TEXT, 
	error_message TEXT, 
	ip_address VARCHAR(50), 
	user_agent TEXT, 
	created_at TIMESTAMP, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT operation_log_pkey PRIMARY KEY (id)
);
CREATE TABLE practice_set (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	notes TEXT, 
	subject_id INTEGER NOT NULL, 
	source_type VARCHAR(20), 
	question_type VARCHAR(20), 
	pdf_path VARCHAR(500), 
	total_questions INTEGER, 
	reviewed BOOLEAN, 
	review_count INTEGER, 
	accuracy DOUBLE PRECISION, 
	last_reviewed_at TIMESTAMP, 
	review_images TEXT, 
	passage_id INTEGER, 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP, 
	CONSTRAINT practice_set_pkey PRIMARY KEY (id), 
	CONSTRAINT practice_set_passage_id_fkey FOREIGN KEY(passage_id) REFERENCES reading_passage (id), 
	CONSTRAINT practice_set_subject_id_fkey FOREIGN KEY(subject_id) REFERENCES subject (id)
);
CREATE TABLE practice_set_question (
	id INTEGER NOT NULL, 
	practice_set_id INTEGER NOT NULL, 
	question_id INTEGER NOT NULL, 
	similar_question_id INTEGER, 
	is_correct BOOLEAN, 
	display_order INTEGER, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT practice_set_question_pkey PRIMARY KEY (id), 
	CONSTRAINT practice_set_question_similar_question_id_fkey FOREIGN KEY(similar_question_id) REFERENCES similar_question (id), 
	CONSTRAINT practice_set_question_question_id_fkey FOREIGN KEY(question_id) REFERENCES question (id), 
	CONSTRAINT practice_set_question_practice_set_id_fkey FOREIGN KEY(practice_set_id) REFERENCES practice_set (id)
);
CREATE TABLE question (
	id INTEGER NOT NULL, 
	error_book_id INTEGER, 
	subject_id INTEGER NOT NULL, 
	original_image VARCHAR(500), 
	original_images TEXT, 
	original_text TEXT, 
	grade INTEGER, 
	semester INTEGER, 
	parsed_question TEXT, 
	answer TEXT, 
	analysis TEXT, 
	analysis_image VARCHAR(500), 
	difficulty INTEGER, 
	error_type VARCHAR(50), 
	knowledge_point VARCHAR(200), 
	review_count INTEGER NOT NULL, 
	correct_count INTEGER NOT NULL, 
	error_count INTEGER NOT NULL, 
	last_reviewed_at TIMESTAMP, 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP, 
	updated_at TIMESTAMP, knowledge_revision INTEGER NOT NULL DEFAULT 0, legacy_knowledge_point TEXT, 
	CONSTRAINT question_pkey PRIMARY KEY (id), 
	CONSTRAINT check_difficulty CHECK (difficulty >= 1 AND difficulty <= 5), 
	CONSTRAINT question_subject_id_fkey FOREIGN KEY(subject_id) REFERENCES subject (id), 
	CONSTRAINT question_error_book_id_fkey FOREIGN KEY(error_book_id) REFERENCES error_book (id)
);
CREATE TABLE question_knowledge_point (
  id INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL,
  knowledge_point_id INTEGER NOT NULL,
  is_primary INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'manual',
  deleted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE question_tag (
	question_id INTEGER NOT NULL, 
	tag_id INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT question_tag_pkey PRIMARY KEY (question_id, tag_id), 
	CONSTRAINT question_tag_tag_id_fkey FOREIGN KEY(tag_id) REFERENCES tag (id), 
	CONSTRAINT question_tag_question_id_fkey FOREIGN KEY(question_id) REFERENCES question (id)
);
CREATE TABLE reading_passage (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	content TEXT NOT NULL, 
	topic VARCHAR(100) NOT NULL, 
	grade INTEGER NOT NULL, 
	difficulty INTEGER NOT NULL, 
	word_count INTEGER, 
	source VARCHAR(50), 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP, 
	updated_at TIMESTAMP, 
	CONSTRAINT reading_passage_pkey PRIMARY KEY (id)
);
CREATE TABLE reading_question (
	id INTEGER NOT NULL, 
	passage_id INTEGER NOT NULL, 
	question_number INTEGER NOT NULL, 
	question_text TEXT NOT NULL, 
	option_a VARCHAR(500) NOT NULL, 
	option_b VARCHAR(500) NOT NULL, 
	option_c VARCHAR(500) NOT NULL, 
	option_d VARCHAR(500) NOT NULL, 
	correct_answer VARCHAR(1) NOT NULL, 
	explanation TEXT, 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP, 
	CONSTRAINT reading_question_pkey PRIMARY KEY (id), 
	CONSTRAINT reading_question_passage_id_fkey FOREIGN KEY(passage_id) REFERENCES reading_passage (id)
);
CREATE TABLE redemption (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	reward_id INTEGER NOT NULL, 
	star_cost INTEGER NOT NULL, 
	redeemed_at TIMESTAMP, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT redemption_pkey PRIMARY KEY (id), 
	CONSTRAINT redemption_reward_id_fkey FOREIGN KEY(reward_id) REFERENCES reward (id)
);
CREATE TABLE request_record (name TEXT PRIMARY KEY,value TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
CREATE TABLE reward (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR(500), 
	icon VARCHAR(500), 
	cost_stars INTEGER NOT NULL, 
	total_stock INTEGER, 
	remaining_stock INTEGER, 
	is_active BOOLEAN, 
	deleted BOOLEAN, 
	image_url VARCHAR(500), 
	created_at TIMESTAMP, 
	CONSTRAINT reward_pkey PRIMARY KEY (id)
);
CREATE TABLE runtime_config (name TEXT PRIMARY KEY,value TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL);
CREATE TABLE similar_question (
	id INTEGER NOT NULL, 
	source_question_id INTEGER NOT NULL, 
	similar_text TEXT NOT NULL, 
	similar_answer TEXT, 
	similarity_score DOUBLE PRECISION, 
	deleted BOOLEAN NOT NULL, 
	generated_at TIMESTAMP, 
	CONSTRAINT similar_question_pkey PRIMARY KEY (id), 
	CONSTRAINT similar_question_source_question_id_fkey FOREIGN KEY(source_question_id) REFERENCES question (id)
);
CREATE TABLE star_action (
	id INTEGER NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	star_value INTEGER NOT NULL, 
	icon VARCHAR(500), 
	enabled BOOLEAN, 
	is_custom BOOLEAN, 
	deleted BOOLEAN, 
	created_at TIMESTAMP, 
	CONSTRAINT star_action_pkey PRIMARY KEY (id), 
	CONSTRAINT star_action_code_key UNIQUE (code)
);
CREATE TABLE star_balance (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	balance INTEGER, 
	updated_at TIMESTAMP, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT star_balance_pkey PRIMARY KEY (id)
);
CREATE TABLE star_record (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	action_code VARCHAR(50) NOT NULL, 
	star_delta INTEGER NOT NULL, 
	balance_after INTEGER NOT NULL, 
	reason VARCHAR(200), 
	deleted BOOLEAN, 
	created_at TIMESTAMP, 
	CONSTRAINT star_record_pkey PRIMARY KEY (id)
);
CREATE TABLE subject (
	id INTEGER NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP, 
	CONSTRAINT subject_pkey PRIMARY KEY (id), 
	CONSTRAINT subject_name_key UNIQUE (name)
);
CREATE TABLE tag (
	id INTEGER NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	color VARCHAR(20), 
	deleted BOOLEAN NOT NULL, 
	CONSTRAINT tag_pkey PRIMARY KEY (id), 
	CONSTRAINT tag_name_key UNIQUE (name)
);
CREATE TABLE word (
	id INTEGER NOT NULL, 
	english VARCHAR(200) NOT NULL, 
	chinese TEXT NOT NULL, 
	phonetic VARCHAR(100), 
	grade INTEGER, 
	semester INTEGER, 
	review_count INTEGER, 
	correct_count INTEGER, 
	last_reviewed_at TIMESTAMP, 
	next_review_at TIMESTAMP, 
	ease_factor INTEGER, 
	interval INTEGER, 
	learning_phase VARCHAR(20), 
	deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP NOT NULL, entry_type TEXT NOT NULL DEFAULT 'word', focus_spec TEXT, focus_status TEXT NOT NULL DEFAULT 'none', focus_updated_at TEXT, dictation_level INTEGER NOT NULL DEFAULT 3, 
	CONSTRAINT word_pkey PRIMARY KEY (id)
);
CREATE TABLE word_review (
	id INTEGER NOT NULL, 
	total_count INTEGER, 
	correct_count INTEGER, 
	error_count INTEGER, 
	duration INTEGER, 
	reviewed_at TIMESTAMP NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT word_review_pkey PRIMARY KEY (id)
);
CREATE TABLE word_review_log (
	id INTEGER NOT NULL, 
	word_id INTEGER NOT NULL, 
	is_correct BOOLEAN NOT NULL, 
	user_answer TEXT, 
	review_type INTEGER NOT NULL, 
	reviewed_at TIMESTAMP NOT NULL, 
	deleted BOOLEAN NOT NULL, token_results TEXT, dictation_level INTEGER, 
	CONSTRAINT word_review_log_pkey PRIMARY KEY (id), 
	CONSTRAINT word_review_log_word_id_fkey FOREIGN KEY(word_id) REFERENCES word (id)
);
CREATE TABLE word_review_session (
	id INTEGER NOT NULL, 
	practice_set_id INTEGER, 
	session_id INTEGER NOT NULL, 
	total_count INTEGER, 
	correct_count INTEGER, 
	accuracy INTEGER, 
	duration INTEGER, 
	reviewed_at TIMESTAMP, 
	word_results TEXT, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT word_review_session_pkey PRIMARY KEY (id), 
	CONSTRAINT word_review_session_practice_set_id_fkey FOREIGN KEY(practice_set_id) REFERENCES practice_set (id)
);
CREATE TABLE word_tag (
	word_id INTEGER NOT NULL, 
	tag_id INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, 
	CONSTRAINT word_tag_pkey PRIMARY KEY (word_id, tag_id), 
	CONSTRAINT word_tag_tag_id_fkey FOREIGN KEY(tag_id) REFERENCES tag (id), 
	CONSTRAINT word_tag_word_id_fkey FOREIGN KEY(word_id) REFERENCES word (id)
);
CREATE TABLE write_guard(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL,deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX cf_practice_active_date ON practice_set(created_at DESC,id DESC) WHERE deleted=0;
CREATE INDEX cf_practice_active_source ON practice_set(source_type,subject_id,last_reviewed_at) WHERE deleted=0;
CREATE INDEX cf_question_active_date ON question(created_at DESC,id DESC) WHERE deleted=0;
CREATE INDEX cf_question_subject_grade ON question(subject_id,grade,created_at DESC) WHERE deleted=0;
CREATE INDEX cf_reading_active_grade ON reading_passage(grade,topic,created_at DESC) WHERE deleted=0;
CREATE INDEX cf_review_log_date ON word_review_log(reviewed_at,is_correct) WHERE deleted=0;
CREATE INDEX cf_review_log_word_date ON word_review_log(word_id,reviewed_at DESC,id DESC) WHERE deleted=0;
CREATE INDEX cf_word_active_grade ON word(grade,semester,created_at DESC) WHERE deleted=0;
CREATE INDEX cf_word_entry_focus ON word(entry_type,focus_status) WHERE deleted=0;
CREATE INDEX cf_word_review_due ON word(next_review_at) WHERE deleted=0;
CREATE UNIQUE INDEX cloudflare_star_balance_user ON star_balance(user_id);
CREATE INDEX ix_kp_parent ON knowledge_point(parent_id) WHERE deleted=0;
CREATE INDEX ix_kp_subject_level ON knowledge_point(subject_id, level, sort_order, id) WHERE deleted=0;
CREATE INDEX ix_qkp_point ON question_knowledge_point(knowledge_point_id, question_id) WHERE deleted=0;
CREATE INDEX ix_qkp_question ON question_knowledge_point(question_id, is_primary) WHERE deleted=0;
CREATE INDEX ix_word_english ON word (english);
CREATE UNIQUE INDEX ux_kp_code ON knowledge_point(code) WHERE code IS NOT NULL AND deleted=0;
CREATE UNIQUE INDEX ux_kp_level1_name ON knowledge_point(subject_id, name_key) WHERE level=1 AND deleted=0;
CREATE UNIQUE INDEX ux_kp_level2_name ON knowledge_point(parent_id, name_key) WHERE level=2 AND deleted=0;
CREATE UNIQUE INDEX ux_qkp_pair ON question_knowledge_point(question_id, knowledge_point_id);
CREATE UNIQUE INDEX ux_qkp_primary ON question_knowledge_point(question_id)
  WHERE is_primary=1 AND deleted=0;
CREATE TRIGGER trg_knowledge_assert_guard BEFORE UPDATE OF guard ON knowledge_assert
WHEN NEW.guard IS NULL
BEGIN
  SELECT RAISE(ABORT,'KP_GUARD:题目分类版本冲突，请刷新后重试');
END;
CREATE TRIGGER trg_knowledge_assert_structure BEFORE UPDATE OF structure ON knowledge_assert
WHEN NEW.structure IS NULL
BEGIN
  SELECT RAISE(ABORT,'KP_STRUCT:题目主考点结构校验失败');
END;
CREATE TRIGGER trg_kp_bi BEFORE INSERT ON knowledge_point
BEGIN
  SELECT CASE WHEN NEW.level IS NOT NULL AND NEW.level NOT IN (1,2)
    THEN RAISE(ABORT,'KP_LEVEL:知识点层级只能是一级或二级') END;
  SELECT CASE WHEN NEW.deleted=0 AND NEW.level=1 AND NEW.parent_id IS NOT NULL
    THEN RAISE(ABORT,'KP_LEVEL:一级知识点不能有父级') END;
  SELECT CASE WHEN NEW.deleted=0 AND NEW.level=2 AND NOT EXISTS(
      SELECT 1 FROM knowledge_point p
       WHERE p.id=NEW.parent_id AND p.deleted=0 AND p.level=1 AND p.subject_id=NEW.subject_id)
    THEN RAISE(ABORT,'KP_LEVEL:二级知识点必须挂在同一学科的有效一级下') END;
  SELECT CASE WHEN NEW.deleted=0 AND NEW.level IN (1,2)
      AND (NEW.name_key IS NULL OR trim(NEW.name_key)='')
    THEN RAISE(ABORT,'KP_NAME:知识点名称不能为空') END;
END;
CREATE TRIGGER trg_kp_bu BEFORE UPDATE ON knowledge_point
BEGIN
  SELECT CASE WHEN NEW.level IS NOT NULL AND NEW.level NOT IN (1,2)
    THEN RAISE(ABORT,'KP_LEVEL:知识点层级只能是一级或二级') END;
  SELECT CASE WHEN NEW.deleted=0 AND NEW.level=1 AND NEW.parent_id IS NOT NULL
    THEN RAISE(ABORT,'KP_LEVEL:一级知识点不能有父级') END;
  -- 已引用的节点禁止改学科，先于父级一致性检查，便于应用层映射为 KP_SUBJECT。
  SELECT CASE WHEN OLD.level IS NOT NULL AND NEW.subject_id IS NOT OLD.subject_id
      AND (EXISTS(SELECT 1 FROM knowledge_point c WHERE c.parent_id=OLD.id AND c.deleted=0)
        OR EXISTS(SELECT 1 FROM question_knowledge_point l
                    JOIN question q ON q.id=l.question_id AND q.deleted=0
                   WHERE l.knowledge_point_id=OLD.id AND l.deleted=0))
    THEN RAISE(ABORT,'KP_SUBJECT:有子级或题目关联的知识点不能修改学科') END;
  SELECT CASE WHEN NEW.deleted=0 AND NEW.level=2 AND NOT EXISTS(
      SELECT 1 FROM knowledge_point p
       WHERE p.id=NEW.parent_id AND p.deleted=0 AND p.level=1 AND p.subject_id=NEW.subject_id)
    THEN RAISE(ABORT,'KP_LEVEL:二级知识点必须挂在同一学科的有效一级下') END;
  SELECT CASE WHEN NEW.deleted=0 AND NEW.level IN (1,2)
      AND (NEW.name_key IS NULL OR trim(NEW.name_key)='')
    THEN RAISE(ABORT,'KP_NAME:知识点名称不能为空') END;
  SELECT CASE WHEN OLD.level IS NOT NULL AND NEW.level IS NOT OLD.level
      AND (EXISTS(SELECT 1 FROM knowledge_point c WHERE c.parent_id=OLD.id AND c.deleted=0)
        OR EXISTS(SELECT 1 FROM question_knowledge_point l
                    JOIN question q ON q.id=l.question_id AND q.deleted=0
                   WHERE l.knowledge_point_id=OLD.id AND l.deleted=0))
    THEN RAISE(ABORT,'KP_MOVE:有子级或题目关联的知识点不能修改层级') END;
  SELECT CASE WHEN OLD.level=2 AND NEW.parent_id IS NOT OLD.parent_id
      AND EXISTS(SELECT 1 FROM question_knowledge_point l
                   JOIN question q ON q.id=l.question_id AND q.deleted=0
                  WHERE l.knowledge_point_id=OLD.id AND l.deleted=0)
    THEN RAISE(ABORT,'KP_MOVE:有题目关联的二级知识点不能移动父级') END;
  SELECT CASE WHEN OLD.deleted=0 AND NEW.deleted=1 AND OLD.level=1
      AND EXISTS(SELECT 1 FROM knowledge_point c WHERE c.parent_id=OLD.id AND c.deleted=0)
    THEN RAISE(ABORT,'KP_CHILD:一级知识点仍有有效二级，不能删除') END;
  SELECT CASE WHEN OLD.deleted=0 AND NEW.deleted=1 AND OLD.level=2
      AND EXISTS(SELECT 1 FROM question_knowledge_point l
                   JOIN question q ON q.id=l.question_id AND q.deleted=0
                  WHERE l.knowledge_point_id=OLD.id AND l.deleted=0)
    THEN RAISE(ABORT,'KP_INUSE:二级知识点仍被有效错题引用，不能删除') END;
END;
CREATE TRIGGER trg_kp_error_type_bi BEFORE INSERT ON kp_error_type
WHEN NEW.deleted=0
BEGIN
  SELECT CASE WHEN NOT EXISTS(
      SELECT 1 FROM knowledge_point k WHERE k.id=NEW.knowledge_point_id AND k.deleted=0 AND k.level=2)
    THEN RAISE(ABORT,'KP_LEVEL:错误类型只能配置在有效的二级知识点上') END;
END;
CREATE TRIGGER trg_kp_error_type_bu BEFORE UPDATE ON kp_error_type
WHEN NEW.deleted=0
BEGIN
  SELECT CASE WHEN NOT EXISTS(
      SELECT 1 FROM knowledge_point k WHERE k.id=NEW.knowledge_point_id AND k.deleted=0 AND k.level=2)
    THEN RAISE(ABORT,'KP_LEVEL:错误类型只能配置在有效的二级知识点上') END;
END;
CREATE TRIGGER trg_qkp_bi BEFORE INSERT ON question_knowledge_point
WHEN NEW.deleted=0
BEGIN
  SELECT CASE WHEN NOT EXISTS(
      SELECT 1 FROM question q JOIN knowledge_point k ON k.id=NEW.knowledge_point_id
       WHERE q.id=NEW.question_id AND q.deleted=0 AND k.deleted=0 AND k.level=2)
    THEN RAISE(ABORT,'KP_LEVEL:只能关联未删除的二级知识点') END;
  SELECT CASE WHEN NOT EXISTS(
      SELECT 1 FROM question q JOIN knowledge_point k ON k.id=NEW.knowledge_point_id
       WHERE q.id=NEW.question_id AND q.deleted=0 AND k.deleted=0 AND k.subject_id=q.subject_id)
    THEN RAISE(ABORT,'KP_SUBJECT:知识点必须与题目同学科') END;
END;
CREATE TRIGGER trg_qkp_bu BEFORE UPDATE ON question_knowledge_point
WHEN NEW.deleted=0
BEGIN
  SELECT CASE WHEN NOT EXISTS(
      SELECT 1 FROM question q JOIN knowledge_point k ON k.id=NEW.knowledge_point_id
       WHERE q.id=NEW.question_id AND q.deleted=0 AND k.deleted=0 AND k.level=2)
    THEN RAISE(ABORT,'KP_LEVEL:只能关联未删除的二级知识点') END;
  SELECT CASE WHEN NOT EXISTS(
      SELECT 1 FROM question q JOIN knowledge_point k ON k.id=NEW.knowledge_point_id
       WHERE q.id=NEW.question_id AND q.deleted=0 AND k.deleted=0 AND k.subject_id=q.subject_id)
    THEN RAISE(ABORT,'KP_SUBJECT:知识点必须与题目同学科') END;
END;
CREATE TRIGGER trg_question_subject_kp BEFORE UPDATE OF subject_id ON question
WHEN NEW.subject_id IS NOT OLD.subject_id
BEGIN
  SELECT CASE WHEN EXISTS(
      SELECT 1 FROM question_knowledge_point l JOIN knowledge_point k ON k.id=l.knowledge_point_id
       WHERE l.question_id=OLD.id AND l.deleted=0
         AND (k.deleted=1 OR k.subject_id IS NOT NEW.subject_id))
    THEN RAISE(ABORT,'KP_SUBJECT:题目改学科前必须清除原学科知识点关联') END;
END;
CREATE TRIGGER trg_subject_bu BEFORE UPDATE OF deleted ON subject
WHEN NEW.deleted=1 AND OLD.deleted=0
BEGIN
  SELECT CASE WHEN EXISTS(
      SELECT 1 FROM knowledge_point k
       WHERE k.subject_id=OLD.id AND k.deleted=0 AND k.level IS NOT NULL)
    THEN RAISE(ABORT,'KP_INUSE:学科下仍有有效知识点，不能删除') END;
  SELECT CASE WHEN EXISTS(
      SELECT 1 FROM question q WHERE q.subject_id=OLD.id AND q.deleted=0)
    THEN RAISE(ABORT,'KP_INUSE:学科下仍有有效错题，不能删除') END;
END;
