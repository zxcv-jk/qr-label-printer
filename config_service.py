"""
配置服务 - 读取和保存 config.json
"""

import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

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
    "qr_size_mm": 30,
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
        # 填充缺失的默认值
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