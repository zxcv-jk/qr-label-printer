"""
Windows 打印模块
- 获取打印机列表和默认打印机
- 使用 pywin32 提交标签图片到打印队列
"""

import os
import win32print
import win32ui
from PIL import ImageWin


def get_printer_list() -> list[str]:
    """获取 Windows 已安装打印机名称列表"""
    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
    return [printer[2] for printer in printers]


def get_default_printer() -> str | None:
    """获取 Windows 默认打印机名称"""
    try:
        return win32print.GetDefaultPrinter()
    except Exception:
        return None


def get_printer(config: dict) -> str | None:
    """
    根据配置获取要使用的打印机名称
    优先级：配置指定打印机 > Windows 默认打印机
    """
    if not config.get("use_default_printer", True) and config.get("printer_name"):
        printer_name = config["printer_name"]
        # 检查配置的打印机是否存在
        available = get_printer_list()
        if printer_name in available:
            return printer_name

    # 使用默认打印机
    return get_default_printer()


def print_label(
    image_path: str,
    printer_name: str,
    config: dict,
) -> bool:
    """
    将标签图片提交到 Windows 打印队列
    返回 True 表示任务已提交，False 表示失败
    """
    try:
        from PIL import Image

        # 打开图片
        img = Image.open(image_path)

        # 获取打印机 DC
        printer_dc = win32ui.CreateDC()
        printer_dc.CreatePrinterDC(printer_name)

        # 开始打印任务
        printer_dc.StartDoc("二维码标签打印工具")
        printer_dc.StartPage()

        # 获取实际打印尺寸 (mm -> 打印机 units)
        dpi = config.get("dpi", 203)
        width_mm = config.get("label_width_mm", 100)
        height_mm = config.get("label_height_mm", 60)

        # 打印机单位 = 英寸的千分之一，所以 DPI=203 时 1mm ≈ 8 units
        units_per_mm = dpi / 25.4
        width_units = int(width_mm * units_per_mm)
        height_units = int(height_mm * units_per_mm)

        # 转换图片为打印兼容格式
        dib = ImageWin.Dib(img)

        # 绘制到打印机 DC
        dib.draw(printer_dc.GetHandleOutput(), (0, 0, width_units, height_units))

        # 结束打印
        printer_dc.EndPage()
        printer_dc.EndDoc()
        printer_dc.DeleteDC()

        return True

    except Exception as e:
        import logging
        logging.error(f"打印失败: {e}", exc_info=True)
        raise