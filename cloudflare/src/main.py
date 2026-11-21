"""EasyFix 的 Cloudflare 入口；接口适配期间默认不开放公共路由。"""

import hmac
import json
from fastapi import FastAPI, Request, Query
from workers import asgi
from auth import guard, router as auth_router
from catalog import router as catalog_router
from knowledge import router as knowledge_router
from scan import router as scan_router
from questions import router as questions_router
from word_focus import router as word_focus_router
from words import router as words_router
from readings import router as readings_router
from settings import router as settings_router
from analytics import router as analytics_router
from motivation import router as motivation_router
from targeted import router as targeted_router
from grading_scan import router as grading_scan_router
from practices import router as practices_router
from review import router as review_router
from reports import router as reports_router
from intake import router as intake_router
from papers import router as papers_router
from similar import router as similar_router
from starmap import router as starmap_router
from media import router as media_router
from weekly import router as weekly_router, run_scheduled

app = FastAPI(title='EasyFix Cloudflare', docs_url=None, redoc_url=None, openapi_url=None)


class Default(asgi.entrypoint(app)):
    """后端入口：HTTP 请求原样继承 asgi.entrypoint(app) 生成的 fetch，只多一个定时入口。"""

    async def scheduled(self, controller, env, ctx):
        """Cron 触发（wrangler.jsonc 的 triggers.crons）：把最近一期周报推进一步，打印一行日志。"""
        # 用 self.env：和 HTTP 请求拿到的是同一个包装过的 env（D1 绑定由运行时转换参数）
        await run_scheduled(self.env)


app.middleware('http')(guard)
app.include_router(auth_router)
app.include_router(motivation_router)
# 考点卷的固定路径 /api/practice-sets/targeted/... 要排在练习集的 /{practice_set_id} 之前
app.include_router(targeted_router)
app.include_router(grading_scan_router)
app.include_router(practices_router)
app.include_router(review_router)
app.include_router(reports_router)
app.include_router(intake_router)
app.include_router(papers_router)
app.include_router(similar_router)
app.include_router(starmap_router)
app.include_router(media_router)
app.include_router(weekly_router)
app.include_router(catalog_router)
app.include_router(knowledge_router)
app.include_router(scan_router)
app.include_router(questions_router)
app.include_router(word_focus_router)
app.include_router(words_router)
app.include_router(readings_router)
app.include_router(settings_router)
app.include_router(analytics_router)


@app.get('/health')
async def health(request: Request):
    """提供不包含业务数据的存活检查。"""
    return {'status': 'ok', 'service': 'easyfix', 'migration_complete': str(getattr(request.scope['env'], 'MIGRATION_READY', '')).lower() == 'true'}
