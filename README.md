# 二维码标签打印工具

Windows 桌面小工具，用于批量生成并打印 QR Code 流水标签。

## 环境要求

- **操作系统：** Windows 10/11（64 位或 32 位均可）
- **Python：** 3.10 或更高版本（仅开发需要，运行时不需要）
- **打印机：** 支持 Windows 打印驱动的标签打印机（如得力 DL-888TW）

## 快速开始（开发模式）

```bash
# 1. 克隆仓库
git clone https://github.com/zxcv-jk/qr-label-printer.git
cd qr-label-printer

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境
.\venv\Scripts\activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 运行程序
python main.py
```

## 功能说明

操作员填写以下信息：
- 物料编码（不限位数）
- 生产批次（8 位数字）
- 装箱量（自动补成 5 位）
- 物料描述（可修改）
- 起始流水号（自动补成 4 位，每张 +1）
- 打印数量

程序自动完成：
1. 字段校验和格式化
2. 内容拼接（物料编码 + 生产批次 + 装箱量 + 流水号，无分隔符）
3. QR Code 生成（最近邻缩放，纯黑白，4 格白边）
4. 100×60mm 标签排版（左二维码 + 右字段 + 下明文 + 下物料描述）
5. 首张预览（自动打开图片）
6. 批量流水号递增
7. 调用 Windows 打印机驱动
8. 保存打印记录（CSV）和运行日志

## 项目结构

```
qr_label_printer/
├─ main.py                 # 程序入口
├─ gui.py                  # Tkinter 主界面
├─ validator.py            # 字段校验和流水号逻辑
├─ label_generator.py      # QR Code 和标签图片生成
├─ printer_service.py      # Windows 打印机操作
├─ config_service.py       # 配置读写
├─ history_service.py      # 打印记录和中断恢复
├─ error_handler.py        # 日志和异常处理
├─ config.json             # 打印机、尺寸、偏移等配置
├─ requirements.txt        # 运行时依赖
├─ README.md               # 本文件
├─ data/                   # 打印记录（自动生成）
├─ logs/                   # 运行日志（自动生成）
└─ output/                 # 测试图片（自动生成）
```

## 配置说明

编辑 `config.json` 调整以下参数：

| 参数 | 说明 | 默认值 |
|---|---|---|
| `printer_name` | 指定打印机名称 | `""`（空表示使用默认） |
| `use_default_printer` | 是否使用 Windows 默认打印机 | `true` |
| `force_configured_printer` | 找不到指定打印机时是否报错 | `false` |
| `label_width_mm` | 标签宽度（毫米） | `100` |
| `label_height_mm` | 标签高度（毫米） | `60` |
| `dpi` | 打印分辨率 | `203` |
| `offset_x_mm` | 水平偏移（毫米） | `0` |
| `offset_y_mm` | 垂直偏移（毫米） | `0` |
| `qr_size_mm` | 二维码尺寸（毫米） | `30` |
| `default_description` | 默认物料描述 | `"请填写物料描述"` |
| `draw_debug_border` | 绘制调试边框 | `false` |

## 打包为 EXE

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包为文件夹版（推荐首次使用）
pyinstaller --noconsole --onedir --name 二维码标签打印工具 main.py

# 打包后的文件在 dist/二维码标签打印工具/
# 将整个文件夹 + config.json 发给现场即可
# config.json、data/、logs/ 会自动在 EXE 旁边创建
```

## 打印记录

- 打印记录保存在 `data/print_history.csv`
- 中断恢复信息保存在 `data/last_progress.json`
- 运行日志保存在 `logs/app.log`

## 已知限制（第一版）

- 暂不支持 PDF、Excel 导入
- 暂不支持 ERP/MES/WMS 对接
- 暂不支持 Code 128、Data Matrix 等其他条码格式
- 暂不支持自由拖动模板
- 纸张尺寸和方向依赖打印机驱动预设

## License

MIT