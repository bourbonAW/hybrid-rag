# lib/__init__.py
import sys
from pathlib import Path

_lib_dir = Path(__file__).parent

# 将 submodules 添加到 Python 路径
for _name in ["pageindex", "hirag"]:
    _path = _lib_dir / _name
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
