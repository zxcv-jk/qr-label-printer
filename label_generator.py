"""
QR Code 生成 + 完整标签图片生成
- 调用 qrcode 库生成二维码（最近邻缩放、4格白边、整数倍尺寸）
- 使用 Pillow 创建 100×60mm 标签画布
- 绘制固定模板：左二维码、右四字段、下明文、下物料描述
- 物料描述使用 textbbox 按实际像素宽度截断
"""

import math
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont

# 中文字体路径（Windows 常见系统字体）
_FONT_PATHS = [
    "C:/Windows/Fonts/simsun.ttc",       # 宋体
    "C:/Windows/Fonts/msyh.ttc",         # 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",       # 黑体
    "C:/Windows/Fonts/yahei.ttf",        # 雅黑
]


def _get_font(size: int = 14):
    """获取系统中文字体，找不到时使用默认字体"""
    for path in _FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_qr_image(qr_content: str, qr_size_mm: int = 30, dpi: int = 203) -> Image.Image:
    """
    生成 QR Code 图片，使用最近邻缩放确保纯黑白。

    - border=4（4格白边）
    - 先以 box_size=1 生成，计算模块数
    - 再以整数倍 box_size 重新生成，NEAREST 缩放到精确尺寸

    返回 PIL Image（RGB 模式）
    """
    # 第一步：以 box_size=1 生成，获取模块数
    qr_small = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=4,
    )
    qr_small.add_data(qr_content)
    qr_small.make(fit=True)

    # 计算目标像素尺寸
    target_px = int(qr_size_mm * dpi / 25.4)

    # 计算总模块数（含 border）
    modules = qr_small.modules_count
    total_modules = modules + 8  # border=4 两边共 8

    # 找到最接近目标尺寸的整数倍
    factor = max(1, round(target_px / total_modules))
    final_size = total_modules * factor

    # 第二步：以计算的 box_size 重新生成
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=factor,
        border=4,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # NEAREST 缩放到精确像素尺寸（消除任何微小偏差）
    if qr_img.size != (final_size, final_size):
        qr_img = qr_img.resize((final_size, final_size), Image.Resampling.NEAREST)

    return qr_img


def _truncate_text_to_fit(draw: ImageDraw.Draw, text: str, font: ImageFont, max_width: int) -> str:
    """
    根据可用像素宽度逐步截断文字，避免超出边界。
    """
    if not text:
        return text
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_width:
        return text
    # 逐步缩短
    for i in range(len(text) - 1, 0, -1):
        truncated = text[:i] + "..."
        bbox = draw.textbbox((0, 0), truncated, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return truncated
    return text[0] + "..." if text else ""


def create_label_image(
    qr_content: str,
    qr_img: Image.Image,
    material_code: str,
    batch: str,
    packing_qty: str,
    serial: str,
    description: str,
    config: dict,
) -> Image.Image:
    """
    创建完整标签图片。

    字体大小（203 DPI 参考值）：
    - 字段名称/值：28 px
    - 二维码明文：20 px
    - 物料描述：26 px
    """
    dpi = config.get("dpi", 203)
    width_mm = config.get("label_width_mm", 100)
    height_mm = config.get("label_height_mm", 60)

    # mm -> px
    width_px = int(width_mm * dpi / 25.4)
    height_px = int(height_mm * dpi / 25.4)

    # 创建白色画布
    canvas = Image.new("RGB", (width_px, height_px), "white")
    draw = ImageDraw.Draw(canvas)

    # 放大后的字体（issue #12）
    font_field = _get_font(28)       # 字段名称和值
    font_plain = _get_font(20)       # 二维码明文
    font_desc = _get_font(26)        # 物料描述

    # 偏移量 (px)
    offset_x = int(config.get("offset_x_mm", 0) * dpi / 25.4)
    offset_y = int(config.get("offset_y_mm", 0) * dpi / 25.4)

    # 二维码尺寸 (px)
    qr_size_px = qr_img.width  # 使用二维码实际尺寸
    margin = 12
    qr_x = margin + offset_x
    qr_y = margin + offset_y
    canvas.paste(qr_img, (qr_x, qr_y))

    # 右侧信息文本
    text_x = qr_x + qr_size_px + 12
    text_y = qr_y + 2

    # 装箱量显示（去掉前置零）
    packing_display = str(int(packing_qty))

    lines_right = [
        f"物料编码：{material_code}",
        f"生产批次：{batch}",
        f"装箱量：{packing_display}",
        f"流水号：{serial}",
    ]

    line_height = 34  # 28px 字体的行高
    for i, text in enumerate(lines_right):
        y_pos = text_y + i * line_height
        draw.text((text_x, y_pos), text, fill="black", font=font_field)

    # 下方明文 - 完整二维码内容
    # 计算可用宽度，居中对齐
    plain_y = height_px - 70 + offset_y
    plain_text = qr_content
    # 如果明文超出宽度，也用 textbbox 截断（但通常二维码内容较短）
    max_plain_width = width_px - margin * 2
    plain_text = _truncate_text_to_fit(draw, plain_text, font_plain, max_plain_width)
    draw.text(
        (margin + offset_x, plain_y),
        plain_text,
        fill="black",
        font=font_plain,
    )

    # 下方物料描述
    desc_y = plain_y + 30
    desc_text = description.strip()
    if not desc_text:
        desc_text = config.get("default_description", "")
    # 使用 textbbox 按实际宽度截断
    desc_max_width = width_px - margin * 2
    desc_text = _truncate_text_to_fit(draw, desc_text, font_desc, desc_max_width)
    draw.text(
        (margin + offset_x, desc_y),
        desc_text,
        fill="black",
        font=font_desc,
    )

    # 调试边框（issue #14）
    if config.get("draw_debug_border", False):
        draw.rectangle(
            [0, 0, width_px - 1, height_px - 1],
            outline="black",
            width=1,
        )

    return canvas


def save_test_image(image: Image.Image, output_dir: str = "output", filename: str = "test_label.png"):
    """保存测试标签图片到 output 目录"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    image.save(path)
    return path