from pydantic import BaseModel
from typing import List, Dict


class SubjectStats(BaseModel):
    subject_id: int
    subject_name: str
    question_count: int
    error_type_counts: dict = {}
    difficulty_distribution: dict = {}
    knowledge_point_counts: dict = {}
    practice_count: int = 0


class GradeStats(BaseModel):
    grade: int
    question_count: int
    difficulty_distribution: dict = {}


class SemesterStats(BaseModel):
    semester: int
    question_count: int
    difficulty_distribution: dict = {}


class WordStats(BaseModel):
    total_words: int = 0
    reviewed_words: int = 0
    total_reviews: int = 0
    accuracy: float = 0.0


class AccuracyCurvePoint(BaseModel):
    date: str
    accuracy: float


class StatsResponse(BaseModel):
    total_questions: int
    total_subjects: int
    total_error_books: int
    active_days: int = 0
    difficulty_distribution: dict = {}
    error_type_distribution: dict = {}
    by_subject: List[SubjectStats] = []
    by_grade: List[GradeStats] = []
    by_semester: List[SemesterStats] = []
    word_stats: WordStats = WordStats()
    word_accuracy_curve: List[AccuracyCurvePoint] = []
