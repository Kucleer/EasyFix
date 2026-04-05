from app.schemas.question import (
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
    QuestionListResponse,
    QuestionBatchCreate,
    BatchCreateResponse,
)
from app.schemas.error_book import (
    ErrorBookCreate,
    ErrorBookUpdate,
    ErrorBookResponse,
    ErrorBookListResponse,
)
from app.schemas.stats import StatsResponse, SubjectStats, GradeStats, SemesterStats, WordStats, AccuracyCurvePoint, TodayStats, LearningOverview
from app.schemas.learning_report import (
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportListItem,
    ReportDetail,
    ReportListResponse,
)
from app.schemas.star import (
    StarActionBase,
    StarActionCreate,
    StarActionUpdate,
    StarActionResponse,
    StarBalanceResponse,
    StarRecordResponse,
)
from app.schemas.achievement import (
    AchievementBase,
    AchievementCreate,
    AchievementUpdate,
    AchievementResponse,
    AchievementProgressResponse,
)
from app.schemas.reward import (
    RewardBase,
    RewardCreate,
    RewardUpdate,
    RewardResponse,
    RedemptionResponse,
)

__all__ = [
    "QuestionCreate",
    "QuestionUpdate",
    "QuestionResponse",
    "QuestionListResponse",
    "QuestionBatchCreate",
    "BatchCreateResponse",
    "ErrorBookCreate",
    "ErrorBookUpdate",
    "ErrorBookResponse",
    "ErrorBookListResponse",
    "StatsResponse",
    "SubjectStats",
    "GradeStats",
    "SemesterStats",
    "WordStats",
    "AccuracyCurvePoint",
    "TodayStats",
    "LearningOverview",
    "ReportGenerateRequest",
    "ReportGenerateResponse",
    "ReportListItem",
    "ReportDetail",
    "ReportListResponse",
    # Star schemas
    "StarActionBase",
    "StarActionCreate",
    "StarActionUpdate",
    "StarActionResponse",
    "StarBalanceResponse",
    "StarRecordResponse",
    # Achievement schemas
    "AchievementBase",
    "AchievementCreate",
    "AchievementUpdate",
    "AchievementResponse",
    "AchievementProgressResponse",
    # Reward schemas
    "RewardBase",
    "RewardCreate",
    "RewardUpdate",
    "RewardResponse",
    "RedemptionResponse",
]
