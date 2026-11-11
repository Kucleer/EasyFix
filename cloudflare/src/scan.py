"""整页识别录入的接口。"""

from fastapi import APIRouter, Request

import ocr_client
from scan_model import HEALTH_TIMEOUT_SECONDS, interpret_health

router = APIRouter()


@router.get('/api/scan/health')
async def health(request: Request):
    """识别主机是否可用；只返回 available，不透出主机的任何细节。"""
    status, body = await ocr_client.fetch_health(request.scope['env'], HEALTH_TIMEOUT_SECONDS)
    return {'available': interpret_health(status, body)}
