import os
import base64
import json
from typing import Optional
from app.config import get_settings

settings = get_settings()

# 检测可用的本地OCR
PADDLEOCR_AVAILABLE = False
TESSERACT_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PaddleOCR = None

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None


def load_config() -> dict:
    """从config/ocr.json加载配置"""
    config_file = "config/ocr.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            return json.load(f)
    return {}


class OCRService:
    """多OCR引擎支持服务"""

    def __init__(self):
        self._config = load_config()
        # 优先使用config文件中的配置，否则用环境变量
        self.provider = self._config.get("provider", settings.OCR_PROVIDER)
        self._init_provider()

    def _get_config(self, key: str, default: str = "") -> str:
        """获取配置，优先从config文件，否则从环境变量"""
        return self._config.get(key, getattr(settings, key, default))

    def _init_provider(self):
        if self.provider == "paddleocr" and PADDLEOCR_AVAILABLE:
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang="ch",
                use_gpu=False,
                show_log=False,
            )
            self._available = True
        elif self.provider == "tesseract" and TESSERACT_AVAILABLE:
            self._ocr = None
            self._available = True
        elif self.provider in ("baidu", "tencent"):
            self._available = True
        elif self.provider == "multimodal":
            from app.services.multimodal_ocr import multimodal_ocr_service
            self._multimodal = multimodal_ocr_service
            self._available = self._multimodal.is_available
        else:
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def recognize(self, image_path: str) -> dict:
        """
        识别图片中的文字

        Returns:
            dict: {
                "full_text": str,
                "blocks": list,
                "provider": str,
            }
        """
        # 重新加载配置（每次识别前）
        self._config = load_config()
        self.provider = self._config.get("provider", settings.OCR_PROVIDER)
        self._init_provider()

        if not self._available:
            return {
                "full_text": "",
                "blocks": [],
                "warning": f"OCR provider '{self.provider}' not configured",
                "provider": self.provider,
            }

        try:
            if self.provider == "paddleocr":
                return self._recognize_paddleocr(image_path)
            elif self.provider == "tesseract":
                return self._recognize_tesseract(image_path)
            elif self.provider == "baidu":
                return self._recognize_baidu(image_path)
            elif self.provider == "tencent":
                return self._recognize_tencent(image_path)
            elif self.provider == "multimodal":
                return self._recognize_multimodal(image_path)
            else:
                return {"full_text": "", "blocks": [], "error": "Unknown provider"}
        except Exception as e:
            return {"full_text": "", "blocks": [], "error": str(e), "provider": self.provider}

    def _recognize_paddleocr(self, image_path: str) -> dict:
        result = self._ocr.ocr(image_path, cls=True)
        if not result or not result[0]:
            return {"full_text": "", "blocks": [], "provider": "paddleocr"}

        blocks = []
        full_text_parts = []
        for line in result[0]:
            if line:
                text = line[1][0]
                confidence = line[1][1]
                blocks.append({"text": text, "confidence": confidence, "bbox": line[0]})
                full_text_parts.append(text)

        return {
            "full_text": "\n".join(full_text_parts),
            "blocks": blocks,
            "provider": "paddleocr",
        }

    def _recognize_tesseract(self, image_path: str) -> dict:
        from PIL import Image
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        return {
            "full_text": text,
            "blocks": [],
            "provider": "tesseract",
        }

    def _recognize_baidu(self, image_path: str) -> dict:
        """百度OCR"""
        import requests

        with open(image_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()

        url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
        access_token = self._get_baidu_access_token()

        payload = {'image': img_data}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        response = requests.post(
            url,
            params={'access_token': access_token},
            data=payload,
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()
            words = result.get('words_result', [])
            full_text = '\n'.join([w['words'] for w in words])
            return {
                "full_text": full_text,
                "blocks": [{"text": w['words'], "confidence": w.get('probability', 1)} for w in words],
                "provider": "baidu",
            }
        return {"full_text": "", "blocks": [], "error": "Baidu OCR failed", "provider": "baidu"}

    def _get_baidu_access_token(self) -> str:
        """获取百度OCR access_token"""
        import requests

        token_file = ".baidu_access_token"
        api_key = self._get_config("BAIDU_API_KEY", settings.BAIDU_API_KEY)
        secret_key = self._get_config("BAIDU_SECRET_KEY", settings.BAIDU_SECRET_KEY)

        if os.path.exists(token_file):
            with open(token_file) as f:
                return f.read().strip()

        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            'grant_type': 'client_credentials',
            'client_id': api_key,
            'client_secret': secret_key,
        }
        response = requests.post(url, params=params)
        if response.status_code == 200:
            result = response.json()
            token = result.get('access_token', '')
            with open(token_file, 'w') as f:
                f.write(token)
            return token
        return ""

    def _recognize_tencent(self, image_path: str) -> dict:
        """腾讯OCR"""
        import requests
        import hashlib
        import time

        with open(image_path, 'rb') as f:
            img_data = f.read()

        appid = self._get_config("TENCENT_APP_ID", settings.TENCENT_APP_ID)
        secret_id = self._get_config("TENCENT_SECRET_ID", settings.TENCENT_SECRET_ID)
        secret_key = self._get_config("TENCENT_SECRET_KEY", settings.TENCENT_SECRET_KEY)
        bucket = self._get_config("TENCENT_BUCKET", settings.TENCENT_BUCKET)

        url = f"https://{appid}.service.myqcloud.com/ocr/v1/general"

        expired = int(time.time()) + 3600
        fileid = "ocr/multipart"

        sign_str = f"a={appid}&k={secret_id}&e={expired}&t={int(time.time())}&r={123456}&f=&fileid={fileid}"
        sign = hashlib.sha1(sign_str.encode() + secret_key.encode()).hexdigest() + base64.b64encode(secret_key.encode()).decode()

        headers = {
            'Host': f'{appid}.service.myqcloud.com',
            'Content-Type': 'application/json',
            'Authorization': f'{sign}',
        }

        payload = {
            'appid': appid,
            'bucket': bucket,
            'file': base64.b64encode(img_data).decode(),
            'fileid': fileid,
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            result = response.json()
            items = result.get('data', {}).get('items', [])
            full_text = '\n'.join([item.get('itemstring', '') for item in items])
            return {
                "full_text": full_text,
                "blocks": [{"text": item.get('itemstring', '')} for item in items],
                "provider": "tencent",
            }
        return {"full_text": "", "blocks": [], "error": "Tencent OCR failed", "provider": "tencent"}

    def _recognize_multimodal(self, image_path: str) -> dict:
        """使用多模态模型进行OCR"""
        return self._multimodal.recognize(image_path)


# 全局单例
ocr_service = OCRService()
