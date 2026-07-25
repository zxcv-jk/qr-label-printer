"""
统一异常处理 - 记录日志并显示友好提示
"""

import logging
import os
import traceback

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")


def setup_logging():
    """初始化日志配置"""
    os.makedirs(_LOG_DIR, exist_ok=True)
    logging.basicConfig(
        filename=_LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )


def log_error(message: str, exc_info: bool = True):
    """记录错误日志"""
    logging.error(message, exc_info=exc_info)


def log_info(message: str):
    """记录信息日志"""
    logging.info(message)


def handle_exception(e: Exception) -> str:
    """
    处理异常，返回给 GUI 显示的用户友好消息
    """
    if isinstance(e, ValueError):
        # ValueError 已经有明确的中文提示，直接使用
        return str(e)
    elif isinstance(e, FileNotFoundError):
        log_error(f"文件未找到: {e}")
        return f"文件未找到，请检查路径配置。"
    elif isinstance(e, PermissionError):
        log_error(f"权限不足: {e}")
        return f"权限不足，请检查文件和目录权限。"
    else:
        # 未知错误：记录完整日志，返回简短提示
        log_error(f"未知错误: {e}", exc_info=True)
        return f"程序遇到未知错误，详情请查看 logs/app.log"