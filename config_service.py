"""
配置服务 - 读取和保存 config.json
"""

import json
import os
import sys

def _get_base_dir() -> str:
    """获取配置文件目录：EXE 旁边或源码目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

_CONFIG_PATH = os.path.join(_get_base_dir(), "config.json")

_DEFAULT_CONFIG = {
    "printer_name": "",
    "use_default_printer": True,
    "force_configured_printer": False,
    "label_width_mm": 100,
    "label_height_mm": 60,
    "dpi": 203,
    "orientation": "horizontal",
    "offset_x_mm": 0,
    "offset_y_mm": 0,
    "qr_size_mm": 31.0,
    "qr_y_mm": 4.0,
    "margin_left_mm": 4.0,
    "field_label_x_mm": 40.0,
    "field_value_x_mm": 62.0,
    "field_first_y_mm": 5.0,
    "field_line_height_mm": 7.0,
    "content_y_mm": 39.0,
    "description_y_mm": 49.0,
    "font_size_field": 24,
    "font_size_plain": 18,
    "font_size_desc": 22,
    "default_description": "请填写物料描述",
    "draw_debug_border": False,
    "save_test_image": False,
}


def load_config() -> dict:
    """读取配置文件，缺失项用默认值填充"""
    if not os.path.exists(_CONFIG_PATH):
        save_config(_DEFAULT_CONFIG)
        return dict(_DEFAULT_CONFIG)

    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        for key, value in _DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config
    except Exception as e:
        import logging
        logging.error(f"配置文件读取失败: {e}", exc_info=True)
        print(f"警告：配置文件读取失败，已使用默认设置。错误：{e}")
        return dict(_DEFAULT_CONFIG)


def save_config(config: dict):
    """保存配置到文件"""
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)