"""打包现有只读统计算法，保留业务口径，不加载原应用入口。"""

from pathlib import Path


def main():
    """复制模型定义与只读统计模块，并改写隔离包内的引用。"""
    root = Path(__file__).resolve().parents[2]
    output = root / 'cloudflare/src/legacy'
    (output / 'models').mkdir(parents=True, exist_ok=True)
    mapping = {path: output / 'models' / path.name for path in (root / 'backend/app/models').glob('*.py')}
    mapping.update({root / 'backend/app/routers/stats.py': output / 'stats_routes.py',
                    root / 'backend/app/services/learning_analysis.py': output / 'learning_analysis.py',
                    root / 'backend/app/schemas/stats.py': output / 'stats_schema.py'})
    for source, destination in mapping.items():
        text = source.read_text(encoding='utf-8-sig').replace('app.models', 'legacy.models').replace('app.database', 'legacy.database').replace('app.services.learning_analysis', 'legacy.learning_analysis').replace('from app.schemas import', 'from legacy.stats_schema import')
        destination.write_text(text, encoding='utf-8')
    (output / '__init__.py').write_text('"""仅用于只读统计的现有算法。"""\n', encoding='utf-8')
    print('Prepared existing read-only analytics algorithms.')


if __name__ == '__main__':
    main()
