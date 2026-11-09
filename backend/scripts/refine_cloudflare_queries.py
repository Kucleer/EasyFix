"""补齐迁移端关联记录软删除过滤，保持原始后端开发文件不变。"""

from pathlib import Path


def main():
    """只对明确列出的云端 SQL 片段做幂等替换。"""
    root=Path(__file__).resolve().parents[2]/'cloudflare/src'
    replacements={
      'FROM practice_set_question pq JOIN':'FROM practice_set_question pq JOIN',
      'WHERE pq.question_id=? AND pq.is_correct':'WHERE pq.deleted=0 AND pq.question_id=? AND pq.is_correct',
      'WHERE pq.practice_set_id=? ORDER BY':'WHERE pq.deleted=0 AND pq.practice_set_id=? ORDER BY',
      'WHERE p.deleted=0 AND p.source_type=':'WHERE p.deleted=0 AND pq.deleted=0 AND p.source_type=',
      'FROM word_review ORDER BY reviewed_at':'FROM word_review WHERE deleted=0 ORDER BY reviewed_at',
      'WHERE s.reviewed_at>=?':'WHERE s.deleted=0 AND s.reviewed_at>=?',
      'WHERE s.practice_set_id IS NULL OR p.deleted=0':'WHERE s.deleted=0 AND (s.practice_set_id IS NULL OR p.deleted=0)',
      'WHERE r.practice_set_id IS NULL OR p.deleted=0':'WHERE r.deleted=0 AND (r.practice_set_id IS NULL OR p.deleted=0)',
      'WHERE s.practice_set_id=? ORDER BY':'WHERE s.deleted=0 AND s.practice_set_id=? ORDER BY',
      'FROM word_review_session WHERE practice_set_id=?':'FROM word_review_session WHERE deleted=0 AND practice_set_id=?',
      'FROM word_review_session WHERE practice_set_id IN':'FROM word_review_session WHERE deleted=0 AND practice_set_id IN',
      'FROM star_balance WHERE user_id=1':'FROM star_balance WHERE user_id=1 AND deleted=0',
      'UPDATE star_balance SET balance=balance+?,updated_at=? WHERE user_id=1':'UPDATE star_balance SET balance=balance+?,updated_at=? WHERE user_id=1 AND deleted=0',
      'SELECT p.* FROM achievement_progress p JOIN achievement a ON a.id=p.achievement_id WHERE p.user_id=1':'SELECT p.* FROM achievement_progress p JOIN achievement a ON a.id=p.achievement_id WHERE p.deleted=0 AND p.user_id=1',
      'SELECT * FROM achievement_progress WHERE user_id=1 AND achievement_id=?':'SELECT * FROM achievement_progress WHERE deleted=0 AND user_id=1 AND achievement_id=?',
      'SELECT * FROM redemption WHERE user_id=1':'SELECT * FROM redemption WHERE deleted=0 AND user_id=1',
    }
    for name in ('main.py','questions.py','analytics.py','practices.py','motivation.py','words.py'):
        path=root/name;source=path.read_text(encoding='utf-8')
        for old,new in replacements.items():
            if old!=new and new not in source:source=source.replace(old,new)
        path.write_text(source,encoding='utf-8')
    print('Refined cloud-only soft-delete queries.')


if __name__=='__main__':main()
