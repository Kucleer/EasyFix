"""学习分析服务 - 数据聚合"""
import re
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer
from app.models import Question, Subject, Word, WordReviewLog, PracticeSet, PracticeSetQuestion, KnowledgePoint
from app.models.tag import Tag
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import Counter

class LearningAnalysisService:
    def __init__(self, db: Session, subject_id=None):
        """按指定学科汇总，未选择时保留各知识点的学科身份。"""
        self.db = db
        self.subject_id = subject_id

    def get_full_stats(self) -> Dict[str, Any]:
        """获取完整学习统计数据"""
        return {
            "question_stats": self._get_question_stats(),
            "word_stats": self._get_word_stats(),
            "practice_stats": self._get_practice_stats(),
            "knowledge_graph": self._get_knowledge_graph(),
        }

    def _get_question_stats(self) -> Dict[str, Any]:
        """获取错题统计，使用数据库聚合避免加载所有记录"""
        try:
            # 使用数据库聚合计算总数
            total = self.db.query(func.count(Question.id)).filter(Question.deleted == False, (Question.subject_id == self.subject_id if self.subject_id is not None else True)).scalar() or 0

            # 难度分布 - 使用数据库分组聚合
            difficulty_results = (
                self.db.query(
                    Question.difficulty,
                    func.count(Question.id)
                )
                .filter(Question.deleted == False, (Question.subject_id == self.subject_id if self.subject_id is not None else True), Question.difficulty.isnot(None))
                .group_by(Question.difficulty)
                .all()
            )
            by_difficulty = {d.difficulty: d[1] for d in difficulty_results}

            # 错误类型分布 - 使用数据库分组聚合
            # 注意：错误类型存储为逗号分隔的字符串，需要在应用层拆分
            error_type_results = (
                self.db.query(Question.error_type)
                .filter(Question.deleted == False, (Question.subject_id == self.subject_id if self.subject_id is not None else True), Question.error_type.isnot(None))
                .all()
            )
            error_types = Counter()
            for row in error_type_results:
                if row.error_type:
                    for et in row.error_type.split(','):
                        et = et.strip()
                        if et:
                            error_types[et] += 1

            # 知识点错误排行 - 使用数据库分组聚合
            kp_results = (
                self.db.query(
                    Question.knowledge_point, Question.subject_id,
                    func.count(Question.id)
                )
                .filter(Question.deleted == False, (Question.subject_id == self.subject_id if self.subject_id is not None else True), Question.knowledge_point.isnot(None))
                .group_by(Question.subject_id, Question.knowledge_point)
                .order_by(func.count(Question.id).desc())
                .all()
            )
            subject_map = {subject.id: subject.name for subject in self.db.query(Subject).filter(Subject.deleted == False).all()}
            top_kp = [{"point": kp[0], "subject_id": kp[1], "subject_name": subject_map.get(kp[1], "未知学科"), "count": kp[2]} for kp in kp_results]

            # 复习效果 - 使用数据库聚合
            not_reviewed = (
                self.db.query(func.count(Question.id))
                .filter(Question.deleted == False, (Question.subject_id == self.subject_id if self.subject_id is not None else True), (Question.review_count == 0) | (Question.review_count.is_(None)))
                .scalar() or 0
            )
            reviewed_once = (
                self.db.query(func.count(Question.id))
                .filter(Question.deleted == False, (Question.subject_id == self.subject_id if self.subject_id is not None else True), Question.review_count == 1)
                .scalar() or 0
            )
            reviewed_multiple = (
                self.db.query(func.count(Question.id))
                .filter(Question.deleted == False, (Question.subject_id == self.subject_id if self.subject_id is not None else True), Question.review_count > 1)
                .scalar() or 0
            )

            # 正确率趋势
            accuracy_trend = self._get_question_accuracy_trend()

            return {
                "total": total,
                "by_difficulty": by_difficulty,
                "by_error_type": dict(error_types),
                "top_error_knowledge_points": top_kp,
                "review_effectiveness": {
                    "not_reviewed": not_reviewed,
                    "reviewed_once": reviewed_once,
                    "reviewed_multiple": reviewed_multiple,
                },
                "accuracy_trend": accuracy_trend,
            }
        except Exception as e:
            # 错误处理：返回空数据而不是崩溃
            return {
                "total": 0,
                "by_difficulty": {},
                "by_error_type": {},
                "top_error_knowledge_points": [],
                "review_effectiveness": {
                    "not_reviewed": 0,
                    "reviewed_once": 0,
                    "reviewed_multiple": 0,
                },
                "accuracy_trend": [],
            }

    def _get_question_accuracy_trend(self) -> List[Dict]:
        """获取错题正确率趋势"""
        try:
            logs = (
                self.db.query(
                    func.date(PracticeSet.created_at).label('date'),
                    func.sum(func.cast(PracticeSetQuestion.is_correct, Integer)).label('correct'),
                    func.count(PracticeSetQuestion.id).label('total')
                )
                .join(PracticeSet, PracticeSet.id == PracticeSetQuestion.practice_set_id)
                .filter(
                    PracticeSet.deleted == False, (PracticeSet.subject_id == self.subject_id if self.subject_id is not None else True),
                    PracticeSet.source_type == 'question',
                    PracticeSet.reviewed == True,
                    PracticeSetQuestion.is_correct.isnot(None)
                )
                .group_by(func.date(PracticeSet.created_at))
                .order_by(func.date(PracticeSet.created_at))
                .all()
            )

            cumulative_correct = 0
            cumulative_total = 0
            trend = []
            for log in logs:
                cumulative_correct += log.correct or 0
                cumulative_total += log.total or 0
                accuracy = round(cumulative_correct / cumulative_total * 100, 1) if cumulative_total > 0 else 0
                trend.append({
                    "date": log.date.strftime('%Y-%m-%d') if hasattr(log.date, 'strftime') else str(log.date),
                    "accuracy": accuracy
                })
            return trend
        except Exception:
            return []

    def _get_word_stats(self) -> Dict[str, Any]:
        """获取单词统计，使用数据库聚合避免加载所有记录"""
        try:
            if self.subject_id is not None:
                subject = self.db.query(Subject).filter(Subject.id == self.subject_id, Subject.deleted == False).first()
                if not subject or "英" not in subject.name:
                    return {"total": 0, "mastery_distribution": {}, "low_accuracy_words": [], "memory_curve_status": {}, "frequency_trend": []}
            # 使用数据库聚合计算总数
            total = self.db.query(func.count(Word.id)).filter(Word.deleted == False).scalar() or 0

            # 掌握分布 - 使用数据库聚合
            unmastered = (
                self.db.query(func.count(Word.id))
                .filter(Word.deleted == False, (Word.review_count == 0) | (Word.review_count.is_(None)))
                .scalar() or 0
            )
            learning = (
                self.db.query(func.count(Word.id))
                .filter(Word.deleted == False, Word.review_count > 0, Word.review_count <= 3)
                .scalar() or 0
            )
            mastered = (
                self.db.query(func.count(Word.id))
                .filter(Word.deleted == False, Word.review_count > 3)
                .scalar() or 0
            )

            # 低准确率单词 - 使用数据库查询过滤
            low_acc_query = (
                self.db.query(Word.english, Word.correct_count, Word.review_count)
                .filter(
                    Word.deleted == False,
                    Word.review_count > 0,
                    Word.correct_count.isnot(None)
                )
                .all()
            )
            low_acc = []
            for w in low_acc_query:
                acc = w.correct_count / w.review_count * 100
                if acc < 70:
                    low_acc.append({"word": w.english, "accuracy": round(acc, 1)})

            # 记忆曲线状态 - 使用数据库聚合
            now = datetime.now()
            due_review = (
                self.db.query(func.count(Word.id))
                .filter(Word.deleted == False, Word.next_review_at.isnot(None), Word.next_review_at <= now)
                .scalar() or 0
            )
            on_track = total - due_review

            # 复习频率趋势
            frequency = self._get_word_frequency_trend()

            return {
                "total": total,
                "mastery_distribution": {
                    "unmastered": unmastered,
                    "learning": learning,
                    "mastered": mastered,
                },
                "low_accuracy_words": low_acc[:20],
                "memory_curve_status": {
                    "due_review": due_review,
                    "on_track": on_track,
                },
                "frequency_trend": frequency,
            }
        except Exception as e:
            # 错误处理：返回空数据而不是崩溃
            return {
                "total": 0,
                "mastery_distribution": {
                    "unmastered": 0,
                    "learning": 0,
                    "mastered": 0,
                },
                "low_accuracy_words": [],
                "memory_curve_status": {
                    "due_review": 0,
                    "on_track": 0,
                },
                "frequency_trend": [],
            }

    def _get_word_frequency_trend(self) -> List[Dict]:
        """获取单词复习频率趋势"""
        try:
            logs = (
                self.db.query(
                    func.date(WordReviewLog.reviewed_at).label('date'),
                    func.count(WordReviewLog.id).label('count')
                )
                .filter(WordReviewLog.deleted == False)
                .group_by(func.date(WordReviewLog.reviewed_at))
                .order_by(func.date(WordReviewLog.reviewed_at))
                .all()
            )
            return [
                {"date": log.date.strftime('%Y-%m-%d') if hasattr(log.date, 'strftime') else str(log.date), "count": log.count}
                for log in logs
            ]
        except Exception:
            return []

    def _get_practice_stats(self) -> Dict[str, Any]:
        """获取练习统计，使用数据库聚合避免加载所有记录"""
        try:
            # 使用数据库聚合计算总数
            total_practices = (
                self.db.query(func.count(PracticeSet.id))
                .filter(PracticeSet.deleted == False, (PracticeSet.subject_id == self.subject_id if self.subject_id is not None else True))
                .scalar() or 0
            )

            # 频率热力图（按星期）- 使用数据库分组聚合
            # 使用 func.extract('dow', ...) 获取星期几，0=周日, 1=周一, ..., 6=周六
            weekday_results = (
                self.db.query(
                    func.extract('dow', PracticeSet.created_at).label('dow'),
                    func.count(PracticeSet.id)
                )
                .filter(PracticeSet.deleted == False, (PracticeSet.subject_id == self.subject_id if self.subject_id is not None else True))
                .group_by(func.extract('dow', PracticeSet.created_at))
                .all()
            )
            # 映射数字星期到星期名称
            weekday_names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
            weekday_counts = {}
            for r in weekday_results:
                dow = int(r.dow) if r.dow is not None else 0
                weekday_counts[weekday_names[dow]] = r[1]

            # 正确率趋势
            accuracy_trend = self._get_practice_accuracy_trend()

            return {
                "total_practices": total_practices,
                "frequency_heatmap": weekday_counts,
                "accuracy_trend": accuracy_trend,
            }
        except Exception as e:
            # 错误处理：返回空数据而不是崩溃
            return {
                "total_practices": 0,
                "frequency_heatmap": {},
                "accuracy_trend": [],
            }

    def _get_practice_accuracy_trend(self) -> List[Dict]:
        """获取练习正确率趋势"""
        try:
            from app.models import WordReview
            sessions = (
                self.db.query(WordReview)
                .order_by(WordReview.reviewed_at)
                .all()
            )

            cumulative_correct = 0
            cumulative_total = 0
            trend = []
            for s in sessions:
                cumulative_correct += s.correct_count or 0
                cumulative_total += s.total_count or 0
                accuracy = round(cumulative_correct / cumulative_total * 100, 1) if cumulative_total > 0 else 0
                trend.append({
                    "date": s.reviewed_at.strftime('%Y-%m-%d') if hasattr(s.reviewed_at, 'strftime') else str(s.reviewed_at),
                    "accuracy": accuracy
                })
            return trend
        except Exception:
            return []

    def _get_knowledge_graph(self) -> Dict[str, Any]:
        """获取知识点关联图，使用数据库聚合避免加载所有记录"""
        try:
            nodes = []
            edges = []

            # 获取知识点及其错误次数（使用数据库分组聚合）
            kp_error_results = (
                self.db.query(
                    KnowledgePoint.id,
                    KnowledgePoint.name,
                    KnowledgePoint.subject_id,
                    func.count(Question.id).label('error_count')
                )
                .outerjoin(Question, (KnowledgePoint.name == Question.knowledge_point) & (KnowledgePoint.subject_id == Question.subject_id) & (Question.deleted == False))
                .filter(KnowledgePoint.deleted == False, (KnowledgePoint.subject_id == self.subject_id if self.subject_id is not None else True))
                .group_by(KnowledgePoint.id, KnowledgePoint.name, KnowledgePoint.subject_id)
                .all()
            )

            # 构建节点
            for kp in kp_error_results:
                nodes.append({
                    "id": str(kp.id),
                    "name": kp.name,
                    "error_count": kp.error_count or 0,
                    "category": kp.subject_id or 0
                })

            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            # 错误处理：返回空数据而不是崩溃
            return {"nodes": [], "edges": []}

    def analyze_with_llm(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """使用LLM分析学习数据，生成结构化建议"""
        from app.services.llm import LLMService

        prompt = self._build_analysis_prompt(stats)

        llm = LLMService()
        try:
            response = llm.analyze_learning_data(prompt)
            return self._parse_llm_response(response)
        except Exception as e:
            return {"error": str(e)}

    def _build_analysis_prompt(self, stats: Dict[str, Any]) -> str:
        """构建分析提示词"""
        q = stats.get("question_stats", {})
        w = stats.get("word_stats", {})
        p = stats.get("practice_stats", {})

        prompt = f"""基于以下学习数据，生成结构化分析报告：

## 错题统计
- 总数: {q.get('total', 0)}
- 难度分布: {q.get('by_difficulty', {})}
- 错误类型: {q.get('by_error_type', {})}
- 高频错误知识点: {q.get('top_error_knowledge_points', [])}
- 复习效果: 未复习{q.get('review_effectiveness', {}).get('not_reviewed', 0)}题, 已复习多次{q.get('review_effectiveness', {}).get('reviewed_multiple', 0)}题

## 单词统计
- 总数: {w.get('total', 0)}
- 掌握分布: 未掌握{w.get('mastery_distribution', {}).get('unmastered', 0)}, 学习中{w.get('mastery_distribution', {}).get('learning', 0)}, 已牢记{w.get('mastery_distribution', {}).get('mastered', 0)}
- 待复习: {w.get('memory_curve_status', {}).get('due_review', 0)}个
- 低准确率单词: {w.get('low_accuracy_words', [])[:5]}

## 练习统计
- 总练习次数: {p.get('total_practices', 0)}
- 周频率: {p.get('frequency_heatmap', {})}

请生成JSON格式的分析报告，包含：
{{
  "weak_points": [{{"point": "知识点名", "reason": "原因分析", "suggestion": "改进建议"}}],  // TOP3薄弱点
  "trends": {{"pattern": "趋势描述", "cause": "原因分析", "prediction": "趋势预测"}},
  "suggestions": [{{"type": "练习|记忆|复习|策略", "content": "建议内容", "priority": 1-3}}],  // 3-5条建议
  "learning_plan": {{"daily_time": "每日建议时长", "focus_areas": ["重点领域"], "priority_order": ["优先级排序"]}}
}}

只返回JSON，不要其他内容。"""
        return prompt

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        import json

        # 提取JSON
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return {"error": "解析失败", "raw": response}
        return {"error": "未找到JSON", "raw": response}