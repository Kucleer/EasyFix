from pydantic import BaseModel
from typing import List, Dict


class SubjectStats(BaseModel):
    subject_id: int
    subject_name: str
    question_count: int
    error_type_counts: dict = {}
    difficulty_distribution: dict = {}


class GradeStats(BaseModel):
    grade: int
    question_count: int
    difficulty_distribution: dict = {}


class SemesterStats(BaseModel):
    semester: int
    question_count: int
    difficulty_distribution: dict = {}


class StatsResponse(BaseModel):
    total_questions: int
    total_subjects: int
    total_error_books: int
    difficulty_distribution: dict = {}
    error_type_distribution: dict = {}
    by_subject: List[SubjectStats] = []
    by_grade: List[GradeStats] = []
    by_semester: List[SemesterStats] = []
