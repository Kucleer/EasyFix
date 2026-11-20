-- 0016：周报。只新建表 weekly_report，不改已有的表。
-- 每个学生每一期（week_end，周日 20:00 北京时间）最多一条未删除的周报；删除只做软删除（deleted=1）。
-- status：new（刚建）→ facts_ready（数字已算好）→ done（文字已写好）。
-- text_source：文字来源，model（模型写的）或 fallback（模板兜底）。
-- step_started_at 用来判断某一步是否被认领后卡住（过期后可以重新认领）。

CREATE TABLE weekly_report (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL DEFAULT 1,
    week_end TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    step_started_at TEXT,
    facts TEXT,
    text TEXT,
    text_source TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0
);

-- 同一学生同一期只允许一条未删除的周报；软删除后的记录不占位置。
CREATE UNIQUE INDEX idx_weekly_report_week ON weekly_report(student_id, week_end) WHERE deleted=0;
