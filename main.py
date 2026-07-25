"""
程序入口 - 二维码标签打印工具
只负责初始化并打开主窗口
"""

import sys
import os

# 确保当前目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from gui import Application


def main():
    root = tk.Tk()
    app = Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()