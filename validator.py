"""
字段处理和流水号逻辑
- 去除首尾空格
- 物料编码只检查非空
- 生产批次检查 8 位数字
- 装箱量补成 5 位
- 流水号补成 4 位并递增
- 打印数量校验
"""


def validate_and_process(
    material_code: str,
    batch: str,
    packing_qty: str,
    serial_start: str,
    print_qty: str,
):
    """
    校验所有输入字段，返回处理后的值或抛出 ValueError。
    返回: (material_code, batch, packing_qty_padded, serial_start_padded, print_qty_int)
    """
    # 1. 物料编码 - 去空格，不能为空
    material_code = material_code.strip()
    if not material_code:
        raise ValueError("物料编码不能为空")

    # 2. 生产批次 - 去空格，必须为 8 位数字
    batch = batch.strip()
    if not batch.isdigit() or len(batch) != 8:
        raise ValueError("生产批次必须为 8 位数字")

    # 3. 装箱量 - 去空格，1~5 位数字，补成 5 位
    packing_qty = packing_qty.strip()
    if not packing_qty.isdigit() or not (1 <= len(packing_qty) <= 5):
        raise ValueError("装箱量必须为 1~5 位数字")
    packing_qty_padded = packing_qty.zfill(5)

    # 4. 起始流水号 - 非负整数，补成 4 位
    serial_start = serial_start.strip()
    if not serial_start.isdigit():
        raise ValueError("起始流水号必须为非负整数")
    serial_int = int(serial_start)
    if serial_int < 0 or serial_int > 9999:
        raise ValueError("流水号范围必须在 0~9999 之间")
    serial_padded = str(serial_int).zfill(4)

    # 5. 打印数量 - 大于 0 的整数
    print_qty = print_qty.strip()
    if not print_qty.isdigit() or int(print_qty) <= 0:
        raise ValueError("打印数量必须为大于 0 的整数")
    print_qty_int = int(print_qty)

    # 6. 检查最终流水号不超过 9999
    final_serial = serial_int + print_qty_int - 1
    if final_serial > 9999:
        raise ValueError(
            f"起始流水号 {serial_int} + 打印数量 {print_qty_int} - 1 = {final_serial}，"
            f"超过流水号范围上限 9999"
        )

    return material_code, batch, packing_qty_padded, serial_padded, print_qty_int


def build_qr_content(
    material_code: str, batch: str, packing_qty: str, serial: str
) -> str:
    """按顺序拼接二维码内容：物料编码 + 生产批次 + 装箱量 + 流水号"""
    return material_code + batch + packing_qty + serial


def generate_serials(serial_padded: str, print_qty: int):
    """根据起始流水号和打印数量，生成流水号列表"""
    start = int(serial_padded)
    return [str(start + i).zfill(4) for i in range(print_qty)]