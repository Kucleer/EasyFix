import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.operation_log import OperationLog, OperationType, OperationStatus
from app.database import SessionLocal


class LoggerService:
    """日志记录服务"""

    @staticmethod
    def log(
        operation_type: str,
        operation_status: str,
        target_type: str = None,
        target_id: int = None,
        request_data: dict = None,
        response_data: dict = None,
        error_message: str = None,
        ip_address: str = None,
        user_agent: str = None,
    ) -> int:
        """
        记录操作日志

        Returns:
            日志ID
        """
        db = SessionLocal()
        try:
            log_entry = OperationLog(
                operator="system",
                operation_type=operation_type,
                operation_status=operation_status,
                target_type=target_type,
                target_id=target_id,
                request_data=json.dumps(request_data, ensure_ascii=False) if request_data else None,
                response_data=json.dumps(response_data, ensure_ascii=False) if response_data else None,
                error_message=error_message,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            return log_entry.id
        except Exception as e:
            db.rollback()
            print(f"Failed to write log: {e}")
            return -1
        finally:
            db.close()

    @staticmethod
    def log_upload(image_path: str, ocr_result: dict, success: bool = True, error: str = None):
        """记录上传操作"""
        return LoggerService.log(
            operation_type=OperationType.UPLOAD,
            operation_status=OperationStatus.SUCCESS if success else OperationStatus.FAILED,
            target_type="image",
            target_id=None,
            request_data={"image_path": image_path},
            response_data=ocr_result,
            error_message=error,
        )

    @staticmethod
    def log_question(operation: str, question_id: int, data: dict, success: bool = True, error: str = None):
        """记录错题操作"""
        return LoggerService.log(
            operation_type=operation,
            operation_status=OperationStatus.SUCCESS if success else OperationStatus.FAILED,
            target_type="question",
            target_id=question_id,
            request_data=data,
            error_message=error,
        )

    @staticmethod
    def log_error_book(operation: str, error_book_id: int, data: dict, success: bool = True, error: str = None):
        """记录错题本操作"""
        return LoggerService.log(
            operation_type=operation,
            operation_status=OperationStatus.SUCCESS if success else OperationStatus.FAILED,
            target_type="error_book",
            target_id=error_book_id,
            request_data=data,
            error_message=error,
        )

    @staticmethod
    def log_ocr(image_path: str, result: dict, provider: str, success: bool = True, error: str = None):
        """记录OCR识别"""
        return LoggerService.log(
            operation_type=OperationType.OCR_RECOGNIZE,
            operation_status=OperationStatus.SUCCESS if success else OperationStatus.FAILED,
            target_type="ocr",
            target_id=None,
            request_data={"image_path": image_path, "provider": provider},
            response_data={"text_length": len(result.get("full_text", ""))} if success else None,
            error_message=error,
        )

    @staticmethod
    def log_similar(question_id: int, similar_result: dict, success: bool = True, error: str = None):
        """记录相似题生成"""
        return LoggerService.log(
            operation_type=OperationType.GENERATE_SIMILAR,
            operation_status=OperationStatus.SUCCESS if success else OperationStatus.FAILED,
            target_type="question",
            target_id=question_id,
            request_data={"question_id": question_id},
            response_data=similar_result,
            error_message=error,
        )

    @staticmethod
    def log_operation(
        operation_type: str,
        target_type: str = None,
        target_id: int = None,
        data: dict = None,
        success: bool = True,
        error: str = None,
    ):
        """记录通用操作"""
        return LoggerService.log(
            operation_type=operation_type,
            operation_status=OperationStatus.SUCCESS if success else OperationStatus.FAILED,
            target_type=target_type,
            target_id=target_id,
            request_data=data,
            error_message=error,
        )


# 全局日志服务实例
logger_service = LoggerService()
