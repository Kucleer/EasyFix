-- 两级知识点改造：追加 schema、索引、触发器与版本记录。
-- 只追加，不重放旧快照；迁移前需按 docs/knowledge-hierarchy-final-plan.md 第 12 节停写并备份。
-- 触发器错误消息统一使用 KP_<CODE>:<中文说明>，应用层按前缀映射 409 / 422 / 503。

-- 1. knowledge_point 扩展列
ALTER TABLE knowledge_point ADD COLUMN code TEXT;
ALTER TABLE knowledge_point ADD COLUMN name_key TEXT;
ALTER TABLE knowledge_point ADD COLUMN level INTEGER;
ALTER TABLE knowledge_point ADD COLUMN parent_id INTEGER;
ALTER TABLE knowledge_point ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0;
ALTER TABLE knowledge_point ADD COLUMN updated_at TEXT;

-- 过渡期回填：规范键由应用层用 NFKC + casefold 重新计算，这里只保证非空可比较。
UPDATE knowledge_point SET name_key = lower(trim(name)) WHERE name_key IS NULL;
-- 旧目录行不参与两级树，level 保持 NULL；节点数由迁移脚本重新核对。
CREATE UNIQUE INDEX ux_kp_code ON knowledge_point(code) WHERE code IS NOT NULL AND deleted=0;
CREATE UNIQUE INDEX ux_kp_level1_name ON knowledge_point(subject_id, name_key) WHERE level=1 AND deleted=0;
CREATE UNIQUE INDEX ux_kp_level2_name ON knowledge_point(parent_id, name_key) WHERE level=2 AND deleted=0;
CREATE INDEX ix_kp_subject_level ON knowledge_point(subject_id, level, sort_order, id) WHERE deleted=0;
CREATE INDEX ix_kp_parent ON knowledge_point(parent_id) WHERE deleted=0;

-- 2. question 扩展：分类版本与旧文本原件
ALTER TABLE question ADD COLUMN knowledge_revision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE question ADD COLUMN legacy_knowledge_point TEXT;
UPDATE question SET legacy_knowledge_point = knowledge_point
 WHERE legacy_knowledge_point IS NULL AND knowledge_point IS NOT NULL AND trim(knowledge_point)<>'';

-- 3. 题目与二级知识点多对多关联
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
CREATE UNIQUE INDEX ux_qkp_pair ON question_knowledge_point(question_id, knowledge_point_id);
CREATE UNIQUE INDEX ux_qkp_primary ON question_knowledge_point(question_id)
  WHERE is_primary=1 AND deleted=0;
CREATE INDEX ix_qkp_question ON question_knowledge_point(question_id, is_primary) WHERE deleted=0;
CREATE INDEX ix_qkp_point ON question_knowledge_point(knowledge_point_id, question_id) WHERE deleted=0;

-- 4. 事务内断言表：guard 失败映射 409，structure 失败映射 422。
CREATE TABLE knowledge_assert (
  id INTEGER PRIMARY KEY CHECK(id=1),
  guard INTEGER NOT NULL DEFAULT 1,
  structure INTEGER NOT NULL DEFAULT 1
);
INSERT INTO knowledge_assert(id,guard,structure) VALUES(1,1,1) ON CONFLICT(id) DO NOTHING;
INSERT INTO write_guard(id,revision,deleted) VALUES(1,0,0) ON CONFLICT(id) DO NOTHING;
INSERT INTO runtime_config(name,value,deleted,updated_at)
  VALUES('taxonomy_version','0',0,CURRENT_TIMESTAMP) ON CONFLICT(name) DO NOTHING;

-- 5. knowledge_point 写入约束
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

-- 6. 题目关联只允许有效同学科二级
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

-- 7. 题目改学科时不允许留下原学科的有效关联
CREATE TRIGGER trg_question_subject_kp BEFORE UPDATE OF subject_id ON question
WHEN NEW.subject_id IS NOT OLD.subject_id
BEGIN
  SELECT CASE WHEN EXISTS(
      SELECT 1 FROM question_knowledge_point l JOIN knowledge_point k ON k.id=l.knowledge_point_id
       WHERE l.question_id=OLD.id AND l.deleted=0
         AND (k.deleted=1 OR k.subject_id IS NOT NEW.subject_id))
    THEN RAISE(ABORT,'KP_SUBJECT:题目改学科前必须清除原学科知识点关联') END;
END;

-- 8. 错误类型只配置在二级
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

-- 9. 学科删除保护
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

-- 10. 事务内断言触发器
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
