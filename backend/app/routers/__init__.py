from app.routers.question import router as question_router
from app.routers.upload import router as upload_router
from app.routers.stats import router as stats_router
from app.routers.similar import router as similar_router
from app.routers.config import router as config_router
from app.routers.error_book import router as error_book_router
from app.routers.subject import router as subject_router
from app.routers.tag import router as tag_router
from app.routers.knowledge_point import router as knowledge_point_router
from app.routers.practice_set import router as practice_set_router

__all__ = [
    "question_router",
    "upload_router",
    "stats_router",
    "similar_router",
    "config_router",
    "error_book_router",
    "subject_router",
    "tag_router",
    "knowledge_point_router",
    "practice_set_router",
]
