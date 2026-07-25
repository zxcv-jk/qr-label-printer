"""
QR Code 生成 + 完整标签图片生成
- 调用 qrcode 库生成二维码（最近邻缩放、4格白边、整数倍尺寸）
- 使用 Pillow 创建 100×60mm 标签画布
- 所有关键位置使用毫米参数，可从 config.json 调节
- 支持生成连续多页 PDF 和纵向连续长图
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


def generate_qr_image(qr_content: str, qr_size_mm: float = 31.0, dpi: int = 203) -> Image.Image:
    """
    生成 QR Code 图片，使用最近邻缩放确保纯黑白。

    - border=4（4格白边）
    - 先以 box_size=1 生成，计算模块数
    - 再以整数倍 box_size 重新生成

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

    # NEAREST 缩放到精确像素尺寸
    if qr_img.size != (final_size, final_size):
        qr_img = qr_img.resize((final_size, final_size), Image.Resampling.NEAREST)

    return qr_img


def _truncate_text_to_fit(draw: ImageDraw.Draw, text: str, font: ImageFont, max_width_px: int) -> str:
    """根据可用像素宽度逐步截断文字"""
    if not text:
        return text
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_width_px:
        return text
    for i in range(len(text) - 1, 0, -1):
        truncated = text[:i] + "..."
        bbox = draw.textbbox((0, 0), truncated, font=font)
        if bbox[2] - bbox[0] <= max_width_px:
            return truncated
    return text[0] + "..." if text else ""


def _mm_to_px(mm: float, dpi: int) -> int:
    """毫米转像素"""
    return int(mm * dpi / 25.4)


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

    布局参数（可从 config.json 调整，单位：毫米）：
    - qr_size_mm: 二维码尺寸
    - margin_left_mm: 左侧边距
    - field_label_x_mm: 字段名称起始 X
    - field_first_y_mm: 第一行字段 Y
    - field_line_height_mm: 字段行高
    - content_y_mm: 二维码明文 Y
    - description_y_mm: 物料描述 Y
    - font_size_field: 字段字号（像素）
    - font_size_plain: 明文字号（像素）
    - font_size_desc: 描述字号（像素）
    """
    dpi = config.get("dpi", 203)
    width_mm = config.get("label_width_mm", 100)
    height_mm = config.get("label_height_mm", 60)

    width_px = _mm_to_px(width_mm, dpi)
    height_px = _mm_to_px(height_mm, dpi)

    # 创建白色画布
    canvas = Image.new("RGB", (width_px, height_px), "white")
    draw = ImageDraw.Draw(canvas)

    # 字体
    font_field = _get_font(config.get("font_size_field", 24))
    font_plain = _get_font(config.get("font_size_plain", 18))
    font_desc = _get_font(config.get("font_size_desc", 22))

    # 偏移量
    offset_x = _mm_to_px(config.get("offset_x_mm", 0), dpi)
    offset_y = _mm_to_px(config.get("offset_y_mm", 0), dpi)

    # ---------- 二维码 ----------
    margin_left = _mm_to_px(config.get("margin_left_mm", 4.0), dpi)
    qr_x = margin_left + offset_x
    qr_y = _mm_to_px(config.get("qr_y_mm", 4.0), dpi) + offset_y
    canvas.paste(qr_img, (qr_x, qr_y))

    # ---------- 右侧字段 ----------
    field_label_x = _mm_to_px(config.get("field_label_x_mm", 40.0), dpi) + offset_x
    field_value_x = _mm_to_px(config.get("field_value_x_mm", 62.0), dpi) + offset_x
    field_first_y = _mm_to_px(config.get("field_first_y_mm", 5.0), dpi) + offset_y
    field_line_h = _mm_to_px(config.get("field_line_height_mm", 7.0), dpi)

    field_labels = [
        ("物料编码：", material_code),
        ("生产批次：", batch),
        ("装箱量：",   packing_qty),
        ("流水号：",   serial),
    ]

    for i, (label, value) in enumerate(field_labels):
        y_pos = field_first_y + i * field_line_h
        draw.text((field_label_x, y_pos), label, fill="black", font=font_field)
        # 字段值纵向对齐固定位置
        draw.text((field_value_x, y_pos), value, fill="black", font=font_field)

    # ---------- 下方二维码明文 ----------
    desc_font_for_plain = _get_font(config.get("font_size_plain", 18))
    content_y = _mm_to_px(config.get("content_y_mm", 39.0), dpi) + offset_y
    max_content_width = width_px - _mm_to_px(config.get("margin_left_mm", 4.0) * 2, dpi)
    display_content = _truncate_text_to_fit(draw, qr_content, desc_font_for_plain, max_content_width)
    draw.text((margin_left + offset_x, content_y), display_content, fill="black", font=desc_font_for_plain)

    # ---------- 底部物料描述 ----------
    desc_font = _get_font(config.get("font_size_desc", 22))
    desc_y = _mm_to_px(config.get("description_y_mm", 49.0), dpi) + offset_y
    desc_text = description.strip()
    if not desc_text:
        desc_text = config.get("default_description", "")
    desc_text = _truncate_text_to_fit(draw, desc_text, desc_font, max_content_width)
    draw.text((margin_left + offset_x, desc_y), desc_text, fill="black", font=desc_font)

    # 调试边框
    if config.get("draw_debug_border", False):
        draw.rectangle([0, 0, width_px - 1, height_px - 1], outline="black", width=1)

    return canvas


def create_multi_page_pdf(
    images: list[Image.Image],
    output_path: str,
    config: dict,
):
    """
    将多张标签图片保存为多页 PDF（每张标签一页）。

    需要配合：保存时使用 Pillow 的 PDF 保存功能，
    第一张图片 save() 时传入 append_images。
    """
    dpi = config.get("dpi", 203)
    if not images:
        return None

    # 所有图片转为 RGB
    rgb_images = [img.convert("RGB") for img in images]

    # 第一张作为主图，其余作为附加页
    first = rgb_images[0]
    rest = rgb_images[1:] if len(rgb_images) > 1 else None

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    first.save(
        output_path,
        format="PDF",
        save_all=True,
        append_images=rest,
        dpi=(dpi, dpi),
        title="二维码标签连续预览",
    )
    return output_path


def create_continuous_long_image(
    images: list[Image.Image],
    output_path: str,
) -> str:
    """
    将多张标签图片纵向拼接为一张长图，
    便于快速查看流水号是否断号、跳号。
    """
    if not images:
        return None

    # 所有图片宽度一致
    widths = [img.width for img in images]
    max_width = max(widths) if widths else 0
    total_height = sum(img.height for img in images)

    # 创建纵向长图，每张标签之间加 2px 分隔线
    separator = 2
    long_img = Image.new(
        "RGB",
        (max_width, total_height + separator * (len(images) - 1)),
        "white",
    )
    y_offset = 0
    for i, img in enumerate(images):
        # 如果宽度不一致，居中放置
        x_offset = (max_width - img.width) // 2
        long_img.paste(img, (x_offset, y_offset))
        y_offset += img.height
        if i < len(images) - 1:
            # 画分隔线
            for s in range(separator):
                for x in range(max_width):
                    long_img.putpixel((x, y_offset + s), (200, 200, 200))
            y_offset += separator

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    long_img.save(output_path)
    return output_path


def save_test_image(image: Image.Image, output_dir: str = "output", filename: str = "test_label.png"):
    """保存测试标签图片到 output 目录"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    image.save(path)
    return path