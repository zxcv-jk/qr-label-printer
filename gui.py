"""
Tkinter 主界面
- 6个输入框
- 生成预览 → 连续多页PDF + 纵向长图
- 开始打印 → 整批单次 StartDoc
- 打印任务锁、整批重复检查、线程安全
"""

import os
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
        self.root.geometry("520x520")
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

        row = 0
        self.entry_material = self._add_entry(main_frame, "物料编码：", row)
        row += 1
        self.entry_batch = self._add_entry(main_frame, "生产批次：", row)
        row += 1
        self.entry_packing = self._add_entry(main_frame, "装箱量：", row)
        row += 1
        self.entry_desc = self._add_entry(main_frame, "物料描述：", row,
                                          default=self.config.get("default_description", ""),
                                          justify="center")
        row += 1
        self.entry_serial = self._add_entry(main_frame, "起始流水号：", row, default="1")
        row += 1
        self.entry_quantity = self._add_entry(main_frame, "打印数量：", row, default="1")

        row += 1
        printer_frame = ttk.Frame(main_frame)
        printer_frame.grid(row=row, column=0, columnspan=2, pady=(10, 5), sticky="w")
        printer = get_printer(self.config) or "未检测到打印机"
        self.printer_var = tk.StringVar(value=f"当前打印机：{printer}")
        ttk.Label(printer_frame, textvariable=self.printer_var, foreground="gray").pack(side=tk.LEFT)
        ttk.Button(printer_frame, text="刷新", command=self._refresh_printer, width=6).pack(side=tk.LEFT, padx=(10, 0))

        row += 1
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(8, 5))
        self.btn_preview = ttk.Button(btn_frame, text="生成连续预览", command=self._preview, width=14)
        self.btn_preview.pack(side=tk.LEFT, padx=5)
        self.btn_print = ttk.Button(btn_frame, text="开始打印", command=self._print, width=12)
        self.btn_print.pack(side=tk.LEFT, padx=5)
        self.btn_history = ttk.Button(btn_frame, text="查看记录", command=self._view_history, width=12)
        self.btn_history.pack(side=tk.LEFT, padx=5)
        self.btn_logs = ttk.Button(btn_frame, text="打开日志目录", command=self._open_logs, width=12)
        self.btn_logs.pack(side=tk.LEFT, padx=5)

        row += 1
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        row += 1
        self.preview_info = tk.StringVar(value="")
        ttk.Label(main_frame, textvariable=self.preview_info, foreground="blue").grid(
            row=row, column=0, columnspan=2, pady=(5, 0)
        )

    def _add_entry(self, parent, label_text, row, default="", justify=None):
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", pady=3)
        entry = ttk.Entry(parent, width=35)
        entry.grid(row=row, column=1, sticky="w", padx=(5, 0), pady=3)
        if default:
            entry.insert(0, default)
        if justify:
            entry.config(justify=justify)
        return entry

    def _refresh_printer(self):
        printer = get_printer(self.config) or "未检测到打印机"
        self.printer_var.set(f"当前打印机：{printer}")
        self._set_status(f"打印机已刷新：{printer}")
        log_info(f"刷新打印机：{printer}")

    def _set_status(self, message: str):
        self.root.after(0, lambda: self.status_var.set(message))

    def _set_busy_state(self, busy: bool):
        """设置忙碌状态，禁用/启用按钮"""
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

                    output_dir = "output"
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
        """执行打印任务：整批一个 StartDoc 多页"""
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
                    # 使用 BatchPrinter 执行整批单次 StartDoc
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

                            # 直接打印（无需保存临时文件）
                            bp.print_page(label_img)

                            # 保存记录
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

                    # 完成
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
    def _get_data_dir() -> str:
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "data")

    @staticmethod
    def _get_logs_dir() -> str:
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "logs")

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