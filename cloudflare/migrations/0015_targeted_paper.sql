-- 0015：考点卷。只加列，不改不删已有的列；新列都有默认值或可空，旧数据保持有效。
-- 注意：ALTER TABLE ... ADD COLUMN 不能重复执行，只能执行一次。不建索引（数据量小）。

-- kind：manual 手动卷（默认）/ targeted 考点卷；grading_revision：批改次数，用来识别重复提交
ALTER TABLE practice_set ADD COLUMN kind TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE practice_set ADD COLUMN grading_revision INTEGER NOT NULL DEFAULT 0;

-- form：original 原题 / similar 相似题，空表示旧数据（按整份卷子的 question_type 判断）
-- reason：入选原因 new/wrong/redo/consolidate/check/spot
-- skip_reason：not_done 没做 / bad_question 题目有误
ALTER TABLE practice_set_question ADD COLUMN form TEXT;
ALTER TABLE practice_set_question ADD COLUMN reason TEXT;
ALTER TABLE practice_set_question ADD COLUMN knowledge_point_id INTEGER;
ALTER TABLE practice_set_question ADD COLUMN skip_reason TEXT;

-- 相似题的解析，可空
ALTER TABLE similar_question ADD COLUMN explanation TEXT;
