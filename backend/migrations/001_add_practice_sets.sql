-- 练习集功能数据库迁移脚本
-- 执行日期: 2026-03-28
-- 版本: v1.0.2

-- 1. 为Question表添加复习相关字段
ALTER TABLE question ADD COLUMN review_count INT NOT NULL DEFAULT 0 COMMENT '复习次数';
ALTER TABLE question ADD COLUMN last_reviewed_at DATETIME COMMENT '最后复习时间';

-- 2. 创建练习集表
CREATE TABLE IF NOT EXISTS practice_set (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL COMMENT '练习集名称',
    subject_id INT NOT NULL COMMENT '所属学科ID',
    question_type VARCHAR(20) DEFAULT 'original' COMMENT '题目类型: original=原题, similar=相似题',
    pdf_path VARCHAR(500) COMMENT '生成的PDF路径',
    total_questions INT DEFAULT 0 COMMENT '总题数',
    reviewed TINYINT(1) DEFAULT 0 COMMENT '是否已复习',
    review_count INT DEFAULT 0 COMMENT '复习次数',
    deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '软删除标记',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subject(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 创建练习集-题目关联表
CREATE TABLE IF NOT EXISTS practice_set_question (
    id INT PRIMARY KEY AUTO_INCREMENT,
    practice_set_id INT NOT NULL COMMENT '练习集ID',
    question_id INT NOT NULL COMMENT '原错题ID',
    similar_question_id INT COMMENT '相似题ID，可为null',
    display_order INT DEFAULT 0 COMMENT '显示顺序',
    FOREIGN KEY (practice_set_id) REFERENCES practice_set(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES question(id),
    FOREIGN KEY (similar_question_id) REFERENCES similar_question(id),
    UNIQUE KEY uk_ps_question_similar (practice_set_id, question_id, similar_question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 创建索引
CREATE INDEX idx_practice_set_subject ON practice_set(subject_id);
CREATE INDEX idx_practice_set_deleted ON practice_set(deleted);
CREATE INDEX idx_psq_practice_set ON practice_set_question(practice_set_id);
CREATE INDEX idx_psq_question ON practice_set_question(question_id);
