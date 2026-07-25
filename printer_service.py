"""
Windows 打印模块
- 获取打印机列表和默认打印机
- 使用 pywin32 提交标签图片到打印队列
- 读取打印机 DC 的实际 DPI 和可打印区域
"""

import os
import win32print
import win32ui
from PIL import ImageWin


def get_printer_list() -> list[str]:
    """获取 Windows 已安装打印机名称列表"""
    printers = win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    )
    return [printer[2] for printer in printers]


def get_default_printer() -> str | None:
    """获取 Windows 默认打印机名称"""
    try:
        return win32print.GetDefaultPrinter()
    except Exception:
        return None


def get_printer(config: dict) -> str | None:
    """
    根据配置获取要使用的打印机名称。

    策略：
    - use_default_printer=True → 使用 Windows 默认打印机
    - force_configured_printer=True → 必须找到配置指定的打印机，找不到则返回 None
    - 其他情况：优先使用默认打印机
    """
    force = config.get("force_configured_printer", False)

    if not config.get("use_default_printer", True) or force:
        printer_name = config.get("printer_name", "")
        if printer_name:
            available = get_printer_list()
            if printer_name in available:
                return printer_name
            if force:
                # 强制使用指定打印机但找不到，返回 None 让调用方报错
                return None

    return get_default_printer()


def get_printer_dpi(printer_name: str) -> int:
    """从打印机 DC 读取实际 DPI（仅用于日志记录和参考）"""
    try:
        printer_dc = win32ui.CreateDC()
        printer_dc.CreatePrinterDC(printer_name)
        try:
            # LOGPIXELSY 返回垂直 DPI
            dpi = printer_dc.GetDeviceCaps(90)  # LOGPIXELSY = 90
            return dpi
        finally:
            printer_dc.DeleteDC()
    except Exception:
        return 203  # 默认值


def print_label(
    image_path: str,
    printer_name: str,
    config: dict,
) -> bool:
    """
    将标签图片提交到 Windows 打印队列。

    从打印机 DC 读取实际 DPI 来计算打印像素尺寸。
    纸张尺寸和方向仍依赖驱动预设（DEVMODE 可在未来版本加入）。

    返回 True 表示任务已提交。
    """
    try:
        from PIL import Image
        import logging

        # 打开图片
        img = Image.open(image_path)

        # 获取打印机 DC
        printer_dc = win32ui.CreateDC()
        printer_dc.CreatePrinterDC(printer_name)

        try:
            # 读取打印机实际 DPI（issue #3）
            actual_dpi_x = printer_dc.GetDeviceCaps(88)   # LOGPIXELSX
            actual_dpi_y = printer_dc.GetDeviceCaps(90)   # LOGPIXELSY
            logging.info(f"打印机 DPI: X={actual_dpi_x}, Y={actual_dpi_y}")

            # 读取可打印区域（单位：像素）
            printable_width = printer_dc.GetDeviceCaps(8)   # HORZRES
            printable_height = printer_dc.GetDeviceCaps(10)  # VERTRES
            logging.info(f"可打印区域: {printable_width}x{printable_height} px")

            # 读取物理页面尺寸（单位：毫米）
            phys_width_mm = printer_dc.GetDeviceCaps(4)    # HORZSIZE
            phys_height_mm = printer_dc.GetDeviceCaps(6)   # VERTSIZE
            logging.info(f"物理纸张: {phys_width_mm}x{phys_height_mm} mm")

            # 开始打印任务
            printer_dc.StartDoc("二维码标签打印工具")
            printer_dc.StartPage()

            # 根据实际 DPI 计算打印尺寸
            dpi = max(actual_dpi_x, actual_dpi_y, 203)
            width_mm = config.get("label_width_mm", 100)
            height_mm = config.get("label_height_mm", 60)

            # 使用实际 DPI 计算目标像素
            width_px = int(width_mm * dpi / 25.4)
            height_px = int(height_mm * dpi / 25.4)

            # 确保不超过可打印区域
            width_px = min(width_px, printable_width)
            height_px = min(height_px, printable_height)

            logging.info(f"打印目标尺寸: {width_px}x{height_px} px (基于 {dpi} DPI)")

            # 缩放图片到目标尺寸
            if img.size != (width_px, height_px):
                img = img.resize((width_px, height_px), Image.Resampling.NEAREST)

            # 转换图片为打印兼容格式
            dib = ImageWin.Dib(img)

            # 绘制到打印机 DC
            dib.draw(printer_dc.GetHandleOutput(), (0, 0, width_px, height_px))

            # 结束打印
            printer_dc.EndPage()
            printer_dc.EndDoc()
            logging.info(f"打印任务已提交到 {printer_name}")

        finally:
            try:
                printer_dc.DeleteDC()
            except Exception:
                pass

        return True

    except Exception as e:
        import logging
        logging.error(f"打印失败: {e}", exc_info=True)
        raise