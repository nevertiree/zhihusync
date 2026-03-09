# ZhihuSync 项目 - AI Agent 公共知识库

> 本文档用于 Kimi 等 AI Agent 的上下文学习，包含项目规范、编程习惯和最佳实践。

---

## 📋 项目概述

**ZhihuSync** 是一个自动备份知乎点赞内容的工具，通过 Docker 部署，提供 Web 管理界面。

- **技术栈**: Python 3.10+, FastAPI, Playwright, Docker
- **代码风格**: Ruff (替代 Black+flake8+isort), MyPy 类型检查
- **Git 工作流**: Git Flow (master/production, feature/* branches)
- **远程仓库**: GitHub (github.com/nevertiree/zhihusync)

---

## 🔧 开发环境配置

### 必备工具

```bash
# Python 工具
pip install pre-commit ruff mypy pytest
pre-commit install  # 必须！

# Docker 工具
docker --version
docker-compose --version
```

### 代码检查（提交前必须执行）

```bash
# 完整检查
pre-commit run --all-files

# 手动检查（如果 pre-commit 跳过）
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/ --ignore-missing-imports

# 测试
pytest tests/unit/ -v -m unit
```

---

## 📝 代码规范

### Python 规范

```python
"""模块文档字符串使用 Google 风格.

该模块提供 XXX 功能，支持 YYY。

Examples:
    >>> # 使用示例
    >>> result = function_name(arg1, arg2)
    >>> print(result)
"""

from pathlib import Path  # 优先使用 pathlib 而非 os.path
from typing import Optional  # 类型注解必须

# 常量使用大写
DEFAULT_SCAN_INTERVAL: int = 30
DATA_DIR: Path = Path("/app/data")


def process_data(
    input_path: Path,
    output_dir: Optional[Path] = None,
    *,  # 强制关键字参数
    force: bool = False
) -> dict[str, any]:
    """处理数据并返回结果.

    Args:
        input_path: 输入文件路径
        output_dir: 输出目录，默认为 None
        force: 是否强制覆盖

    Returns:
        包含处理结果的字典

    Raises:
        FileNotFoundError: 当输入文件不存在时
    """
    if not input_path.exists():
        raise FileNotFoundError(f"文件不存在: {input_path}")

    # 处理逻辑...
    return {"status": "success"}
```

### Ruff 配置要点

```toml
[tool.ruff]
target-version = "py310"
line-length = 120
indent-width = 4

[tool.ruff.lint]
select = ["F", "E", "W", "I", "UP", "B", "C901", "SIM"]
ignore = ["E501", "E402", "B904"]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

### MyPy 配置要点

```toml
[tool.mypy]
python_version = "3.10"
check_untyped_defs = true
no_implicit_optional = true
strict_equality = true
show_error_codes = true
ignore_missing_imports = true
```

---

## 🌿 Git 工作流 (Git Flow)

### 分支规则

| 分支 | 用途 | 保护规则 |
|------|------|----------|
| `master` | 生产环境 | 禁止直接 push，必须通过 PR |
| `develop` | 开发集成 | 禁止直接 push，必须通过 PR |
| `feature/*` | 功能开发 | 可自由 push |
| `hotfix/*` | 紧急修复 | 可自由 push |

### Commit Message 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**:
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试
- `chore`: 构建/工具

**示例**:
```
feat(crawler): 添加知乎专栏文章备份功能

- 支持备份专栏文章
- 添加专栏解析器
- 更新数据库模型

Closes #123
```

### 开发流程

```bash
# 1. 创建功能分支
git checkout master
git pull origin master
git checkout -b feature/your-feature-name

# 2. 开发和提交
# ... 编写代码 ...
pre-commit run --all-files  # 必须！
git add .
git commit -m "feat(scope): description"

# 3. 推送并创建 PR
git push -u origin feature/your-feature-name
# 在 GitHub 创建 PR 到 master
```

---

## 🐳 Docker 开发规范

### 镜像精简原则

1. **多阶段构建**: 减小最终镜像体积
2. **清理缓存**: 安装依赖后清理
3. **国内镜像**: 使用国内镜像源加速
4. **版本锁定**: 明确指定基础镜像版本

## 🔌 API 设计规范

### 存储配置 API

**获取挂载信息**:
```
GET /api/storage/mounts
Response: {
  "in_docker": true,
  "hostname": "container_id",
  "mounts": {
    "html": {"container_path": "/app/data/html", "description": "HTML备份文件"},
    "db": {"container_path": "/app/data/meta", "description": "数据库文件"},
    "static": {"container_path": "/app/data/static", "description": "静态资源"},
    "images": {"container_path": "/app/data/images", "description": "图片文件"}
  },
  "mount_info": [...]  // Docker 挂载详情
}
```

**迁移存储路径**:
```
POST /api/storage/migrate
Body: {
  "html_path": "/new/path/html",
  "db_path": "/new/path/db",
  "static_path": "/new/path/static",
  "images_path": "/new/path/images"
}
Response: {
  "success": true,
  "message": "数据迁移完成，服务即将重启",
  "details": {
    "html": {"from": "...", "to": "...", "files_copied": 10},
    "db": {"from": "...", "to": "..."},
    "static": {"from": "...", "to": "...", "files_copied": 5},
    "images": {"from": "...", "to": "...", "files_copied": 20}
  }
}
```

**系统重启**:
```
POST /api/system/restart
Response: {"success": true, "message": "服务正在重启..."}
```

### 前端存储页面实现

**功能特点**:
- 显示当前 Docker 容器内的挂载路径
- 可编辑输入框修改存储路径
- 迁移前确认对话框
- 迁移进度显示
- 自动重启并刷新页面

**关键函数**:
```javascript
// 加载挂载信息
async function loadStorageMounts()

// 执行迁移
async function migrateStorage()

// 重启服务
async function restartService()
```

---

### 一键安装脚本规范

**安装脚本 (install.sh/install.ps1)**:
- 自动检测 Docker 环境
- **必须用户确认**数据目录（即使存在也不默认使用）
- 创建 Docker 所需的子目录 (html, meta, images, static)
- 使用 `docker run` 直接启动，不依赖 compose 文件

**卸载脚本 (uninstall.sh/uninstall.ps1)**:
- 从 Docker 容器自动检测数据目录
- **必须用户确认**数据目录（即使存在也不默认删除）
- 需要输入 `DELETE` 最终确认
- 可选删除 Docker 镜像

### 数据目录结构

```
data/
├── html/          # 备份的知乎回答 HTML
├── meta/          # 数据库和日志
│   ├── zhihusync.db
│   └── zhihusync.log
├── images/        # 下载的图片
└── static/        # 静态资源（头像等）
```

---

## 🧪 测试规范

### 测试分类

| 类型 | 目录 | 标记 | CI 运行 |
|------|------|------|---------|
| 单元测试 | `tests/unit/` | `@pytest.mark.unit` | ✅ |
| 集成测试 | `tests/integration/` | `@pytest.mark.integration` | ❌ |
| E2E 测试 | `tests/e2e/` | `@pytest.mark.e2e` | ❌ |

### 测试命令

```bash
# 单元测试（必须本地通过）
pytest tests/unit/ -v -m unit

# 集成测试（本地运行）
pytest tests/integration/ -v -m integration

# E2E 测试（需要浏览器）
pytest tests/e2e/ -v -m e2e
```

---

## 🔒 安全规范

### 敏感信息处理

1. **绝不提交**: 密码、密钥、Token、Cookie
2. **使用环境变量**: 通过 `.env` 或环境变量注入
3. **模板文件**: 配置使用 `.example` 后缀

### .gitignore 检查

```bash
git status
# 确保没有 .env、config.yaml 等敏感文件
```

---

## ⚠️ 常见错误与正确处理

### 错误 1: pre-commit 检查失败仍强行提交

```bash
# ❌ 错误
git commit -m "xxx"  # 检查失败
git push

# ✅ 正确
pre-commit run --all-files  # 修复问题
git add .
git commit -m "xxx"
git push
```

### 错误 2: 修改 Docker 配置不验证

```bash
# ❌ 错误
vim Dockerfile
git commit -m "update docker"
git push  # 构建失败

# ✅ 正确
vim Dockerfile
docker build -t test .  # 本地验证
git commit -m "fix(docker): xxx"
git push
```

### 错误 3: 忽略 ruff/mypy 警告

```bash
# ❌ 错误
ruff check src/  # 显示警告
# 忽略警告直接提交

# ✅ 正确
ruff check src/ --fix  # 自动修复
ruff format src/       # 格式化
mypy src/              # 类型检查
# 确认无警告后提交
```

---

## 📚 项目结构

```
zhihusync/
├── src/                    # Python 源代码
│   ├── app.py             # 应用入口
│   ├── crawler.py         # 爬虫核心
│   ├── web.py             # Web 服务
│   ├── storage.py         # 存储管理
│   ├── db.py              # 数据库操作
│   └── ...
├── tests/                  # 测试
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   └── e2e/               # E2E 测试
├── config/                 # 配置目录
├── data/                   # 数据目录（持久化）
├── templates/              # Web 模板
├── static/                 # Web 静态资源
├── install.sh              # Linux/macOS 一键安装
├── install.ps1             # Windows 一键安装
├── uninstall.sh            # Linux/macOS 一键卸载
├── uninstall.ps1           # Windows 一键卸载
├── docker-compose.yml      # Docker 配置
├── Dockerfile              # 镜像定义
├── pyproject.toml          # Python 项目配置
├── .pre-commit-config.yaml # pre-commit 配置
└── AGENTS.md               # 开发规范文档
```

---

## 🎯 AI Agent 工作指南

### 接到任务时的检查清单

1. **理解项目结构**: 查看 `src/` 目录，了解模块划分
2. **检查现有规范**: 阅读 `AGENTS.md` 和本知识库
3. **代码风格**: 使用 Ruff 格式化，MyPy 类型检查
4. **提交前**: 必须运行 `pre-commit run --all-files`
5. **Git 工作流**: 从 master 创建 `feature/*` 分支，通过 PR 合并

### 代码修改原则

1. **最小改动**: 只修改必要的代码
2. **保持风格**: 遵循现有代码的命名和结构
3. **类型安全**: 添加/修改函数时必须添加类型注解
4. **文档更新**: 修改功能时同步更新文档
5. **测试覆盖**: 新功能必须包含测试

### 与用户的交互原则

1. **确认理解**: 对模糊需求进行澄清
2. **提供选项**: 多个实现方案时让用户选择
3. **说明影响**: 告知修改可能带来的副作用
4. **安全检查**: 涉及删除操作时要求用户确认

---

## 🔗 参考资源

- [Ruff 文档](https://docs.astral.sh/ruff/)
- [MyPy 文档](https://mypy.readthedocs.io/)
- [pre-commit 文档](https://pre-commit.com/)
- [Git Flow 工作流](https://nvie.com/posts/a-successful-git-branching-model/)

---

*本文档作为 Kimi 公共知识库，用于所有与 ZhihuSync 项目相关的对话上下文。*
