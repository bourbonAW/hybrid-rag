# lib/__init__.py
import sys
from pathlib import Path

# 将 pageindex 目录添加到 Python 路径
pageindex_path = Path(__file__).parent / "pageindex"
if str(pageindex_path) not in sys.path:
    sys.path.insert(0, str(pageindex_path))
