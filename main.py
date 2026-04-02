"""
命令行入口：在项目根目录执行 ``python main.py``。
实现逻辑见 ``src/cli_main.py``；日常使用 Web 界面请执行 ``python app.py``。
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.cli_main import run_cli

if __name__ == "__main__":
    run_cli()
