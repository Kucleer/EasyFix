-- 0014：整页识别录入。一张上传的照片是一条记录，只加表和索引，不改现有表。
-- 两条语句都带 IF NOT EXISTS，可以重复执行；只做软删除（deleted）。

-- status：uploaded 已上传 / reading 读图中 / analyzing 整理中 / rescanning 重扫中 /
--         ready 可以整理 / failed 识别失败 / closed 已结束
-- step_started_at：当前这一步开始的时间（整数秒），用来判断是不是卡住了；没有步骤在跑时为空
-- items：题目草稿，JSON 数组；timings：各步骤用时，JSON 对象
CREATE TABLE IF NOT EXISTS scan_page (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL DEFAULT 1,
  subject_id INTEGER NOT NULL,
  grade INTEGER,
  semester INTEGER,
  image TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'uploaded',
  step_started_at INTEGER,
  ocr_text TEXT,
  ocr_text_enhanced TEXT,
  rescan_used INTEGER NOT NULL DEFAULT 0,
  items TEXT NOT NULL DEFAULT '[]',
  error TEXT,
  timings TEXT NOT NULL DEFAULT '{}',
  deleted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS cf_scan_page_student_status ON scan_page(student_id,status) WHERE deleted=0;
