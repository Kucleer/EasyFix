-- 词组默写优化：词条类型、重点标注、默写档位，以及复习日志的逐词结果。
-- 只追加列和索引，不重建表，不改动任何已有的次数、间隔、阶段和日志内容。
ALTER TABLE word ADD COLUMN entry_type TEXT NOT NULL DEFAULT 'word';
ALTER TABLE word ADD COLUMN focus_spec TEXT;
ALTER TABLE word ADD COLUMN focus_status TEXT NOT NULL DEFAULT 'none';
-- 标注写入时间：错误驱动只看当前标注之后的记录
ALTER TABLE word ADD COLUMN focus_updated_at TEXT;
ALTER TABLE word ADD COLUMN dictation_level INTEGER NOT NULL DEFAULT 3;
ALTER TABLE word_review_log ADD COLUMN token_results TEXT;
ALTER TABLE word_review_log ADD COLUMN dictation_level INTEGER;

-- 回填（包含已软删除的行）：含空格或制表符的英文为词组
UPDATE word SET entry_type='phrase' WHERE instr(trim(english),' ')>0 OR instr(english,char(9))>0;
-- 尚未牢记的词组从档位 1 开始，已牢记的保持档位 3
UPDATE word SET dictation_level=1 WHERE entry_type='phrase' AND COALESCE(learning_phase,'')<>'牢记';
CREATE INDEX IF NOT EXISTS cf_word_entry_focus ON word(entry_type,focus_status) WHERE deleted=0;
