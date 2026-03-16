# 代码质量管理指南

本文档介绍项目使用的代码质量工具和最佳实践。

## 工具概览

| 工具 | 用途 | 配置位置 |
|------|------|----------|
| **Ruff** | Python linter 和 formatter | `pyproject.toml` |
| **MyPy** | 静态类型检查 | `pyproject.toml` |
| **Pre-commit** | Git hooks 管理 | `.pre-commit-config.yaml` |

## 快速开始

### 1. 安装开发依赖

```bash
make dev
# 或
uv sync --group dev
uv run pre-commit install
```

### 2. 代码检查

```bash
make lint
# 或
uv run ruff check .
uv run mypy .
```

### 3. 自动格式化

```bash
make format
# 或
uv run ruff check --fix .
uv run ruff format .
```

### 4. 运行测试

```bash
make test
# 或
uv run pytest -v
```

## Ruff 配置

### 启用的规则

- **E, W**: pycodestyle (代码风格)
- **F**: Pyflakes (未使用变量、未定义名称等)
- **I**: isort (import 排序)
- **N**: pep8-naming (命名规范)
- **D**: pydocstyle (文档字符串)
- **UP**: pyupgrade (Python 升级检查)
- **B**: flake8-bugbear (潜在 bug)
- **C4**: flake8-comprehensions (推导式优化)
- **SIM**: flake8-simplify (简化建议)
- **ASYNC**: flake8-async (异步代码检查)

### 忽略的规则

- `D100`: 模块级文档字符串非强制
- `D104`: 包级文档字符串非强制

### 代码风格

- 行长度: 100 字符
- 引号: 双引号
- 缩进: 4 个空格

## Pre-commit Hooks

提交代码时自动运行的检查：

1. **ruff**: 自动修复 lint 问题
2. **ruff-format**: 自动格式化代码
3. **mypy**: 类型检查
4. **通用检查**:
   - 文件末尾空行
   - 去除行尾空白
   - YAML/JSON 语法检查
   - 合并冲突标记检查
   - 调试语句检查 (breakpoint, pdb)
   - 私钥检查

## 手动运行 Pre-commit

```bash
# 检查所有文件
uv run pre-commit run --all-files

# 检查特定文件
uv run pre-commit run --files main.py

# 跳过特定 hook
SKIP=mypy git commit -m "xxx"
```

## CI/CD 建议

在 CI 中运行以下命令确保代码质量：

```bash
uv run ruff check . --no-fix
uv run mypy .
uv run pytest -v
```

## VS Code 集成

推荐安装扩展：

- **Ruff**: `charliermarsh.ruff` - 代码格式化和 lint
- **MyPy Type Checker**: `ms-python.mypy-type-checker` - 类型检查

### VS Code 设置

```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "ruff.lint.run": "onSave",
  "mypy-type-checker.args": ["--ignore-missing-imports"]
}
```

## 常见问题

### Pre-commit hook 失败

如果 hook 修改了文件，需要重新 `git add` 并提交：

```bash
git add .
git commit -m "xxx"
```

### 临时跳过检查

```bash
# 跳过所有 hooks
git commit --no-verify -m "xxx"

# 跳过特定 hook
SKIP=mypy git commit -m "xxx"
```

### MyPy 报告缺少类型

对于第三方库缺少类型支持的情况，已在 `pyproject.toml` 中配置忽略。

如果需要为特定模块添加类型忽略：

```python
import some_library  # type: ignore
```

## 参考文档

- [Ruff 文档](https://docs.astral.sh/ruff/)
- [MyPy 文档](https://mypy.readthedocs.io/)
- [Pre-commit 文档](https://pre-commit.com/)
