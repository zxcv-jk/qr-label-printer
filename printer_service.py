"""
Windows 打印模块
- 获取打印机列表和默认打印机
- 使用 pywin32 提交标签图片到打印队列
- 支持单次批处理：一个 StartDoc 包含多页
- 读取打印机 DC 的实际 DPI 和可打印区域
"""

import os
import win32print
import win32ui
from PIL import Image, ImageWin


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
                return None

    return get_default_printer()


def get_printer_dpi(printer_name: str) -> int:
    """从打印机 DC 读取实际 DPI"""
    try:
        printer_dc = win32ui.CreateDC()
        printer_dc.CreatePrinterDC(printer_name)
        try:
            dpi = printer_dc.GetDeviceCaps(90)  # LOGPIXELSY = 90
            return dpi
        finally:
            printer_dc.DeleteDC()
    except Exception:
        return 203


class BatchPrinter:
    """
    批量打印上下文管理器。

    整批标签只执行一次 StartDoc，每张标签为一个 Page，
    最后统一 EndDoc。确保 WPS PDF 等虚拟打印机只生成一个多页文件。
    """

    def __init__(self, printer_name: str, config: dict):
        self.printer_name = printer_name
        self.config = config
        self.printer_dc = None
        self.dpi = 203
        self.page_width_px = 0
        self.page_height_px = 0

    def __enter__(self):
        import logging

        self.printer_dc = win32ui.CreateDC()
        self.printer_dc.CreatePrinterDC(self.printer_name)

        # 读取打印机实际 DPI
        actual_dpi_x = self.printer_dc.GetDeviceCaps(88)   # LOGPIXELSX
        actual_dpi_y = self.printer_dc.GetDeviceCaps(90)   # LOGPIXELSY
        self.dpi = max(actual_dpi_x, actual_dpi_y, 203)
        logging.info(f"打印机 DPI: X={actual_dpi_x}, Y={actual_dpi_y}")

        # 读取可打印区域
        printable_width = self.printer_dc.GetDeviceCaps(8)   # HORZRES
        printable_height = self.printer_dc.GetDeviceCaps(10)  # VERTRES
        logging.info(f"可打印区域: {printable_width}x{printable_height} px")

        # 读取物理页面尺寸
        phys_width_mm = self.printer_dc.GetDeviceCaps(4)    # HORZSIZE
        phys_height_mm = self.printer_dc.GetDeviceCaps(6)   # VERTSIZE
        logging.info(f"物理纸张: {phys_width_mm}x{phys_height_mm} mm")

        # 计算目标像素尺寸
        width_mm = self.config.get("label_width_mm", 100)
        height_mm = self.config.get("label_height_mm", 60)
        self.page_width_px = int(width_mm * self.dpi / 25.4)
        self.page_height_px = int(height_mm * self.dpi / 25.4)

        # 不超过可打印区域
        self.page_width_px = min(self.page_width_px, printable_width)
        self.page_height_px = min(self.page_height_px, printable_height)

        logging.info(f"每页尺寸: {self.page_width_px}x{self.page_height_px} px (基于 {self.dpi} DPI)")

        # 开始整批打印任务
        self.printer_dc.StartDoc("二维码标签打印工具 - 批量")
        return self

    def print_page(self, image: Image.Image):
        """打印一张标签页"""
        if self.printer_dc is None:
            raise RuntimeError("打印机未初始化")

        # 缩放图片到目标尺寸
        if image.size != (self.page_width_px, self.page_height_px):
            image = image.resize(
                (self.page_width_px, self.page_height_px),
                Image.Resampling.NEAREST,
            )

        self.printer_dc.StartPage()
        dib = ImageWin.Dib(image)
        dib.draw(self.printer_dc.GetHandleOutput(), (0, 0, self.page_width_px, self.page_height_px))
        self.printer_dc.EndPage()

    def __exit__(self, exc_type, exc_val, exc_tb):
        import logging

        try:
            if exc_type is None:
                self.printer_dc.EndDoc()
                logging.info(f"批量打印任务完成，已提交到 {self.printer_name}")
            else:
                # 异常时中止打印
                self.printer_dc.AbortDoc()
                logging.error(f"批量打印中止: {exc_val}")
        finally:
            try:
                self.printer_dc.DeleteDC()
            except Exception:
                pass