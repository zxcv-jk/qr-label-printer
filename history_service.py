"""
打印记录与中断恢复
- 使用 CSV 保存打印记录
- 检查重复二维码
- 记录上次任务进度以支持中断恢复
- 路径兼容 PyInstaller 打包后的 EXE 运行环境
"""

import csv
import json
import os
import sys
from datetime import datetime


def _get_base_dir() -> str:
    """获取可写数据目录（EXE 旁或项目根目录）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def get_data_dir() -> str:
    """获取数据目录路径"""
    path = os.path.join(_get_base_dir(), "data")
    _ensure_dir(path)
    return path


def get_history_file() -> str:
    """获取打印记录 CSV 文件路径"""
    return os.path.join(get_data_dir(), "print_history.csv")


def get_progress_file() -> str:
    """获取进度 JSON 文件路径"""
    return os.path.join(get_data_dir(), "last_progress.json")


def save_record(
    material_code: str,
    batch: str,
    packing_qty: str,
    serial: str,
    qr_content: str,
    printer_name: str,
    status: str = "已发送",
):
    """保存一条打印记录"""
    history_file = get_history_file()
    file_exists = os.path.exists(history_file)

    with open(history_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["时间", "物料编码", "生产批次", "装箱量", "流水号", "二维码内容", "打印机", "状态"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            material_code,
            batch,
            packing_qty,
            serial,
            qr_content,
            printer_name,
            status,
        ])


def is_duplicate(qr_content: str) -> bool:
    """检查二维码内容是否已存在（重复提醒用）"""
    history_file = get_history_file()
    if not os.path.exists(history_file):
        return False
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳过标题行
            for row in reader:
                if len(row) >= 6 and row[5] == qr_content:
                    return True
    except Exception:
        pass
    return False


def save_progress(
    material_code: str,
    batch: str,
    packing_qty: str,
    description: str,
    current_serial: int,
    total_count: int,
    completed_count: int,
):
    """保存当前打印任务进度"""
    progress = {
        "material_code": material_code,
        "batch": batch,
        "packing_qty": packing_qty,
        "description": description,
        "current_serial": current_serial,
        "total_count": total_count,
        "completed_count": completed_count,
        "timestamp": datetime.now().isoformat(),
    }
    with open(get_progress_file(), "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def load_progress() -> dict | None:
    """读取上次任务进度"""
    if not os.path.exists(get_progress_file()):
        return None
    try:
        with open(get_progress_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def clear_progress():
    """清除上次任务进度（任务完成或取消时调用）"""
    if os.path.exists(get_progress_file()):
        os.remove(get_progress_file())