-- 0012：知识星空（考点掌握度）需要的结构。
-- 第一条 ALTER 不能重复执行；其余语句都带 IF NOT EXISTS，可以重复执行。
-- 所有新表只做软删除（deleted）。

-- 英语语法考点"大约几年级学"；不用 knowledge_point.grade，因为录入接口按 grade 过滤考点目录
ALTER TABLE knowledge_point ADD COLUMN learn_grade INTEGER;

-- 教材的节，例如 沪教版六年级上册 第 4 章 线段与角 / 4.2 角
CREATE TABLE IF NOT EXISTS textbook_section (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL DEFAULT 1,
  subject_id INTEGER NOT NULL,
  textbook TEXT NOT NULL,
  chapter_no INTEGER NOT NULL,
  chapter_name TEXT NOT NULL,
  section_no TEXT NOT NULL,
  section_name TEXT NOT NULL,
  sort_order INTEGER NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT
);

-- 节和二级考点的对应（一节可以对应多个考点）
CREATE TABLE IF NOT EXISTS textbook_section_point (
  id INTEGER PRIMARY KEY,
  section_id INTEGER NOT NULL,
  knowledge_point_id INTEGER NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT
);

-- 先学后学连线：from 先学，to 后学
CREATE TABLE IF NOT EXISTS knowledge_link (
  id INTEGER PRIMARY KEY,
  from_point_id INTEGER NOT NULL,
  to_point_id INTEGER NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT
);

-- 家长在管理设置里做的手动调整；kind 为 up_small / up_large / set_mastered / down_small
CREATE TABLE IF NOT EXISTS mastery_adjustment (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL DEFAULT 1,
  knowledge_point_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  created_at TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS cf_mastery_adjustment_point ON mastery_adjustment(knowledge_point_id) WHERE deleted=0;
CREATE INDEX IF NOT EXISTS cf_textbook_section_point_point ON textbook_section_point(knowledge_point_id) WHERE deleted=0;
CREATE INDEX IF NOT EXISTS cf_knowledge_link_from ON knowledge_link(from_point_id) WHERE deleted=0;
