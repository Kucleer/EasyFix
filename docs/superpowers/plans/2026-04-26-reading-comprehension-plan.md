# 英语阅读理解功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现英语阅读理解题型，支持LLM生成短文与选择题、短文库管理、基于短文的练习集测试

**Architecture:** 后端新建ReadingPassage和ReadingQuestion表存储短文与选择题，新建reading_router处理短文CRUD和LLM生成，扩展PracticeSet支持source_type=reading；前端新增独立/reading路由和阅读理解测试视图

**Tech Stack:** FastAPI + SQLAlchemy + Vue 3 + Element Plus + Anthropic SDK

---

## 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `backend/app/models/reading.py` | ReadingPassage 和 ReadingQuestion ORM 模型 |
| `backend/app/schemas/reading.py` | 阅读理解相关的 Pydantic 请求/响应模型 |
| `backend/app/routers/reading.py` | 短文CRUD、LLM生成、话题列表 API |
| `frontend/src/views/Reading.vue` | 阅读理解入口页（短文库列表 + 详情 + 生成弹窗） |
| `frontend/src/views/ReadingTest.vue` | 阅读理解练习测试页（同屏展示短文+选择题） |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `backend/app/models/practice_set.py` | PracticeSet 增加 passage_id 字段 |
| `backend/app/models/__init__.py` | 导入 ReadingPassage, ReadingQuestion |
| `backend/app/schemas/__init__.py` | 导入 reading schemas |
| `backend/app/routers/__init__.py` | 导入 reading_router |
| `backend/app/main.py` | 注册 reading_router |
| `backend/app/routers/practice_set.py` | 扩展 mark_reviewed 支持 reading 类型；新增 generate-from-reading 端点 |
| `frontend/src/router/index.js` | 新增 /reading 和 /reading-test 路由 |
| `frontend/src/App.vue` | 导航栏新增「阅读」菜单项 |
| `frontend/src/views/PracticeSets.vue` | 列表显示和进入阅读测试的入口 |

---

### Task 1: 创建 ReadingPassage 和 ReadingQuestion 数据模型

**Files:**
- Create: `backend/app/models/reading.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建 reading.py 模型文件**

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Boolean
from app.database import Base


class ReadingPassage(Base):
    """英语阅读理解短文库"""
    __tablename__ = "reading_passage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="短文标题")
    content = Column(Text, nullable=False, comment="英文短文内容")
    topic = Column(String(100), nullable=False, comment="话题主题")
    grade = Column(Integer, nullable=False, comment="适用年级 1-12")
    difficulty = Column(Integer, nullable=False, default=3, comment="难度 1-5")
    word_count = Column(Integer, nullable=True, comment="词数")
    source = Column(String(50), default="generated", comment="来源：generated/manual")
    deleted = Column(Boolean, default=False, nullable=False, comment="软删除标记")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)

    # Relationships
    questions = relationship("ReadingQuestion", back_populates="passage", cascade="all, delete-orphan")


class ReadingQuestion(Base):
    """阅读理解选择题"""
    __tablename__ = "reading_question"

    id = Column(Integer, primary_key=True, autoincrement=True)
    passage_id = Column(Integer, ForeignKey("reading_passage.id"), nullable=False, comment="关联短文ID")
    question_number = Column(Integer, nullable=False, comment="题号 1-4")
    question_text = Column(Text, nullable=False, comment="英文题目")
    option_a = Column(String(500), nullable=False, comment="选项A")
    option_b = Column(String(500), nullable=False, comment="选项B")
    option_c = Column(String(500), nullable=False, comment="选项C")
    option_d = Column(String(500), nullable=False, comment="选项D")
    correct_answer = Column(String(1), nullable=False, comment="正确答案 A/B/C/D")
    explanation = Column(Text, nullable=True, comment="解析")
    deleted = Column(Boolean, default=False, nullable=False, comment="软删除标记")
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    passage = relationship("ReadingPassage", back_populates="questions")
```

- [ ] **Step 2: 更新 models/__init__.py 导入新模型**

```python
# 在文件末尾的导入列表中添加
from app.models.reading import ReadingPassage, ReadingQuestion

# 在 __all__ 列表中添加
"ReadingPassage",
"ReadingQuestion",
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/reading.py backend/app/models/__init__.py
git commit -m "feat(reading): add ReadingPassage and ReadingQuestion models"
```

---

### Task 2: 扩展 PracticeSet 模型支持 passage_id

**Files:**
- Modify: `backend/app/models/practice_set.py`

- [ ] **Step 1: 为 PracticeSet 添加 passage_id 字段**

在 `class PracticeSet(Base):` 中，在 `review_images` 字段之后添加：

```python
    passage_id = Column(Integer, ForeignKey("reading_passage.id"), nullable=True, comment="关联短文ID（阅读理解练习集使用）")
```

并在 imports 确保 ForeignKey 已导入。

- [ ] **Step 2: 提交**

```bash
git add backend/app/models/practice_set.py
git commit -m "feat(reading): add passage_id field to PracticeSet model"
```

---

### Task 3: 创建阅读理解 Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/reading.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 创建 schemas/reading.py**

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ReadingQuestionBase(BaseModel):
    question_number: int = Field(..., ge=1, le=4)
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str = Field(..., pattern=r"^[A-D]$")
    explanation: Optional[str] = None


class ReadingQuestionCreate(ReadingQuestionBase):
    pass


class ReadingQuestionResponse(ReadingQuestionBase):
    id: int
    passage_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReadingPassageBase(BaseModel):
    title: str
    content: str
    topic: str
    grade: int = Field(..., ge=1, le=12)
    difficulty: int = Field(default=3, ge=1, le=5)
    word_count: Optional[int] = None
    source: str = "generated"


class ReadingPassageCreate(ReadingPassageBase):
    questions: List[ReadingQuestionCreate]


class ReadingPassageUpdate(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)


class ReadingPassageResponse(ReadingPassageBase):
    id: int
    word_count: Optional[int] = None
    source: str
    deleted: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    questions: List[ReadingQuestionResponse] = []

    class Config:
        from_attributes = True


class ReadingPassageListResponse(BaseModel):
    total: int
    items: List[ReadingPassageResponse]


class GenerateReadingRequest(BaseModel):
    grade: int = Field(..., ge=1, le=12)
    topic: str
    difficulty: int = Field(default=3, ge=1, le=5)


class ReadingGenerateResponse(BaseModel):
    passage: ReadingPassageResponse
    message: str = "生成成功"
```

- [ ] **Step 2: 更新 schemas/__init__.py**

```python
# 添加到导入
from app.schemas.reading import (
    ReadingPassageCreate,
    ReadingPassageUpdate,
    ReadingPassageResponse,
    ReadingPassageListResponse,
    ReadingQuestionCreate,
    ReadingQuestionResponse,
    GenerateReadingRequest,
    ReadingGenerateResponse,
)

# 添加到 __all__
"ReadingPassageCreate",
"ReadingPassageUpdate",
"ReadingPassageResponse",
"ReadingPassageListResponse",
"ReadingQuestionCreate",
"ReadingQuestionResponse",
"GenerateReadingRequest",
"ReadingGenerateResponse",
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/schemas/reading.py backend/app/schemas/__init__.py
git commit -m "feat(reading): add reading schemas"
```

---

### Task 4: 创建阅读理解 API 路由

**Files:**
- Create: `backend/app/routers/reading.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 routers/reading.py**

```python
"""
阅读理解路由 - 短文库管理、LLM生成、话题列表
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from app.database import get_db
from app.models import ReadingPassage, ReadingQuestion, PracticeSet
from app.schemas.reading import (
    ReadingPassageCreate,
    ReadingPassageUpdate,
    ReadingPassageResponse,
    ReadingPassageListResponse,
    ReadingQuestionCreate,
    ReadingQuestionResponse,
    GenerateReadingRequest,
)
from app.services.logger import logger_service

router = APIRouter(prefix="/api/readings", tags=["阅读理解"])

# 预设话题列表
TOPICS = [
    "校园生活", "家庭生活", "日常生活", "兴趣爱好",
    "科技发展", "环境保护", "文化艺术", "体育运动",
    "健康与医疗", "旅行与地理", "节日与习俗", "历史人物",
    "未来职业", "人际交往", "饮食文化", "动物与自然",
]

DIFFICULTY_WORD_RANGES = {
    1: (80, 120),
    2: (120, 180),
    3: (180, 250),
    4: (250, 320),
    5: (320, 400),
}


@router.get("/topics", response_model=list)
def get_topics():
    """获取可选话题列表"""
    return TOPICS


@router.get("", response_model=ReadingPassageListResponse)
def list_readings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    topic: Optional[str] = None,
    grade: Optional[int] = Query(None, ge=1, le=12),
    difficulty: Optional[int] = Query(None, ge=1, le=5),
    db: Session = Depends(get_db),
):
    """获取短文列表（支持筛选）"""
    query = db.query(ReadingPassage).filter(ReadingPassage.deleted == False).options(
        joinedload(ReadingPassage.questions)
    )

    if topic:
        query = query.filter(ReadingPassage.topic == topic)
    if grade:
        query = query.filter(ReadingPassage.grade == grade)
    if difficulty:
        query = query.filter(ReadingPassage.difficulty == difficulty)

    total = query.count()
    items = query.order_by(ReadingPassage.created_at.desc()).offset(skip).limit(limit).all()

    return {"total": total, "items": items}


@router.get("/{reading_id}", response_model=ReadingPassageResponse)
def get_reading(reading_id: int, db: Session = Depends(get_db)):
    """获取短文详情（含选择题）"""
    passage = db.query(ReadingPassage).options(
        joinedload(ReadingPassage.questions)
    ).filter(
        ReadingPassage.id == reading_id,
        ReadingPassage.deleted == False
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="短文不存在")

    return passage


@router.post("", response_model=ReadingPassageResponse, status_code=201)
def create_reading(data: ReadingPassageCreate, db: Session = Depends(get_db)):
    """手动创建短文 + 选择题"""
    passage = ReadingPassage(
        title=data.title,
        content=data.content,
        topic=data.topic,
        grade=data.grade,
        difficulty=data.difficulty,
        word_count=data.word_count or len(data.content.split()),
        source="manual",
    )
    db.add(passage)
    db.flush()

    for q in data.questions:
        question = ReadingQuestion(
            passage_id=passage.id,
            question_number=q.question_number,
            question_text=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            correct_answer=q.correct_answer,
            explanation=q.explanation,
        )
        db.add(question)

    db.commit()
    db.refresh(passage)

    return passage


@router.put("/{reading_id}", response_model=ReadingPassageResponse)
def update_reading(reading_id: int, data: ReadingPassageUpdate, db: Session = Depends(get_db)):
    """更新短文信息（标题、话题、年级、难度）"""
    passage = db.query(ReadingPassage).filter(
        ReadingPassage.id == reading_id,
        ReadingPassage.deleted == False
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="短文不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(passage, key, value)

    db.commit()
    db.refresh(passage)

    return passage


@router.delete("/{reading_id}", status_code=204)
def delete_reading(reading_id: int, db: Session = Depends(get_db)):
    """软删除短文"""
    passage = db.query(ReadingPassage).filter(
        ReadingPassage.id == reading_id,
        ReadingPassage.deleted == False
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="短文不存在")

    passage.deleted = True
    db.commit()
```

- [ ] **Step 2: 更新 routers/__init__.py**

```python
# 在导入列表中追加
from app.routers.reading import router as reading_router

# 在 __all__ 中追加
"reading_router",
```

- [ ] **Step 3: 更新 main.py 注册路由**

在 `app.include_router(motivation_router)` 之后添加：

```python
app.include_router(reading_router)
```

确保在 `from app.routers import ...` 中也导入 `reading_router`。

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/reading.py backend/app/routers/__init__.py backend/app/main.py
git commit -m "feat(reading): add reading CRUD API router"
```

---

### Task 5: 实现 LLM 生成短文和选择题

**Files:**
- Modify: `backend/app/services/llm.py`
- Modify: `backend/app/routers/reading.py`

- [ ] **Step 1: 在 llm.py 中添加短文生成和选择题生成方法**

```python
    def generate_reading_passage(self, grade: int, topic: str, difficulty: int) -> dict:
        """
        生成英语阅读理解短文

        Returns:
            dict: {"title": str, "content": str, "word_count": int}
        """
        self._config = load_llm_config()
        self._init_client()

        api_key = self._get_config("api_key", settings.ANTHROPIC_API_KEY)
        if not api_key:
            return {"error": "LLM API Key not configured. Please set it in Settings."}

        model = self._get_config("model", "claude-sonnet-4-20250514")

        # 根据难度确定词数范围
        word_ranges = {
            1: "80-120词", 2: "120-180词", 3: "180-250词",
            4: "250-320词", 5: "320-400词",
        }
        difficulty_labels = {
            1: "简单", 2: "较简单", 3: "中等", 4: "较难", 5: "困难",
        }

        prompt = f"""你是一位专业的英语教师。请根据以下要求生成一篇英语阅读理解短文。

## 要求
- 年级：{self._get_grade_name(grade)}
- 话题：{topic}
- 难度：{difficulty_labels.get(difficulty, '中等')}
- 词数：{word_ranges.get(difficulty, '180-250词')}

## 输出格式
请以以下JSON格式返回：
{{
    "title": "短文标题（中文或英文均可）",
    "content": "英语短文内容",
    "word_count": 实际词数
}}

注意：
- 短文内容应为2-4段，难度与指定等级匹配
- 避免使用过于生僻的词汇
- 内容健康积极，适合对应年级学生阅读
"""
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                timeout=60,
                thinking={"type": "disabled"},
            )

            content = ""
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'text' and hasattr(block, 'text'):
                    content = block.text
                    break

            if not content:
                return {"error": "LLM返回内容为空"}

            return self._parse_generate_response(content)
        except Exception as e:
            return {"error": str(e)}

    def generate_reading_questions(self, passage_content: str) -> dict:
        """
        为短文生成4道阅读理解选择题

        Returns:
            dict: {"questions": [...]}
        """
        self._config = load_llm_config()
        self._init_client()

        api_key = self._get_config("api_key", settings.ANTHROPIC_API_KEY)
        if not api_key:
            return {"error": "LLM API Key not configured"}

        model = self._get_config("model", "claude-sonnet-4-20250514")

        prompt = f"""你是一位专业的英语教师。请为以下英语短文生成4道阅读理解选择题。

## 短文
{passage_content}

## 要求
- 题型：4选1选择题
- 每题必须包含A/B/C/D四个选项
- 问题应涵盖：主旨大意、细节理解、推理判断、词义猜测等类型
- 正确答案分布合理（不全部选同一选项）

## 输出格式
请以以下JSON格式返回：
{{
    "questions": [
        {{
            "question_number": 1,
            "question_text": "What is the main idea of the passage?",
            "option_a": "A. 选项内容",
            "option_b": "B. 选项内容",
            "option_c": "C. 选项内容",
            "option_d": "D. 选项内容",
            "correct_answer": "A",
            "explanation": "解析说明"
        }}
    ]
}}

注意：
- 题目和选项都要用英文
- 选项长度适中，避免过长
- 解析用中文简要说明
"""
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                timeout=60,
                thinking={"type": "disabled"},
            )

            content = ""
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'text' and hasattr(block, 'text'):
                    content = block.text
                    break

            if not content:
                return {"error": "LLM返回内容为空"}

            return self._parse_reading_questions_response(content)
        except Exception as e:
            return {"error": str(e)}

    def _parse_generate_response(self, content: str) -> dict:
        """解析短文生成响应"""
        import json, re
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        try:
            data = json.loads(content)
            return {
                "title": data.get("title", ""),
                "content": data.get("content", ""),
                "word_count": data.get("word_count", 0),
            }
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end != 0:
                try:
                    data = json.loads(content[start:end])
                    return {
                        "title": data.get("title", ""),
                        "content": data.get("content", ""),
                        "word_count": data.get("word_count", 0),
                    }
                except json.JSONDecodeError:
                    pass
            return {"error": "解析失败"}

    def _parse_reading_questions_response(self, content: str) -> dict:
        """解析选择题生成响应"""
        import json, re
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        try:
            data = json.loads(content)
            questions = data.get("questions", [])
            if not questions and "question" in data:
                questions = [data["question"]]
            return {"questions": questions}
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end != 0:
                try:
                    data = json.loads(content[start:end])
                    return {"questions": data.get("questions", [])}
                except json.JSONDecodeError:
                    pass
            return {"error": "解析失败"}
```

- [ ] **Step 2: 在 routers/reading.py 添加 generate 端点**

在 `router` 定义后面，`get_topics` 之前或之后，添加：

```python
@router.post("/generate", status_code=201)
def generate_reading(data: GenerateReadingRequest, db: Session = Depends(get_db)):
    """
    调用LLM生成英语短文 + 配套选择题，保存到数据库
    """
    from app.services.llm import llm_service

    # 1. 生成短文
    passage_result = llm_service.generate_reading_passage(
        grade=data.grade,
        topic=data.topic,
        difficulty=data.difficulty,
    )

    if "error" in passage_result:
        raise HTTPException(status_code=500, detail=f"短文生成失败: {passage_result['error']}")

    if not passage_result.get("content"):
        raise HTTPException(status_code=500, detail="生成了空短文")

    # 2. 生成选择题
    questions_result = llm_service.generate_reading_questions(
        passage_content=passage_result["content"]
    )

    if "error" in questions_result:
        raise HTTPException(status_code=500, detail=f"选择题生成失败: {questions_result['error']}")

    raw_questions = questions_result.get("questions", [])
    if not raw_questions:
        raise HTTPException(status_code=500, detail="未生成选择题")

    # 3. 保存到数据库
    passage = ReadingPassage(
        title=passage_result["title"],
        content=passage_result["content"],
        topic=data.topic,
        grade=data.grade,
        difficulty=data.difficulty,
        word_count=passage_result.get("word_count") or len(passage_result["content"].split()),
        source="generated",
    )
    db.add(passage)
    db.flush()

    for i, q in enumerate(raw_questions[:4]):
        question = ReadingQuestion(
            passage_id=passage.id,
            question_number=q.get("question_number", i + 1),
            question_text=q.get("question_text", ""),
            option_a=q.get("option_a", ""),
            option_b=q.get("option_b", ""),
            option_c=q.get("option_c", ""),
            option_d=q.get("option_d", ""),
            correct_answer=q.get("correct_answer", "A"),
            explanation=q.get("explanation", ""),
        )
        db.add(question)

    db.commit()
    db.refresh(passage)

    return passage
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/llm.py backend/app/routers/reading.py
git commit -m "feat(reading): implement LLM generation of passages and questions"
```

---

### Task 6: 扩展练习集 API 支持阅读理解

**Files:**
- Modify: `backend/app/routers/practice_set.py`
- Modify: `backend/app/schemas/reading.py`（如果需要补充schemas）

- [ ] **Step 1: 在 practice_set.py 中添加 generate-from-reading 端点**

在 `generate_practice_from_questions` 函数之前（或现有路由之后），添加：

```python
class GenerateFromReadingRequest(BaseModel):
    """从短文生成练习集请求"""
    passage_id: int
    name: Optional[str] = None


@router.post("/generate-from-reading", response_model=PracticeSetResponse, status_code=201)
def generate_practice_from_reading(data: GenerateFromReadingRequest, db: Session = Depends(get_db)):
    """
    从短文生成阅读理解练习集

    创建 source_type=reading 的练习集，关联短文
    """
    from app.models.reading import ReadingPassage, ReadingQuestion

    # 验证短文存在
    passage = db.query(ReadingPassage).options(
        joinedload(ReadingPassage.questions)
    ).filter(
        ReadingPassage.id == data.passage_id,
        ReadingPassage.deleted == False
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="短文不存在")

    if not passage.questions:
        raise HTTPException(status_code=400, detail="该短文没有选择题")

    # 创建练习集（reading 类型不创建 PracticeSetQuestion 记录，
    # 因为题目来自 ReadingQuestion 表，通过 passage_id 关联）
    practice_set = PracticeSet(
        name=data.name or f"阅读理解-{passage.title}"[:200],
        subject_id=_get_english_subject_id(db),  # 英语学科ID
        source_type="reading",
        question_type="original",
        total_questions=len(passage.questions),
        passage_id=passage.id,
    )
    db.add(practice_set)
    db.commit()
    db.refresh(practice_set)

    db.commit()
    db.refresh(practice_set)

    return {
        "id": practice_set.id,
        "name": practice_set.name,
        "subject_id": practice_set.subject_id,
        "source_type": "reading",
        "question_type": "original",
        "total_questions": len(passage.questions),
        "reviewed": False,
        "review_count": 0,
        "created_at": practice_set.created_at,
        "questions": [],
    }


def _get_english_subject_id(db: Session) -> int:
    """获取英语学科ID，如果不存在则创建"""
    from app.models.subject import Subject
    subject = db.query(Subject).filter(Subject.name == "英语").first()
    if subject:
        return subject.id
    # 创建英语学科
    subject = Subject(name="英语")
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject.id
```

- [ ] **Step 2: 扩展 get_practice_set 支持 reading 类型**

在获取练习集详情时，当 `source_type == "reading"` 时，返回短文+题目：

在 `get_practice_set` 函数中，找到 `if ps.source_type == "word":` 这个分支，在其之前或之后添加：

```python
    if ps.source_type == "reading" and ps.passage_id:
        from app.models.reading import ReadingPassage, ReadingQuestion
        passage = db.query(ReadingPassage).options(
            joinedload(ReadingPassage.questions)
        ).filter(ReadingPassage.id == ps.passage_id).first()

        if passage:
            # 构造阅读理解的题目响应
            for idx, q in enumerate(passage.questions):
                questions.append({
                    "id": q.id,
                    "question_id": q.id,
                    "similar_question_id": None,
                    "display_order": idx,
                    "question_text": f"[阅读题] {passage.title} - 第{q.question_number}题",
                    "answer": q.correct_answer,
                    "difficulty": passage.difficulty,
                    "knowledge_point": f"阅读理解-{passage.topic}",
                    "is_correct": None,  # 尚未批改
                    "tags": [],
                    "original_question_text": q.question_text,
                    "original_answer": q.correct_answer,
                    "original_image": None,
                })
```

同时需要将 passage 和 questions 的额外信息加入到 response 中。考虑到 PracticeSetResponse 中已经有 questions 字段，且 question_text 和 original_question_text 已存在，前端在渲染时可以通过 source_type==reading 来判断需要特殊展示。

- [ ] **Step 3: 扩展 mark_reviewed 支持 reading 批改**

reading 类型练习集没有 PracticeSetQuestion 记录（问题来自 ReadingQuestion 表），
需要在计算正确率时从 `question_results` 直接统计：

```python
    # 获取所有关联题目（reading 类型没有 ps_questions，跳过循环）
    if ps.source_type != "reading":
        ps_questions = db.query(PracticeSetQuestion).filter(
            PracticeSetQuestion.practice_set_id == practice_set_id
        ).all()

        for psq in ps_questions:
            question = db.query(Question).filter(Question.id == psq.question_id).first()
            if not question:
                continue
            question.review_count = (question.review_count or 0) + 1
            # ... 原有逻辑不变
    else:
        # reading 类型：results_list 直接记录所有结果，不关联 question 表
        pass

    # 计算正确率（对 reading 类型，直接由 results_list 计算）
    if ps.source_type == "reading":
        if results_list:
            correct_count = sum(1 for r in results_list if r.get('is_correct'))
            ps.accuracy = round(correct_count / len(results_list) * 100, 1) if results_list else None
    elif is_all_correct == True:
        # 原有逻辑...
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/practice_set.py
git commit -m "feat(reading): extend practice set API for reading comprehension"
```

---

### Task 7: 阅读理解前端入口页

**Files:**
- Create: `frontend/src/views/Reading.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/views/ReadingTest.vue`

- [ ] **Step 1: 创建 Reading.vue（短文库主页）**

```vue
<template>
  <div class="reading-page">
    <el-row :gutter="20">
      <!-- 左侧短文列表 -->
      <el-col :span="10">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>短文库</span>
              <el-button type="primary" size="small" @click="showGenerateDialog = true">
                生成短文
              </el-button>
            </div>
          </template>

          <!-- 筛选 -->
          <div class="filters">
            <el-select v-model="filters.topic" placeholder="话题" clearable size="small" @change="fetchReadings" style="width: 110px">
              <el-option v-for="t in topics" :key="t" :label="t" :value="t" />
            </el-select>
            <el-select v-model="filters.grade" placeholder="年级" clearable size="small" @change="fetchReadings" style="width: 90px">
              <el-option v-for="g in 12" :key="g" :label="g + '年级'" :value="g" />
            </el-select>
            <el-select v-model="filters.difficulty" placeholder="难度" clearable size="small" @change="fetchReadings" style="width: 90px">
              <el-option v-for="d in 5" :key="d" :label="'⭐'.repeat(d)" :value="d" />
            </el-select>
          </div>

          <!-- 列表 -->
          <div v-if="loading" class="loading">加载中...</div>
          <div v-else-if="readings.length === 0" class="empty">暂无短文</div>
          <div v-else class="passage-list">
            <div
              v-for="item in readings"
              :key="item.id"
              class="passage-card"
              :class="{ active: selectedId === item.id }"
              @click="selectPassage(item)"
            >
              <div class="passage-title">{{ item.title }}</div>
              <div class="passage-meta">
                <el-tag size="small" type="info">{{ item.topic }}</el-tag>
                <span class="meta-item">{{ item.grade }}年级</span>
                <span class="meta-item">{{ '⭐'.repeat(item.difficulty) }}</span>
                <span class="meta-item">{{ item.word_count || '-' }}词</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧详情 -->
      <el-col :span="14">
        <el-card v-if="selectedPassage">
          <template #header>
            <div class="card-header">
              <span>{{ selectedPassage.title }}</span>
              <div>
                <el-button type="success" size="small" @click="createPracticeSet">
                  创建练习集
                </el-button>
                <el-button type="danger" size="small" @click="deletePassage">
                  删除
                </el-button>
              </div>
            </div>
          </template>

          <div class="passage-content">
            <p v-for="(para, idx) in selectedPassage.content.split('\n').filter(Boolean)" :key="idx" class="paragraph">
              {{ para.trim() }}
            </p>
          </div>

          <el-divider />

          <div class="questions-section">
            <h4>选择题（共 {{ selectedPassage.questions.length }} 题）</h4>
            <div v-for="q in selectedPassage.questions" :key="q.id" class="question-item">
              <p class="question-text">{{ q.question_number }}. {{ q.question_text }}</p>
              <div class="options">
                <div class="option">A. {{ q.option_a }}</div>
                <div class="option">B. {{ q.option_b }}</div>
                <div class="option">C. {{ q.option_c }}</div>
                <div class="option">D. {{ q.option_d }}</div>
              </div>
              <el-button v-if="showAnswer" size="small" type="warning" @click="q._showAnswer = !q._showAnswer">
                {{ q._showAnswer ? '隐藏答案' : '查看答案' }}
              </el-button>
              <div v-if="q._showAnswer" class="answer-box">
                答案：{{ q.correct_answer }} —— {{ q.explanation }}
              </div>
            </div>
            <el-button size="small" @click="showAnswer = !showAnswer">
              {{ showAnswer ? '全部隐藏' : '全部显示' }}答案
            </el-button>
          </div>
        </el-card>

        <el-card v-else>
          <div class="empty-detail">请在左侧选择一篇短文</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 生成短文弹窗 -->
    <el-dialog v-model="showGenerateDialog" title="生成英语短文" width="450px">
      <el-form :model="generateForm" label-width="80px">
        <el-form-item label="年级">
          <el-select v-model="generateForm.grade" style="width: 100%">
            <el-option v-for="g in 12" :key="g" :label="g + '年级'" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="话题">
          <el-select v-model="generateForm.topic" style="width: 100%">
            <el-option v-for="t in topics" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-rate v-model="generateForm.difficulty" :max="5" show-score />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="doGenerate">
          {{ generating ? '生成中...' : '生成' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const readings = ref([])
const topics = ref([])
const selectedId = ref(null)
const selectedPassage = ref(null)
const loading = ref(false)
const showAnswer = ref(false)
const showGenerateDialog = ref(false)
const generating = ref(false)

const filters = reactive({
  topic: '',
  grade: null,
  difficulty: null,
})

const generateForm = reactive({
  grade: 7,
  topic: '校园生活',
  difficulty: 3,
})

async function fetchTopics() {
  try {
    const res = await axios.get('/api/readings/topics')
    topics.value = res.data
  } catch {
    topics.value = []
  }
}

async function fetchReadings() {
  loading.value = true
  try {
    const params = {}
    if (filters.topic) params.topic = filters.topic
    if (filters.grade) params.grade = filters.grade
    if (filters.difficulty) params.difficulty = filters.difficulty
    const res = await axios.get('/api/readings', { params })
    readings.value = res.data.items || []
  } catch {
    ElMessage.error('获取短文列表失败')
  } finally {
    loading.value = false
  }
}

async function selectPassage(item) {
  selectedId.value = item.id
  try {
    const res = await axios.get(`/api/readings/${item.id}`)
    selectedPassage.value = res.data
  } catch {
    ElMessage.error('获取短文详情失败')
  }
}

async function doGenerate() {
  generating.value = true
  try {
    await axios.post('/api/readings/generate', generateForm)
    ElMessage.success('生成成功')
    showGenerateDialog.value = false
    await fetchReadings()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    generating.value = false
  }
}

async function deletePassage() {
  if (!selectedPassage.value) return
  try {
    await ElMessageBox.confirm('确定删除这篇短文？')
    await axios.delete(`/api/readings/${selectedPassage.value.id}`)
    ElMessage.success('删除成功')
    selectedPassage.value = null
    selectedId.value = null
    await fetchReadings()
  } catch {
    // 取消删除
  }
}

async function createPracticeSet() {
  if (!selectedPassage.value) return
  try {
    const res = await axios.post('/api/practice-sets/generate-from-reading', {
      passage_id: selectedPassage.value.id,
    })
    ElMessage.success('练习集创建成功')
    // 跳转到练习集详情
    window.location.href = `/reading-test/${res.data.id}`
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

onMounted(() => {
  fetchTopics()
  fetchReadings()
})
</script>

<style scoped>
.reading-page { padding: 10px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filters { display: flex; gap: 8px; margin-bottom: 15px; }
.passage-list { max-height: 600px; overflow-y: auto; }
.passage-card { padding: 12px; border: 1px solid #ebeef5; border-radius: 6px; margin-bottom: 8px; cursor: pointer; transition: all 0.2s; }
.passage-card:hover { border-color: #409eff; }
.passage-card.active { border-color: #409eff; background-color: #ecf5ff; }
.passage-title { font-weight: bold; margin-bottom: 6px; }
.passage-meta { display: flex; gap: 8px; align-items: center; font-size: 12px; color: #909399; }
.meta-item { white-space: nowrap; }
.passage-content { line-height: 1.8; font-size: 14px; }
.paragraph { margin-bottom: 10px; text-indent: 2em; }
.question-item { margin-bottom: 16px; padding: 12px; background: #fafafa; border-radius: 4px; }
.question-text { font-weight: bold; margin-bottom: 8px; }
.option { padding: 4px 0; }
.answer-box { margin-top: 6px; padding: 6px 10px; background: #fdf6ec; border-radius: 4px; color: #e6a23c; font-size: 13px; }
.loading, .empty, .empty-detail { text-align: center; padding: 40px; color: #909399; }
</style>
```

- [ ] **Step 2: 创建 ReadingTest.vue（阅读理解测试页面）**

```vue
<template>
  <div class="reading-test">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>阅读理解测试 - {{ practiceSet?.name || '' }}</span>
          <el-button @click="goBack">返回</el-button>
        </div>
      </template>

      <div v-if="passage" class="test-container">
        <el-row :gutter="20">
          <!-- 短文区 -->
          <el-col :xs="24" :md="12" class="passage-col">
            <div class="passage-scroll">
              <h3>{{ passage.title }}</h3>
              <p v-for="(para, idx) in passage.content.split('\n').filter(Boolean)" :key="idx" class="paragraph">
                {{ para.trim() }}
              </p>
              <div class="meta-bar">
                <el-tag size="small">{{ passage.topic }}</el-tag>
                <span class="meta-item">{{ passage.grade }}年级</span>
                <span class="meta-item">{{ '⭐'.repeat(passage.difficulty) }}</span>
                <span class="meta-item">{{ passage.word_count }}词</span>
              </div>
            </div>
          </el-col>

          <!-- 答题区 -->
          <el-col :xs="24" :md="12" class="answer-col">
            <h4>选择题</h4>
            <div v-for="q in questions" :key="q.id" class="question-block">
              <p class="q-text">{{ q.question_number }}. {{ q.question_text }}</p>
              <el-radio-group v-model="answers[q.id]" class="options-group">
                <el-radio value="A" class="option-item">A. {{ q.option_a }}</el-radio>
                <el-radio value="B" class="option-item">B. {{ q.option_b }}</el-radio>
                <el-radio value="C" class="option-item">C. {{ q.option_c }}</el-radio>
                <el-radio value="D" class="option-item">D. {{ q.option_d }}</el-radio>
              </el-radio-group>
            </div>

            <div class="action-bar">
              <el-button type="primary" size="large" :disabled="!allAnswered" @click="submitTest">
                交卷
              </el-button>
            </div>

            <!-- 结果展示 -->
            <div v-if="testResult" class="result-box" :class="{ pass: resultRate >= 60, fail: resultRate < 60 }">
              <h4>测试结果</h4>
              <p>正确：{{ resultCorrect }}/{{ resultTotal }}（{{ resultRate }}%）</p>
              <div v-for="q in questions" :key="q.id" class="result-item">
                <span :class="answers[q.id] === q.correct_answer ? 'correct' : 'wrong'">
                  Q{{ q.question_number }}:
                  <template v-if="answers[q.id] === q.correct_answer">✓ 正确</template>
                  <template v-else>
                    ✗ 你的答案: {{ answers[q.id] }}, 正确答案: {{ q.correct_answer }}
                  </template>
                </span>
                <p class="explanation">{{ q.explanation }}</p>
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const practiceSetId = route.params.id

const practiceSet = ref(null)
const passage = ref(null)
const questions = ref([])
const answers = ref({})
const testResult = ref(false)

const allAnswered = computed(() => {
  return questions.value.length > 0 && questions.value.every(q => answers.value[q.id])
})

const resultCorrect = computed(() => {
  return questions.value.filter(q => answers.value[q.id] === q.correct_answer).length
})

const resultTotal = computed(() => questions.value.length)

const resultRate = computed(() => {
  return resultTotal.value > 0 ? Math.round(resultCorrect.value / resultTotal.value * 100) : 0
})

async function fetchTestData() {
  try {
    const res = await axios.get(`/api/practice-sets/${practiceSetId}`)
    practiceSet.value = res.data

    // 获取短文详情
    if (res.data.passage_id) {
      const passageRes = await axios.get(`/api/readings/${res.data.passage_id}`)
      passage.value = passageRes.data
      questions.value = passageRes.data.questions || []
    }
  } catch {
    ElMessage.error('获取测试数据失败')
  }
}

async function submitTest() {
  const results = questions.value.map(q => ({
    question_id: q.id,
    is_correct: answers.value[q.id] === q.correct_answer,
  }))

  try {
    await axios.post(`/api/practice-sets/${practiceSetId}/mark-reviewed`, {
      question_results: JSON.stringify(results),
    })
    testResult.value = true
  } catch {
    ElMessage.error('提交失败')
  }
}

function goBack() {
  router.push('/reading')
}

onMounted(fetchTestData)
</script>

<style scoped>
.reading-test { padding: 10px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.test-container { min-height: 500px; }
.passage-col { border-right: 1px solid #ebeef5; }
.passage-scroll { padding-right: 20px; max-height: 600px; overflow-y: auto; }
.passage-scroll h3 { margin-bottom: 16px; }
.paragraph { margin-bottom: 12px; line-height: 1.8; text-indent: 2em; }
.meta-bar { margin-top: 20px; display: flex; gap: 8px; align-items: center; font-size: 12px; color: #909399; }
.answer-col { padding-left: 20px; }
.question-block { margin-bottom: 20px; padding: 16px; background: #fafafa; border-radius: 6px; }
.q-text { font-weight: bold; margin-bottom: 12px; }
.options-group { display: flex; flex-direction: column; gap: 8px; }
.option-item { margin: 0; padding: 8px 12px; border-radius: 4px; }
.option-item:hover { background: #ecf5ff; }
.action-bar { text-align: center; margin: 20px 0; }
.result-box { padding: 16px; border-radius: 6px; margin-top: 16px; }
.result-box.pass { background: #f0f9eb; border: 1px solid #e1f3d8; }
.result-box.fail { background: #fef0f0; border: 1px solid #fde2e2; }
.result-item { padding: 8px 0; border-bottom: 1px solid #ebeef5; }
.correct { color: #67c23a; }
.wrong { color: #f56c6c; }
.explanation { font-size: 13px; color: #909399; margin-top: 4px; }
@media (max-width: 768px) {
  .passage-col { border-right: none; }
  .passage-scroll { padding-right: 0; }
  .answer-col { padding-left: 0; }
}
</style>
```

- [ ] **Step 3: 更新路由配置**

```javascript
// 在 router/index.js 中，在 /practice-sets 路由之前添加：
  {
    path: '/reading',
    name: 'Reading',
    component: () => import('@/views/Reading.vue'),
  },
  {
    path: '/reading-test/:id',
    name: 'ReadingTest',
    component: () => import('@/views/ReadingTest.vue'),
  },
```

- [ ] **Step 4: 更新导航栏 App.vue**

在「练习」和「统计」之间添加阅读菜单项：

```html
<el-menu-item index="/practice-sets">练习</el-menu-item>
<el-menu-item index="/reading">阅读</el-menu-item>
<el-menu-item index="/stats">统计</el-menu-item>
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/Reading.vue frontend/src/views/ReadingTest.vue frontend/src/router/index.js frontend/src/App.vue
git commit -m "feat(reading): add reading comprehension UI with /reading route"
```

---

### Task 8: 整合验证

- [ ] **Step 1: 启动后端并检查 startup 日志**

```bash
cd backend && python -m app.main
```

Expected: 无导入错误，ReadingPassage 和 ReadingQuestion 表自动创建，reading_router 注册无误

- [ ] **Step 2: 启动前端 Dev Server**

```bash
cd frontend && npm run dev
```

Expected: 导航栏显示「阅读」菜单，`/reading` 路由可访问

- [ ] **Step 3: 冒烟测试**

```bash
# 获取话题列表
curl http://localhost:8000/api/readings/topics
# 生成短文（需要 LLM 配置）
curl -X POST http://localhost:8000/api/readings/generate -H "Content-Type: application/json" -d '{"grade":7,"topic":"校园生活","difficulty":3}'
# 列出短文
curl http://localhost:8000/api/readings
```

Expected: 各接口正常返回
