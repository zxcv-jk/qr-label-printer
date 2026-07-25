"""
QR Code 生成 + 完整标签图片生成
- 调用 qrcode 库生成二维码
- 使用 Pillow 创建 100×60mm 标签画布
- 绘制固定模板：左二维码、右四字段、下明文、下物料描述
"""

import io
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


def generate_qr_image(qr_content: str, box_size: int = 8) -> Image.Image:
    """
    生成 QR Code 图片
    qr_content: 拼接后的字符串
    box_size: 每个像素块的大小（越大二维码越清晰）
    返回 PIL Image 对象
    """
    qr = qrcode.QRCode(
        version=None,  # 自动选择版本
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("RGB")


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
    创建完整标签图片
    尺寸：根据 config 中的 DPI 计算（默认 203 DPI，100×60mm ≈ 800×480 px）
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

    # 字体定义
    font_title = _get_font(16)
    font_text = _get_font(14)
    font_small = _get_font(12)

    # 偏移量 (px)
    offset_x = int(config.get("offset_x_mm", 0) * dpi / 25.4)
    offset_y = int(config.get("offset_y_mm", 0) * dpi / 25.4)

    # 二维码尺寸 (px)
    qr_size_px = int(config.get("qr_size_mm", 30) * dpi / 25.4)
    qr_resized = qr_img.resize((qr_size_px, qr_size_px), Image.LANCZOS)

    # 放置二维码 - 左侧，带边距
    margin = 15
    qr_x = margin + offset_x
    qr_y = margin + offset_y
    canvas.paste(qr_resized, (qr_x, qr_y))

    # 右侧信息文本
    text_x = qr_x + qr_size_px + 15
    text_y = qr_y + 5

    # 打包量显示（去掉前置零）
    packing_display = str(int(packing_qty))

    lines_right = [
        (f"物料编码：{material_code}", font_text),
        (f"生产批次：{batch}", font_text),
        (f"装箱量：{packing_display}", font_text),
        (f"流水号：{serial}", font_text),
    ]

    line_height = 22
    for i, (text, font) in enumerate(lines_right):
        y_pos = text_y + i * line_height
        draw.text((text_x, y_pos), text, fill="black", font=font)

    # 下方明文 - 完整二维码内容
    bottom_y = height_px - 60 + offset_y
    draw.text(
        (margin + offset_x, bottom_y),
        qr_content,
        fill="black",
        font=font_text,
    )

    # 下方物料描述
    desc_y = bottom_y + 25
    desc_text = description.strip()
    if not desc_text:
        desc_text = config.get("default_description", "")
    # 处理过长描述，截断
    if len(desc_text) > 40:
        desc_text = desc_text[:37] + "..."

    # 绘制边框（可选，方便确认打印偏移）
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