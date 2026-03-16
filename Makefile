# Makefile for hybrid-search-practice
# 使用 `make <target>` 运行命令

.PHONY: help install dev lint format test clean hooks

# 默认显示帮助
help:
	@echo "Available targets:"
	@echo "  make install    - 安装项目依赖"
	@echo "  make dev        - 安装开发依赖并设置 pre-commit hooks"
	@echo "  make lint       - 运行代码检查 (ruff + mypy)"
	@echo "  make format     - 自动格式化代码 (ruff)"
	@echo "  make test       - 运行测试"
	@echo "  make hooks      - 安装 git pre-commit hooks"
	@echo "  make clean      - 清理缓存文件"

# 安装依赖
install:
	uv sync

# 安装开发依赖并设置环境
dev:
	uv sync --group dev
	uv run pre-commit install
	@echo "✅ Development environment ready! Pre-commit hooks installed."

# 运行代码检查
lint:
	@echo "🔍 Running ruff check..."
	uv run ruff check .
	@echo "🔍 Running mypy check..."
	uv run mypy .

# 自动修复和格式化
format:
	@echo "🔧 Auto-fixing with ruff..."
	uv run ruff check --fix .
	@echo "🔧 Formatting with ruff..."
	uv run ruff format .

# 运行测试
test:
	uv run pytest -v

# 运行集成测试
test-integration:
	uv run pytest -v -m integration

# 安装 pre-commit hooks
hooks:
	uv run pre-commit install
	@echo "✅ Pre-commit hooks installed!"

# 手动运行 pre-commit 检查所有文件
hooks-run:
	uv run pre-commit run --all-files

# 清理缓存文件
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache 2>/dev/null || true
	@echo "✅ Cache cleaned!"
