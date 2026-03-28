from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, func
from app.database import Base
import enum


class OperationType(str, enum.Enum):
    UPLOAD = "upload"           # 上传图片
    OCR_RECOGNIZE = "ocr"       # OCR识别
    CREATE_QUESTION = "create_question"   # 创建错题
    UPDATE_QUESTION = "update_question"   # 更新错题
    DELETE_QUESTION = "delete_question"  # 删除错题
    GENERATE_SIMILAR = "generate_similar"  # 生成相似题
    CREATE_ERROR_BOOK = "create_error_book"  # 创建错题本
    UPDATE_ERROR_BOOK = "update_error_book"  # 更新错题本
    LOGIN = "login"             # 登录
    CONFIG_CHANGE = "config"     # 配置变更


class OperationStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class OperationLog(Base):
    """操作日志表"""
    __tablename__ = "operation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator = Column(String(100), default="system")  # 操作人
    operation_type = Column(String(50), nullable=False)  # 操作类型
    operation_status = Column(String(20), nullable=False)  # 操作状态
    target_type = Column(String(50), nullable=True)  # 目标类型 (question, error_book, etc)
    target_id = Column(Integer, nullable=True)  # 目标ID
    request_data = Column(Text, nullable=True)  # 请求数据 (JSON)
    response_data = Column(Text, nullable=True)  # 响应数据 (JSON)
    error_message = Column(Text, nullable=True)  # 错误信息
    ip_address = Column(String(50), nullable=True)  # IP地址
    user_agent = Column(Text, nullable=True)  # User-Agent
    created_at = Column(DateTime, server_default=func.now())

    @property
    def operation_display(self):
        """操作描述"""
        mapping = {
            OperationType.UPLOAD: "上传图片",
            OperationType.OCR_RECOGNIZE: "OCR识别",
            OperationType.CREATE_QUESTION: "创建错题",
            OperationType.UPDATE_QUESTION: "更新错题",
            OperationType.DELETE_QUESTION: "删除错题",
            OperationType.GENERATE_SIMILAR: "生成相似题",
            OperationType.CREATE_ERROR_BOOK: "创建错题本",
            OperationType.UPDATE_ERROR_BOOK: "更新错题本",
            OperationType.LOGIN: "登录",
            OperationType.CONFIG_CHANGE: "配置变更",
        }
        return mapping.get(self.operation_type, self.operation_type)
