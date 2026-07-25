"""
统一异常处理 - 记录日志并显示友好提示
路径兼容 PyInstaller 打包后的 EXE 运行环境
"""

import logging
import os
import sys


def _get_base_dir() -> str:
    """获取可写目录（EXE 旁或项目根目录）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_log_dir() -> str:
    """获取日志目录路径"""
    path = os.path.join(_get_base_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def _get_log_file() -> str:
    """获取日志文件路径"""
    return os.path.join(_get_log_dir(), "app.log")


def setup_logging():
    """初始化日志配置"""
    logging.basicConfig(
        filename=_get_log_file(),
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
        return str(e)
    elif isinstance(e, FileNotFoundError):
        log_error(f"文件未找到: {e}")
        return "文件未找到，请检查路径配置。"
    elif isinstance(e, PermissionError):
        log_error(f"权限不足: {e}")
        return "权限不足，请检查文件和目录权限。"
    else:
        log_error(f"未知错误: {e}", exc_info=True)
        return "程序遇到未知错误，详情请查看 logs/app.log"