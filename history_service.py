"""
打印记录与中断恢复
- 使用 CSV 保存打印记录
- 检查重复二维码
- 记录上次任务进度以支持中断恢复
"""

import csv
import os
from datetime import datetime

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_HISTORY_FILE = os.path.join(_DATA_DIR, "print_history.csv")
_PROGRESS_FILE = os.path.join(_DATA_DIR, "last_progress.json")


def _ensure_data_dir():
    """确保 data 目录存在"""
    os.makedirs(_DATA_DIR, exist_ok=True)


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
    _ensure_data_dir()
    file_exists = os.path.exists(_HISTORY_FILE)

    with open(_HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
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
    if not os.path.exists(_HISTORY_FILE):
        return False
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
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
    _ensure_data_dir()
    import json
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
    with open(_PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def load_progress() -> dict | None:
    """读取上次任务进度"""
    if not os.path.exists(_PROGRESS_FILE):
        return None
    import json
    try:
        with open(_PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def clear_progress():
    """清除上次任务进度（任务完成或取消时调用）"""
    if os.path.exists(_PROGRESS_FILE):
        os.remove(_PROGRESS_FILE)