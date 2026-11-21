-- 0017：翻一翻。只新建表 flip_log，不改已有的表。
-- 学生每点一次"我记得"/"我忘了"记一条：result 是 remember（记得）或 forget（忘了）。
-- flip_date 是北京日期（YYYY-MM-DD），created_at 是北京时间；同一学生同一道题同一天最多一条未删除记录。
-- 只用来决定下次翻哪些题和统计翻了几天、几张；不影响考点掌握度、错题毕业和知识星空。
-- 删除只做软删除（deleted=1）。

CREATE TABLE flip_log (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL DEFAULT 1,
    question_id INTEGER NOT NULL,
    result TEXT NOT NULL,
    flip_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0
);

-- 同一学生同一题同一天只记一次；软删除后的记录不占位置。
CREATE UNIQUE INDEX idx_flip_log_day ON flip_log(student_id, question_id, flip_date) WHERE deleted=0;

-- 按日期区间查"翻了几天、几张"（首页、周报）。
CREATE INDEX idx_flip_log_date ON flip_log(student_id, flip_date);
