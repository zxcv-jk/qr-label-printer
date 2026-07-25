"""
Tkinter 主界面
- 6个输入框（带字数统计）
- 生成预览 → 连续多页PDF + 纵向长图
- 开始打印 → 整批单次 StartDoc
- 打印任务锁、整批重复检查、线程安全
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from config_service import load_config
from error_handler import handle_exception, log_info, log_error, setup_logging
from history_service import (
    clear_progress,
    is_duplicate,
    load_progress,
    save_progress,
    save_record,
)
from label_generator import (
    create_label_image,
    create_multi_page_pdf,
    create_continuous_long_image,
    generate_qr_image,
    save_test_image,
)
from printer_service import BatchPrinter, get_default_printer, get_printer, get_printer_list
from validator import build_qr_content, generate_serials, validate_and_process


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("二维码标签打印工具")
        self.root.geometry("520x550")
        self.root.resizable(False, False)

        self.config = load_config()
        setup_logging()

        self.is_printing = False
        self.is_previewing = False

        self._build_ui()
        self.root.after(100, self._check_unfinished)

        log_info("程序启动")

    def _build_ui(self):
        """构建界面"""
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 三列布局：第0列标签，第1列输入框（填满），第2列字数提示
        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=0)

        # 输入区域配置：每行一个标签 + 输入框 + 字数统计标签
        row = 0
        self.entry_material, self.cnt_material = self._add_entry_with_counter(
            main_frame, "物料编码：", row, hint=""
        )
        row += 1
        self.entry_batch, self.cnt_batch = self._add_entry_with_counter(
            main_frame, "生产批次：", row, hint="8位数字"
        )
        row += 1
        self.entry_packing, self.cnt_packing = self._add_entry_with_counter(
            main_frame, "装箱量：", row, hint="1~5位数字"
        )
        row += 1
        self.entry_desc, _ = self._add_entry_with_counter(
            main_frame, "物料描述：", row,
            default=self.config.get("default_description", ""),
            justify="center",
        )
        row += 1
        self.entry_serial, self.cnt_serial = self._add_entry_with_counter(
            main_frame, "起始流水号：", row, default="1", hint="0~9999"
        )
        row += 1
        self.entry_quantity, self.cnt_quantity = self._add_entry_with_counter(
            main_frame, "打印数量：", row, default="1", hint=">0"
        )

        # 打印机信息
        row += 1
        printer_frame = ttk.Frame(main_frame)
        printer_frame.grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
        printer = get_printer(self.config) or "未检测到打印机"
        self.printer_var = tk.StringVar(value=f"当前打印机：{printer}")
        ttk.Label(printer_frame, textvariable=self.printer_var, foreground="gray").pack(side=tk.LEFT)
        ttk.Button(printer_frame, text="刷新", command=self._refresh_printer, width=6).pack(side=tk.LEFT, padx=(10, 0))

        # 按钮区域 - 居中
        row += 1
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=(8, 5))
        self.btn_preview = ttk.Button(btn_frame, text="生成连续预览", command=self._preview, width=14)
        self.btn_preview.pack(side=tk.LEFT, padx=5)
        self.btn_print = ttk.Button(btn_frame, text="开始打印", command=self._print, width=12)
        self.btn_print.pack(side=tk.LEFT, padx=5)
        self.btn_history = ttk.Button(btn_frame, text="查看记录", command=self._view_history, width=12)
        self.btn_history.pack(side=tk.LEFT, padx=5)
        self.btn_logs = ttk.Button(btn_frame, text="打开日志目录", command=self._open_logs, width=12)
        self.btn_logs.pack(side=tk.LEFT, padx=5)

        # 状态栏 - 居中
        row += 1
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.CENTER,
        )
        status_bar.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        # 预览提示 - 居中
        row += 1
        self.preview_info = tk.StringVar(value="")
        ttk.Label(main_frame, textvariable=self.preview_info, foreground="blue", anchor=tk.CENTER).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(5, 0)
        )

    def _add_entry_with_counter(self, parent, label_text, row, default="", hint="", justify=None):
        """
        添加一行：标签 + 输入框 + 字数统计/提示
        返回 (entry, counter_label)
        """
        # 标签（右对齐固定宽度）
        label = ttk.Label(parent, text=label_text, anchor=tk.E, width=10)
        label.grid(row=row, column=0, sticky="e", pady=3)

        # 输入框
        entry_kwargs = {"width": 30}
        if justify:
            entry_kwargs["justify"] = justify
        entry = ttk.Entry(parent, **entry_kwargs)
        entry.grid(row=row, column=1, sticky="ew" if justify else "w", padx=(5, 0), pady=3)
        if default:
            entry.insert(0, default)

        # 字数统计 + 提示
        hint_text = hint if hint else ""
        counter = ttk.Label(parent, text=f"[{len(entry.get())}] {hint_text}", foreground="gray", width=14)
        counter.grid(row=row, column=2, sticky="w", padx=(3, 0), pady=3)

        # 绑定输入事件更新字数
        def on_keyrelease(event, e=entry, c=counter, h=hint):
            text = e.get()
            c.config(text=f"[{len(text)}] {h}" if h else f"[{len(text)}]")

        entry.bind("<KeyRelease>", on_keyrelease)

        return entry, counter

    def _refresh_printer(self):
        printer = get_printer(self.config) or "未检测到打印机"
        self.printer_var.set(f"当前打印机：{printer}")
        self._set_status(f"打印机已刷新：{printer}")
        log_info(f"刷新打印机：{printer}")

    def _set_status(self, message: str):
        self.root.after(0, lambda: self.status_var.set(message))

    def _set_busy_state(self, busy: bool):
        if busy:
            self.is_printing = True
            self.is_previewing = True
        else:
            self.is_printing = False
            self.is_previewing = False
        state = tk.DISABLED if busy else tk.NORMAL
        self.root.after(0, lambda: self.btn_print.config(state=state))
        self.root.after(0, lambda: self.btn_preview.config(state=state))

    def _get_inputs(self) -> dict:
        return {
            "material_code": self.entry_material.get(),
            "batch": self.entry_batch.get(),
            "packing_qty": self.entry_packing.get(),
            "description": self.entry_desc.get(),
            "serial_start": self.entry_serial.get(),
            "print_qty": self.entry_quantity.get(),
        }

    def _preview(self):
        """生成连续预览：多页 PDF + 纵向长图"""
        if self.is_printing or self.is_previewing:
            messagebox.showinfo("提示", "正在处理中，请等待当前任务完成。")
            return

        try:
            inputs = self._get_inputs()
            material_code, batch, packing_qty, serial_start, print_qty = validate_and_process(
                inputs["material_code"], inputs["batch"], inputs["packing_qty"],
                inputs["serial_start"], inputs["print_qty"],
            )

            # 预览数量限制
            if print_qty > 500:
                raise ValueError("单次预览数量不能超过 500 张")

            serials = generate_serials(serial_start, print_qty)

            self._set_busy_state(True)
            self._set_status(f"正在生成 {print_qty} 张预览...")

            def preview_task():
                try:
                    labels = []
                    for serial in serials:
                        qr_content = build_qr_content(material_code, batch, packing_qty, serial)
                        qr_img = generate_qr_image(
                            qr_content, self.config.get("qr_size_mm", 31.0), self.config.get("dpi", 203)
                        )
                        label_img = create_label_image(
                            qr_content=qr_content, qr_img=qr_img,
                            material_code=material_code, batch=batch,
                            packing_qty=packing_qty, serial=serial,
                            description=inputs["description"], config=self.config,
                        )
                        labels.append(label_img)

                    if not labels:
                        raise RuntimeError("未生成任何标签")

                    output_dir = self._get_output_dir()
                    os.makedirs(output_dir, exist_ok=True)

                    # 生成多页 PDF
                    pdf_path = os.path.join(
                        output_dir,
                        f"二维码标签连续预览_{serial_start}-{str(int(serial_start) + print_qty - 1).zfill(4)}.pdf"
                    )
                    create_multi_page_pdf(labels, pdf_path, self.config)

                    # 生成纵向连续长图
                    png_path = os.path.join(
                        output_dir,
                        f"二维码标签连续长图_{serial_start}-{str(int(serial_start) + print_qty - 1).zfill(4)}.png"
                    )
                    create_continuous_long_image(labels, png_path)

                    self.root.after(0, lambda: self.preview_info.set(
                        f"已生成 {len(labels)} 张预览：{os.path.basename(pdf_path)}"
                    ))
                    self._set_status(f"预览完成，共 {len(labels)} 张")
                    log_info(f"连续预览生成成功：{pdf_path}")

                    # 自动打开 PDF
                    os.startfile(pdf_path)

                except Exception as e:
                    msg = handle_exception(e)
                    self.root.after(0, lambda m=msg: self._set_status(f"预览失败：{m}"))
                    log_error(f"预览生成失败: {e}", exc_info=True)
                    self.root.after(0, lambda: messagebox.showerror("预览错误", msg))
                finally:
                    self.root.after(0, lambda: self._set_busy_state(False))

            threading.Thread(target=preview_task, daemon=True).start()

        except ValueError as e:
            messagebox.showwarning("输入错误", str(e))
        except Exception as e:
            msg = handle_exception(e)
            messagebox.showerror("错误", msg)

    def _check_batch_duplicates(self, all_contents: list[str]) -> int:
        return sum(1 for content in all_contents if is_duplicate(content))

    def _print(self):
        if self.is_printing:
            messagebox.showinfo("提示", "正在打印中，请等待当前任务完成。")
            return

        try:
            inputs = self._get_inputs()
            material_code, batch, packing_qty, serial_start, print_qty = validate_and_process(
                inputs["material_code"], inputs["batch"], inputs["packing_qty"],
                inputs["serial_start"], inputs["print_qty"],
            )

            printer_name = get_printer(self.config)
            if not printer_name:
                messagebox.showerror("打印机错误",
                    "未检测到可用打印机。\n请检查打印机是否开机、USB 是否连接、\nWindows 打印驱动和默认打印机是否正常。")
                return

            serials = generate_serials(serial_start, print_qty)
            all_contents = [build_qr_content(material_code, batch, packing_qty, s) for s in serials]

            duplicate_count = self._check_batch_duplicates(all_contents)
            if duplicate_count > 0:
                if not messagebox.askyesno("重复提醒",
                    f"本次任务中有 {duplicate_count} 个二维码可能已经打印过，是否继续？\n"
                    "（不会影响已打印的标签）"):
                    self._set_status("用户取消打印")
                    return

            self._set_busy_state(True)
            self._set_status(f"正在打印 0/{print_qty} ...")

            def print_task():
                try:
                    with BatchPrinter(printer_name, self.config) as bp:
                        completed = 0
                        for i, serial in enumerate(serials):
                            qr_content = all_contents[i]

                            qr_img = generate_qr_image(
                                qr_content,
                                self.config.get("qr_size_mm", 31.0),
                                self.config.get("dpi", 203),
                            )
                            label_img = create_label_image(
                                qr_content=qr_content, qr_img=qr_img,
                                material_code=material_code, batch=batch,
                                packing_qty=packing_qty, serial=serial,
                                description=inputs["description"], config=self.config,
                            )

                            bp.print_page(label_img)

                            save_record(
                                material_code=material_code, batch=batch,
                                packing_qty=packing_qty, serial=serial,
                                qr_content=qr_content, printer_name=printer_name,
                            )

                            completed += 1
                            save_progress(
                                material_code=material_code, batch=batch,
                                packing_qty=packing_qty, description=inputs["description"],
                                current_serial=int(serial), total_count=print_qty,
                                completed_count=completed,
                            )

                            self.root.after(0, lambda c=completed, t=print_qty:
                                self.status_var.set(f"正在打印 {c}/{t} ..."))
                            log_info(f"已打印 [{completed}/{print_qty}]：{qr_content}")

                    clear_progress()
                    self.root.after(0, lambda: self.status_var.set(
                        f"打印完成，共发送 {print_qty} 张到打印机"))
                    self.root.after(0, lambda: messagebox.showinfo("打印完成",
                        f"打印任务已发送到 Windows 打印队列。\n共 {print_qty} 张标签。\n请检查打印机是否正常出纸。"))

                except Exception as e:
                    msg = handle_exception(e)
                    self.root.after(0, lambda m=msg: self.status_var.set(f"打印出错：{m}"))
                    log_error(f"打印过程中出错: {e}", exc_info=True)
                    self.root.after(0, lambda m=msg: messagebox.showerror("打印错误",
                        f"标签未能发送到打印机。\n请检查打印机是否开机、USB 是否连接、\n"
                        f"Windows 打印驱动和默认打印机是否正常。\n\n错误信息：{m}"))
                finally:
                    self.root.after(0, lambda: self._set_busy_state(False))

            threading.Thread(target=print_task, daemon=True).start()

        except ValueError as e:
            messagebox.showwarning("输入错误", str(e))
        except Exception as e:
            msg = handle_exception(e)
            messagebox.showerror("错误", msg)

    def _view_history(self):
        data_dir = self._get_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        os.startfile(data_dir)

    def _open_logs(self):
        logs_dir = self._get_logs_dir()
        os.makedirs(logs_dir, exist_ok=True)
        os.startfile(logs_dir)

    @staticmethod
    def _get_base_dir() -> str:
        """获取程序所在目录（EXE 旁边或源码目录）"""
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    @staticmethod
    def _get_data_dir() -> str:
        return os.path.join(Application._get_base_dir(), "data")

    @staticmethod
    def _get_logs_dir() -> str:
        return os.path.join(Application._get_base_dir(), "logs")

    @staticmethod
    def _get_output_dir() -> str:
        return os.path.join(Application._get_base_dir(), "output")

    def _check_unfinished(self):
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

        result = messagebox.askyesnocancel(
            "发现未完成的任务",
            f"上次打印任务未完成：\n物料编码：{material_code}\n"
            f"已完成：{completed}/{total}\n"
            f"下一个流水号：{str(current_serial + 1).zfill(4)}\n\n"
            f"是否从下一个流水号继续？\n"
            f"（选择'是'=继续、'否'=重新开始、'取消'=跳过）"
        )

        if result is True:
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
            self._set_status(f"已恢复未完成任务，剩余 {remaining} 张")
        elif result is False:
            clear_progress()
            self._set_status("已重置，可重新开始打印")