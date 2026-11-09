"""按已审阅清单标注英语知识点，默认只预检。"""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'backend/scripts'))
def main():
    """校验题目快照和备份后，在单一事务内只更新知识点。"""
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--backup-dir',type=Path);args=parser.parse_args()
    print('注意：旧 backend 数据库已冻结为只读；本脚本仅保留历史预检证据，不能作为生产写入通道。')
    print('两级知识点改造后的正式写入请使用 cloudflare/scripts/knowledge_backfill.py 生成 SQL。')
    if args.backup_dir:args.backup_dir=args.backup_dir.resolve()
    plan=json.loads((ROOT/'backend/data/annotations/english-knowledge-20261108.json').read_text(encoding='utf-8'));os.chdir(ROOT/'backend')
    from app.database import SessionLocal
    from app.models import Question,KnowledgePoint,Subject
    from app.config import get_settings
    if args.apply:
        if not args.backup_dir:raise ValueError('必须提供备份')
        from backup_data import verify_backup
        verify_backup(args.backup_dir.resolve())
        manifest=json.loads((args.backup_dir/'manifest.json').read_text(encoding='utf-8'));settings=get_settings()
        if manifest['database'].get('database')!=settings.DB_NAME or manifest['database'].get('host')!=settings.DB_HOST:raise ValueError('备份与数据库不匹配')
    with SessionLocal() as db:
        with db.begin():
            subject=db.query(Subject).filter(Subject.id==plan['subject_id'],Subject.deleted==False).one()
            if subject.name!='英语':raise ValueError('学科不匹配')
            for item in plan['labels']:
                q=db.query(Question).filter(Question.id==item['id'],Question.deleted==False).with_for_update().one()
                original=item['original']
                if q.subject_id!=plan['subject_id']:raise ValueError('题目学科不匹配')
                if q.knowledge_point==item['label']:continue
                for key in ['knowledge_point','parsed_question','original_text','answer','analysis','grade','semester']:
                    if getattr(q,key)!=original.get(key):raise ValueError(f'题目{q.id}已发生变化：{key}')
                if args.apply:
                    kp=db.query(KnowledgePoint).filter(KnowledgePoint.subject_id==q.subject_id,KnowledgePoint.name==item['label'],KnowledgePoint.deleted==False).first()
                    if not kp:db.add(KnowledgePoint(subject_id=q.subject_id,name=item['label'],grade=q.grade,semester=None,deleted=False))
                    q.knowledge_point=item['label'];db.flush();db.refresh(q)
                    assert q.knowledge_point==item['label']
                    assert q.answer==original['answer'] and q.analysis==original['analysis'] and q.parsed_question==original['parsed_question']
            if not args.apply:db.rollback()
    print('已标注' if args.apply else '预检通过',len(plan['labels']),'道，暂缓',len(plan['skipped']),'道')
if __name__=='__main__':main()
