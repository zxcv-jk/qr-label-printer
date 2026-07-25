"""
Tkinter 主界面
- 6个输入框
- 生成预览、开始打印、查看记录、打开日志目录按钮
- 当前打印机显示
- 状态栏
"""

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter import simpledialog

from config_service import load_config
from error_handler import handle_exception, log_info, log_error, setup_logging
from history_service import (
    clear_progress,
    is_duplicate,
    load_progress,
    save_progress,
    save_record,
)
from label_generator import create_label_image, generate_qr_image, save_test_image
from printer_service import get_default_printer, get_printer, get_printer_list, print_label
from validator import build_qr_content, generate_serials, validate_and_process


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("二维码标签打印工具")
        self.root.geometry("520x520")
        self.root.resizable(False, False)

        # 加载配置
        self.config = load_config()

        # 初始化日志
        setup_logging()

        # 预览图片（保存第一张）
        self.preview_image = None
        self.preview_path = None

        # 创建界面
        self._build_ui()

        # 启动时检查未完成任务
        self.root.after(100, self._check_unfinished)

        log_info("程序启动")

    def _build_ui(self):
        """构建界面"""
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 输入区域
        row = 0
        self.entry_material = self._add_entry(main_frame, "物料编码：", row)
        row += 1
        self.entry_batch = self._add_entry(main_frame, "生产批次：", row, default="20260501")
        row += 1
        self.entry_packing = self._add_entry(main_frame, "装箱量：", row, default="14630")
        row += 1
        self.entry_desc = self._add_entry(main_frame, "物料描述：", row, default=self.config.get("default_description", ""))
        row += 1
        self.entry_serial = self._add_entry(main_frame, "起始流水号：", row, default="1")
        row += 1
        self.entry_quantity = self._add_entry(main_frame, "打印数量：", row, default="10")

        # 打印机信息
        row += 1
        printer_frame = ttk.Frame(main_frame)
        printer_frame.grid(row=row, column=0, columnspan=2, pady=(10, 5), sticky="w")
        self.printer_name = get_printer(self.config) or "未检测到打印机"
        ttk.Label(printer_frame, text=f"当前打印机：{self.printer_name}", foreground="gray").pack(side=tk.LEFT)
        ttk.Button(printer_frame, text="刷新", command=self._refresh_printer, width=6).pack(side=tk.LEFT, padx=(10, 0))

        # 按钮区域
        row += 1
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(8, 5))
        ttk.Button(btn_frame, text="生成预览", command=self._preview, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="开始打印", command=self._print, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="查看记录", command=self._view_history, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="打开日志目录", command=self._open_logs, width=12).pack(side=tk.LEFT, padx=5)

        # 状态栏
        row += 1
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W,
        )
        status_bar.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        # 预览提示标签
        row += 1
        self.preview_info = tk.StringVar(value="")
        ttk.Label(main_frame, textvariable=self.preview_info, foreground="blue").grid(
            row=row, column=0, columnspan=2, pady=(5, 0)
        )

    def _add_entry(self, parent, label_text, row, default=""):
        """添加一行带标签的输入框"""
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", pady=3)
        entry = ttk.Entry(parent, width=35)
        entry.grid(row=row, column=1, sticky="w", padx=(5, 0), pady=3)
        if default:
            entry.insert(0, default)
        return entry

    def _refresh_printer(self):
        """刷新打印机信息"""
        printer = get_printer(self.config) or "未检测到打印机"
        self.printer_name = printer
        self.status_var.set(f"打印机已刷新：{printer}")
        log_info(f"刷新打印机：{printer}")

    def _get_inputs(self) -> dict:
        """获取所有输入框的值（原始字符串）"""
        return {
            "material_code": self.entry_material.get(),
            "batch": self.entry_batch.get(),
            "packing_qty": self.entry_packing.get(),
            "description": self.entry_desc.get(),
            "serial_start": self.entry_serial.get(),
            "print_qty": self.entry_quantity.get(),
        }

    def _preview(self):
        """生成首张预览"""
        try:
            inputs = self._get_inputs()
            material_code, batch, packing_qty, serial_start, print_qty = validate_and_process(
                inputs["material_code"],
                inputs["batch"],
                inputs["packing_qty"],
                inputs["serial_start"],
                inputs["print_qty"],
            )

            # 拼接第一张二维码内容
            qr_content = build_qr_content(material_code, batch, packing_qty, serial_start)

            # 生成二维码
            qr_img = generate_qr_image(qr_content)

            # 生成标签
            label_img = create_label_image(
                qr_content=qr_content,
                qr_img=qr_img,
                material_code=material_code,
                batch=batch,
                packing_qty=packing_qty,
                serial=serial_start,
                description=inputs["description"],
                config=self.config,
            )

            # 保存预览图
            self.preview_path = save_test_image(label_img, filename="preview.png")
            self.preview_image = label_img

            self.status_var.set(f"预览已生成：{qr_content}")
            self.preview_info.set(f"预览内容：{qr_content}")
            log_info(f"预览生成成功：{qr_content}")

        except ValueError as e:
            messagebox.showwarning("输入错误", str(e))
        except Exception as e:
            msg = handle_exception(e)
            messagebox.showerror("错误", msg)

    def _print(self):
        """执行打印任务"""
        try:
            inputs = self._get_inputs()
            material_code, batch, packing_qty, serial_start, print_qty = validate_and_process(
                inputs["material_code"],
                inputs["batch"],
                inputs["packing_qty"],
                inputs["serial_start"],
                inputs["print_qty"],
            )

            # 获取打印机
            printer_name = get_printer(self.config)
            if not printer_name:
                messagebox.showerror("打印机错误",
                    "未检测到可用打印机。\n"
                    "请检查打印机是否开机、USB 是否连接、\n"
                    "Windows 打印驱动和默认打印机是否正常。")
                return

            # 检查是否重复
            first_content = build_qr_content(material_code, batch, packing_qty, serial_start)
            if is_duplicate(first_content):
                if not messagebox.askyesno("重复提醒",
                    "该二维码以前可能打印过，是否继续？\n"
                    "（不会影响已打印的标签）"):
                    self.status_var.set("用户取消打印")
                    return

            # 生成流水号列表
            serials = generate_serials(serial_start, print_qty)

            # 开始打印（在新线程中执行，避免界面卡顿）
            self.status_var.set(f"正在打印 0/{print_qty} ...")
            self.root.update()

            def print_task():
                try:
                    completed = 0
                    for i, serial in enumerate(serials):
                        qr_content = build_qr_content(material_code, batch, packing_qty, serial)

                        # 生成二维码
                        qr_img = generate_qr_image(qr_content)

                        # 生成标签
                        label_img = create_label_image(
                            qr_content=qr_content,
                            qr_img=qr_img,
                            material_code=material_code,
                            batch=batch,
                            packing_qty=packing_qty,
                            serial=serial,
                            description=inputs["description"],
                            config=self.config,
                        )

                        # 保存临时图片
                        temp_path = save_test_image(label_img, filename=f"temp_{serial}.png")

                        # 发送打印
                        print_label(temp_path, printer_name, self.config)

                        # 保存记录
                        save_record(
                            material_code=material_code,
                            batch=batch,
                            packing_qty=packing_qty,
                            serial=serial,
                            qr_content=qr_content,
                            printer_name=printer_name,
                        )

                        # 保存进度
                        completed += 1
                        save_progress(
                            material_code=material_code,
                            batch=batch,
                            packing_qty=packing_qty,
                            description=inputs["description"],
                            current_serial=int(serial),
                            total_count=print_qty,
                            completed_count=completed,
                        )

                        # 删除临时文件
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass

                        # 更新状态
                        self.status_var.set(f"正在打印 {completed}/{print_qty} ...")
                        log_info(f"已发送 [{completed}/{print_qty}]：{qr_content}")

                    # 完成
                    clear_progress()
                    self.status_var.set(f"打印完成，共发送 {print_qty} 张到打印机")
                    messagebox.showinfo("打印完成",
                        f"打印任务已发送到 Windows 打印队列。\n"
                        f"共 {print_qty} 张标签。\n"
                        f"请检查打印机是否正常出纸。")

                except Exception as e:
                    msg = handle_exception(e)
                    self.status_var.set(f"打印出错：{msg}")
                    log_error(f"打印过程中出错: {e}", exc_info=True)
                    messagebox.showerror("打印错误",
                        f"标签未能发送到打印机。\n"
                        f"请检查打印机是否开机、USB 是否连接、\n"
                        f"Windows 打印驱动和默认打印机是否正常。\n\n"
                        f"错误信息：{msg}")

            # 启动打印线程
            threading.Thread(target=print_task, daemon=True).start()

        except ValueError as e:
            messagebox.showwarning("输入错误", str(e))
        except Exception as e:
            msg = handle_exception(e)
            messagebox.showerror("错误", msg)

    def _view_history(self):
        """打开打印记录目录"""
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        os.startfile(data_dir)

    def _open_logs(self):
        """打开日志目录"""
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        os.startfile(logs_dir)

    def _check_unfinished(self):
        """检查上次是否有未完成的任务"""
        progress = load_progress()
        if progress is None:
            return

        material_code = progress.get("material_code", "")
        completed = progress.get("completed_count", 0)
        total = progress.get("total_count", 0)
        current_serial = progress.get("current_serial", 0)

        if completed >= total:
            clear_progress()
            return

        # 获取该目录下的文件路径
        project_dir = os.path.dirname(os.path.abspath(__file__))

        result = messagebox.askyesnocancel(
            "发现未完成的任务",
            f"上次打印任务未完成：\n"
            f"物料编码：{material_code}\n"
            f"已完成：{completed}/{total}\n"
            f"下一个流水号：{str(current_serial + 1).zfill(4)}\n\n"
            f"是否从下一个流水号继续？\n"
            f"（选择'是'=继续、'否'=重新开始、'取消'=跳过）"
        )

        if result is True:
            # 继续：设置输入框的值
            self.entry_material.delete(0, tk.END)
            self.entry_material.insert(0, material_code)
            self.entry_batch.delete(0, tk.END)
            self.entry_batch.insert(0, progress.get("batch", ""))
            self.entry_packing.delete(0, tk.END)
            self.entry_packing.insert(0, progress.get("packing_qty", ""))
            self.entry_desc.delete(0, tk.END)
            self.entry_desc.insert(0, progress.get("description", ""))
            self.entry_serial.delete(0, tk.END)
            self.entry_serial.insert(0, str(current_serial + 1))
            remaining = total - completed
            self.entry_quantity.delete(0, tk.END)
            self.entry_quantity.insert(0, str(remaining))
            self.status_var.set(f"已恢复未完成任务，剩余 {remaining} 张")
        elif result is False:
            # 重新开始：清除进度
            clear_progress()
            self.status_var.set("已重置，可重新开始打印")
        else:
            # 取消：保留进度文件，但不操作
            pass
