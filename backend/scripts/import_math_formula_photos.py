"""按人工核对的图片题干导入正式数据；先校验备份、公式和原图，支持重复执行去重。"""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / 'scripts'))

# 第一张图片顶部题干被裁切，不补猜录入；C(1) 三个小问合并为一条。
QUESTIONS = [
    {
        'source': 0, 'label': '第14页 C层（1）', 'difficulty': 2,
        'question_text': r'计算：\(\left|\frac{1}{2}-1\right|\)；\(\left|\frac{1}{5}-\frac{1}{3}\right|\)；\(\left|\frac{1}{3}-\frac{1}{2}\right|\)。',
        'answer': r'依次为 \(\frac{1}{2}\)、\(\frac{2}{15}\)、\(\frac{1}{6}\)。',
        'analysis': r'先通分求差，再取绝对值：\(\left|-\frac{1}{2}\right|=\frac{1}{2}\)；\(\left|\frac{3-5}{15}\right|=\frac{2}{15}\)；\(\left|\frac{2-3}{6}\right|=\frac{1}{6}\)。原图三个小问均有批改勾，作为同组练习保留，不标记为学生错误。',
        'knowledge_point': '绝对值与分数运算', 'error_type': None,
    },
    {
        'source': 0, 'label': '第14页 C层（2）', 'difficulty': 3,
        'question_text': r'计算：\[\left|\frac{1}{2}-1\right|+\left|\frac{1}{3}-\frac{1}{2}\right|+\left|\frac{1}{4}-\frac{1}{3}\right|+\cdots+\left|\frac{1}{2026}-\frac{1}{2025}\right|\]',
        'answer': r'\(\frac{2025}{2026}\)。',
        'analysis': r'每个绝对值内均为负数，故 \(\left|\frac{1}{n+1}-\frac{1}{n}\right|=\frac{1}{n}-\frac{1}{n+1}\)。原式裂项相消，等于 \[\left(1-\frac{1}{2}\right)+\left(\frac{1}{2}-\frac{1}{3}\right)+\cdots+\left(\frac{1}{2025}-\frac{1}{2026}\right)=1-\frac{1}{2026}=\frac{2025}{2026}\]原图作答为1，遗漏了最后剩余的减项。',
        'knowledge_point': '绝对值与裂项求和', 'error_type': '计算',
    },
    {
        'source': 1, 'label': '绝对值条件与乘方', 'difficulty': 3,
        'question_text': r'已知有理数满足 \(|a-1|+|b+3|+|3c-1|=0\)，求 \((a\times b\times c)^{2026}\) 的值。',
        'answer': r'\(1\)。',
        'analysis': r'绝对值均非负，和为0时每一项都为0，因此 \(a=1\)、\(b=-3\)、\(c=\frac{1}{3}\)。于是 \(a\times b\times c=-1\)。2026为偶数，所以 \((-1)^{2026}=1\)。截图未展示完整作答，不推断学生错误类型。',
        'knowledge_point': '绝对值非负性与有理数乘方', 'error_type': None,
    },
]


def main():
    """完成只读预检后，在单一事务中去重导入三条题目和一个练习集。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-one', type=Path, required=True)
    parser.add_argument('--image-two', type=Path, required=True)
    parser.add_argument('--backup-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='不传时只验证，不写正式数据库')
    args = parser.parse_args()
    images = [args.image_one.resolve(), args.image_two.resolve()]
    backup = args.backup_dir.resolve()
    from backup_data import verify_backup
    verify_backup(backup)
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    if not all(image.is_file() for image in images):
        raise RuntimeError('原图不存在')
    os.chdir(BACKEND)
    from app.config import get_settings
    from app.services.math_pdf import generate_math_practice_pdf
    import psycopg2
    from psycopg2.extras import RealDictCursor
    settings = get_settings()
    if settings.DB_TYPE not in ('postgres', 'postgresql') or manifest['database'].get('database') != settings.DB_NAME:
        raise RuntimeError('备份数据库与当前 PostgreSQL 配置不一致')
    # 先以生产渲染器验证题干、答案、解析全部可排版，失败不入库。
    with tempfile.TemporaryDirectory() as directory:
        generate_math_practice_pdf('正式导入前公式校验', [dict(q, include_solution=True) for q in QUESTIONS], directory)
    if not args.apply:
        print('预检通过；加 --apply 才会写入正式数据库')
        return
    title = '数学·分数与乘方（2026-10-28图片整理）'
    output_root = BACKEND.parent / 'output/math-formula-import'
    output_root.mkdir(parents=True, exist_ok=True)
    image_paths = []
    for image in images:
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        relative = Path('2026/10') / f'{digest[:24]}_{image.suffix.lstrip(".")}{image.suffix.lower()}'
        destination = Path(settings.UPLOAD_DIR) / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise RuntimeError('图片目标路径存在不同内容')
        if not destination.exists():
            shutil.copy2(image, destination)
        image_paths.append(relative.as_posix())
    connection = psycopg2.connect(host=settings.DB_HOST, port=settings.DB_PORT, user=settings.DB_USER,
                                  password=settings.DB_PASSWORD, dbname=settings.DB_NAME, connect_timeout=15)
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # 防止同一批脚本并发运行造成重复导入，不改变其他业务事务。
                cursor.execute('SELECT pg_advisory_xact_lock(%s)', (2026102801,))
                cursor.execute('SELECT id FROM subject WHERE name=%s AND deleted=false ORDER BY id', ('数学',))
                subject = cursor.fetchone()
                if not subject:
                    raise RuntimeError('未找到有效数学学科')
                subject_id = subject['id']
                cursor.execute('SELECT id FROM error_book WHERE name=%s AND deleted=false', (title,))
                book = cursor.fetchone()
                if book:
                    book_id = book['id']
                else:
                    cursor.execute('INSERT INTO error_book (name,subject_id,description,original_images,deleted) VALUES (%s,%s,%s,%s,false) RETURNING id',
                                   (title, subject_id, '用户授权的两张正式图片；保留原图，顶部裁切题目不录入。', json.dumps(image_paths)))
                    book_id = cursor.fetchone()['id']
                ids = []
                inserted = []
                for question in QUESTIONS:
                    cursor.execute('SELECT id,answer,analysis FROM question WHERE subject_id=%s AND parsed_question=%s AND deleted=false ORDER BY id',
                                   (subject_id, question['question_text']))
                    existing = cursor.fetchone()
                    if existing:
                        question_id = existing['id']
                        if existing['answer'] != question['answer'] or existing['analysis'] != question['analysis']:
                            raise RuntimeError('同题已有不同答案或解析，需要人工检查，不覆盖')
                    else:
                        image = image_paths[question['source']]
                        cursor.execute('''INSERT INTO question
                            (error_book_id,subject_id,original_image,original_images,original_text,parsed_question,answer,analysis,
                             grade,semester,difficulty,error_type,knowledge_point,review_count,correct_count,error_count,deleted)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,%s,%s,%s,0,0,0,false) RETURNING id''',
                            (book_id, subject_id, image, json.dumps([image]), question['question_text'], question['question_text'],
                             question['answer'], question['analysis'], question['difficulty'], question['error_type'], question['knowledge_point']))
                        question_id = cursor.fetchone()['id']
                        inserted.append(question_id)
                    cursor.execute('SELECT parsed_question,answer,analysis FROM question WHERE id=%s AND deleted=false', (question_id,))
                    readback = cursor.fetchone()
                    if (readback['parsed_question'], readback['answer'], readback['analysis']) != (question['question_text'], question['answer'], question['analysis']):
                        raise RuntimeError('公式入库回读不一致')
                    ids.append(question_id)
                cursor.execute('SELECT id FROM practice_set WHERE name=%s AND subject_id=%s AND deleted=false', (title, subject_id))
                practice = cursor.fetchone()
                if practice:
                    practice_id = practice['id']
                else:
                    cursor.execute('''INSERT INTO practice_set
                        (name,subject_id,source_type,question_type,total_questions,reviewed,review_count,deleted,notes)
                        VALUES (%s,%s,'question','original',%s,false,0,false,%s) RETURNING id''',
                        (title, subject_id, len(ids), '两张正式图片：第14页C层两题及绝对值乘方题；未展示年级，不推断。'))
                    practice_id = cursor.fetchone()['id']
                    for order, question_id in enumerate(ids):
                        cursor.execute('INSERT INTO practice_set_question (practice_set_id,question_id,display_order) VALUES (%s,%s,%s)',
                                       (practice_id, question_id, order))
        report = {'created_at': datetime.now().isoformat(), 'question_ids': ids, 'inserted_question_ids': inserted,
                  'error_book_id': book_id, 'practice_set_id': practice_id, 'images': image_paths,
                  'backup_directory': str(backup), 'formula_roundtrip': True}
        (output_root / 'import-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        connection.close()


if __name__ == '__main__':
    main()
