-- 录题与卷子：用户表、学生表、卷子记录表，错题新增卷子关联与核对列，各学生数据表加 student_id。
-- 只追加表、列、索引和回填，不改不删任何已有的列；所有新列都带默认值，迁移前的旧代码照常写入。

-- 1. 用户与学生（预置默认行）
CREATE TABLE app_user (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT
);
CREATE TABLE student (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL DEFAULT 1,
  name TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT,
  updated_at TEXT
);
INSERT INTO app_user(id,name,deleted,created_at)
  VALUES(1,'默认用户',0,CURRENT_TIMESTAMP) ON CONFLICT(id) DO NOTHING;
INSERT INTO student(id,user_id,name,deleted,created_at,updated_at)
  VALUES(1,1,'默认学生',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) ON CONFLICT(id) DO NOTHING;

-- 2. 卷子记录：paper_type 为 homework/chapter_practice/exam，exam_kind 为 unit/midterm/final/other，
--    source 为 agent/manual/history；images 是按页顺序存图片路径的 JSON 数组
CREATE TABLE paper (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL DEFAULT 1,
  subject_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  paper_type TEXT NOT NULL DEFAULT 'homework',
  exam_kind TEXT,
  paper_date TEXT,
  grade INTEGER,
  semester INTEGER,
  score REAL,
  full_score REAL,
  images TEXT NOT NULL DEFAULT '[]',
  notes TEXT,
  source TEXT NOT NULL DEFAULT 'manual',
  deleted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT,
  updated_at TEXT
);

-- 3. 各学生数据表加 student_id（附属表跟着主表走，不单独加）
ALTER TABLE question ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE error_book ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE word ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE word_review ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE word_review_session ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE practice_set ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE learning_report ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE reading_passage ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE tag ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE reward ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE redemption ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE star_balance ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE star_record ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE star_action ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE achievement ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE achievement_progress ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1;

-- 4. 错题新增列：卷子关联、卷面信息、核对状态
ALTER TABLE question ADD COLUMN paper_id INTEGER;
ALTER TABLE question ADD COLUMN paper_page INTEGER;
ALTER TABLE question ADD COLUMN question_no TEXT;
ALTER TABLE question ADD COLUMN wrong_answer TEXT;
ALTER TABLE question ADD COLUMN wrong_evidence TEXT;
-- review_status 为 approved/pending/rejected，旧题和旧代码写入的题都是 approved
ALTER TABLE question ADD COLUMN review_status TEXT NOT NULL DEFAULT 'approved';
ALTER TABLE question ADD COLUMN review_reasons TEXT;
ALTER TABLE question ADD COLUMN review_note TEXT;
ALTER TABLE question ADD COLUMN reviewed_at TEXT;

-- 5. 回填旧题（含已软删除的行）：按 学科+年级+学期 各建一条“历史作业”卷子，再把旧题指过去
INSERT INTO paper(student_id,subject_id,name,paper_type,paper_date,grade,semester,images,source,deleted,created_at,updated_at)
SELECT 1, g.subject_id,
       -- 无年级归“年级未填”；有年级时拼“年级+学期+学科”，学期不是 1/2 时不带学期
       CASE WHEN g.grade IS NULL THEN g.subject_name || ' 历史作业（年级未填）'
            ELSE CASE g.grade WHEN 1 THEN '一' WHEN 2 THEN '二' WHEN 3 THEN '三' WHEN 4 THEN '四'
                              WHEN 5 THEN '五' WHEN 6 THEN '六' WHEN 7 THEN '七' WHEN 8 THEN '八'
                              WHEN 9 THEN '九' WHEN 10 THEN '十' WHEN 11 THEN '十一' WHEN 12 THEN '十二'
                              ELSE CAST(g.grade AS TEXT) END
                 || '年级'
                 || CASE g.semester WHEN 1 THEN '上' WHEN 2 THEN '下' ELSE '' END
                 || ' ' || g.subject_name || ' 历史作业' END,
       'homework',
       -- 日期取组内最早录入日期，全为空时取执行当天
       COALESCE(g.first_date, date('now')),
       g.grade, g.semester, '[]', 'history', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
  FROM (SELECT q.subject_id AS subject_id, q.grade AS grade, q.semester AS semester,
               MIN(date(q.created_at)) AS first_date,
               COALESCE((SELECT s.name FROM subject s WHERE s.id=q.subject_id), '未知学科') AS subject_name
          FROM question q
         GROUP BY q.subject_id, q.grade, q.semester) g;
-- 年级、学期可能为空，比较用 IS 才能让空值对得上
UPDATE question SET paper_id=(
  SELECT p.id FROM paper p
   WHERE p.source='history' AND p.subject_id=question.subject_id
     AND p.grade IS question.grade AND p.semester IS question.semester
   ORDER BY p.id LIMIT 1)
 WHERE paper_id IS NULL;

-- 6. 索引
CREATE INDEX IF NOT EXISTS cf_question_review ON question(review_status) WHERE deleted=0 AND review_status='pending';
CREATE INDEX IF NOT EXISTS cf_question_paper ON question(paper_id) WHERE deleted=0;
CREATE INDEX IF NOT EXISTS cf_paper_student_date ON paper(student_id,paper_date) WHERE deleted=0;
