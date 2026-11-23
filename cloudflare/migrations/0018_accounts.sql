-- 多家庭账号：账号列、学生排序、按学生唯一的标签和成就进度、按学生的余额索引、按学生的配置。
-- 设计见 docs/superpowers/specs/2026-11-23-multi-family-accounts-design.md。
-- 本迁移是"迁移只追加"的唯一例外：重建 tag、achievement_progress 两张表，
-- 去掉旧的表级唯一约束（SQLite 只能靠重建表去掉）。执行前必须先导出 D1 备份。

-- question_tag、word_tag 有外键指向 tag(id)，achievement_progress 有外键指向 achievement(id)；
-- 推迟到提交时再检查外键，才能先删旧表再改名。
PRAGMA defer_foreign_keys = on;

-- 1. 账号列
ALTER TABLE app_user ADD COLUMN username TEXT;
ALTER TABLE app_user ADD COLUMN password_hash TEXT;
ALTER TABLE app_user ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;
ALTER TABLE app_user ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE app_user ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE app_user ADD COLUMN last_login_at TEXT;
ALTER TABLE app_user ADD COLUMN updated_at TEXT;
-- 登录名只在未删除的用户里唯一；没设登录名（NULL）的不参与
CREATE UNIQUE INDEX idx_app_user_username ON app_user(username) WHERE deleted=0 AND username IS NOT NULL;
-- 1 号用户（现有数据的主人）是管理员；登录名和密码由 backend/scripts/set_admin_password.py 设置
UPDATE app_user SET is_admin=1 WHERE id=1;

-- 2. 学生排序（登录时默认进入排在最前面的学生）
ALTER TABLE student ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0;

-- 3. 重建 tag：列与旧表相同，去掉表级 UNIQUE(name)，改为同一学生内唯一
CREATE TABLE tag_new (
  id INTEGER NOT NULL,
  name VARCHAR(50) NOT NULL,
  color VARCHAR(20),
  deleted BOOLEAN NOT NULL DEFAULT 0,
  student_id INTEGER NOT NULL DEFAULT 1,
  CONSTRAINT tag_pkey PRIMARY KEY (id)
);
INSERT INTO tag_new(id,name,color,deleted,student_id)
  SELECT id,name,color,deleted,student_id FROM tag;
DROP TABLE tag;
ALTER TABLE tag_new RENAME TO tag;
CREATE UNIQUE INDEX idx_tag_student_name ON tag(student_id,name) WHERE deleted=0;

-- 4. 重建 achievement_progress：列与旧表相同，去掉表级 UNIQUE(user_id, achievement_id)，
--    改为同一学生同一成就唯一；旧列 user_id 保留但以后不再读写
CREATE TABLE achievement_progress_new (
  id INTEGER NOT NULL,
  user_id INTEGER,
  achievement_id INTEGER NOT NULL,
  current_count INTEGER,
  is_unlocked BOOLEAN,
  unlocked_at TIMESTAMP,
  deleted INTEGER NOT NULL DEFAULT 0,
  student_id INTEGER NOT NULL DEFAULT 1,
  CONSTRAINT achievement_progress_pkey PRIMARY KEY (id),
  CONSTRAINT achievement_progress_achievement_id_fkey FOREIGN KEY(achievement_id) REFERENCES achievement (id)
);
INSERT INTO achievement_progress_new(id,user_id,achievement_id,current_count,is_unlocked,unlocked_at,deleted,student_id)
  SELECT id,user_id,achievement_id,current_count,is_unlocked,unlocked_at,deleted,student_id FROM achievement_progress;
DROP TABLE achievement_progress;
ALTER TABLE achievement_progress_new RENAME TO achievement_progress;
CREATE UNIQUE INDEX idx_achievement_progress_student ON achievement_progress(student_id,achievement_id) WHERE deleted=0;

-- 5. 余额：删掉按 user_id 唯一的旧索引，改为按学生唯一
DROP INDEX IF EXISTS cloudflare_star_balance_user;
CREATE UNIQUE INDEX idx_star_balance_student ON star_balance(student_id) WHERE deleted=0;

-- 6. 按学生的配置：默认年级学期（app）、知识星空进度（starmap）复制成 1 号学生的，原行保留
INSERT INTO runtime_config(name,value,deleted,updated_at)
  SELECT 'app:1',value,0,updated_at FROM runtime_config WHERE name='app'
  ON CONFLICT(name) DO NOTHING;
INSERT INTO runtime_config(name,value,deleted,updated_at)
  SELECT 'starmap:1',value,0,updated_at FROM runtime_config WHERE name='starmap'
  ON CONFLICT(name) DO NOTHING;
