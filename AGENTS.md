# AGENTS.md - 开发规范与最佳实践

本文档包含本项目的重要开发规范和最佳实践，所有贡献者（包括 AI Agent）都必须遵守。

---

## 🚨 铁律（不可违反）

### 1. 代码检查必须在本地通过后才能提交

**任何代码检查失败都不能提交到远程仓库。**

#### 环境设置（首次）

```bash
# 1. 安装 pre-commit
pip install pre-commit

# 2. 安装 git hooks
pre-commit install

# 3. 验证安装
pre-commit --version  # 应显示版本号
```

#### 本地检查流程

在每次 `git commit` 前，必须确保以下检查全部通过：

```bash
# 1. 运行 pre-commit 检查
pre-commit run --all-files

# 2. 手动运行代码质量检查（如果 pre-commit 跳过）
ruff check src/ tests/
black --check src/ tests/
mypy src/ --ignore-missing-imports

# 3. 运行测试（分层测试）
# 单元测试（快速，GitHub Actions 会运行）
pytest tests/unit/ -v -m unit

# 集成测试（本地运行，GitHub Actions 不运行）
pytest tests/integration/ -v -m integration

# E2E 测试（本地运行，需要浏览器）
pytest tests/e2e/ -v -m e2e
```

> ⚠️ **重要**：
> - 如果没有安装 pre-commit，代码检查将不会运行，可能导致提交不符合规范的代码！
> - 集成测试和 E2E 测试需要在本地完成后再提交（GitHub Actions 不运行这些测试）

#### pre-commit 钩子说明

本项目配置了以下 pre-commit 钩子（`.pre-commit-config.yaml`）：

| 钩子 | 作用 | 文件类型 |
|------|------|----------|
| `trailing-whitespace` | 去除行尾空格 | 所有 |
| `end-of-file-fixer` | 确保文件末尾有空行 | 所有 |
| `check-yaml` | 验证 YAML 语法 | YAML |
| `check-added-large-files` | 禁止大文件 | 所有 |
| `ruff` | Python 代码检查 | Python |
| `black` | Python 代码格式化 | Python |
| `mypy` | Python 类型检查 | Python |
| `prettier` | 前端代码格式化 | JS/JSON/YAML/CSS/HTML |

**注意**：
- 如果 pre-commit 显示 `Skipped`，说明没有相关文件被修改。但对于 Python 项目，提交前**必须**手动运行 ruff/black/mypy 检查。
- **版本一致性**：`.pre-commit-config.yaml` 中的工具版本必须与 GitHub Actions 保持一致，否则检查规则可能不同！
  ```bash
  # 定期更新 pre-commit 版本
  pre-commit autoupdate
  ```

---

## 📝 提交规范

### 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Type 类型

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `docs` | 文档更新 |
| `style` | 代码格式（不影响代码运行）|
| `refactor` | 重构 |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建过程或辅助工具的变动 |

#### 示例

```
feat(crawler): 添加知乎专栏文章备份功能

- 支持备份专栏文章
- 添加专栏解析器
- 更新数据库模型

Closes #123
```

---

## 🐳 Docker 开发规范

### 镜像精简原则

1. **多阶段构建**：使用多阶段构建减小镜像体积
2. **清理缓存**：安装依赖后清理缓存
3. **国内镜像**：使用国内镜像源加速构建
4. **版本锁定**：明确指定基础镜像版本

### 构建前检查

```bash
# 验证 Dockerfile 语法
docker build -t test:latest -f Dockerfile .

# 验证 docker-compose 配置
docker-compose config

# 检查镜像大小
docker images test:latest
```

---

## 🧪 测试规范

### 测试分类

| 类型 | 目录 | 标记 | 说明 |
|------|------|------|------|
| 单元测试 | `tests/unit/` | `@pytest.mark.unit` | 测试独立函数/类 |
| 集成测试 | `tests/integration/` | `@pytest.mark.integration` | 测试模块间交互 |
| E2E 测试 | `tests/e2e/` | `@pytest.mark.e2e` | 端到端测试 |

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定类型测试
pytest tests/unit/ -v -m unit
pytest tests/integration/ -v -m integration
pytest tests/e2e/ -v -m e2e
```

---

## 🔒 安全规范

### 敏感信息处理

1. **绝不提交**：密码、密钥、Token、Cookie 等
2. **使用环境变量**：通过 `.env` 或环境变量注入
3. **模板文件**：配置使用 `.example` 后缀

### .gitignore 检查

提交前检查是否意外提交了敏感文件：

```bash
git status
# 确保没有 .env、config.yaml 等敏感文件
```

---

## 🔄 工作流程

### 功能开发流程

1. **创建分支**：`git checkout -b feature/xxx`
2. **本地开发**：编写代码
3. **本地检查**：运行 pre-commit 和测试
4. **提交代码**：`git commit -m "feat: xxx"`
5. **推送分支**：`git push origin feature/xxx`
6. **创建 PR**：在 GitHub 创建 Pull Request
7. **等待 CI**：确保所有检查通过
8. **合并代码**：合并到 master

### 紧急修复流程

1. **创建分支**：`git checkout -b hotfix/xxx`
2. **修复问题**：编写修复代码
3. **本地检查**：运行 pre-commit 和测试
4. **提交推送**：commit 并 push
5. **快速审核**：简化审核流程
6. **合并部署**：合并并立即部署

---

## ⚠️ 常见错误

### 错误 1：pre-commit 检查失败仍强行提交

```bash
# ❌ 错误
git commit -m "xxx"  # 检查失败
git push  # 强行推送，导致 CI 失败

# ✅ 正确
pre-commit run --all-files  # 修复问题
git add .
git commit -m "xxx"
git push
```

### 错误 2：修改 Docker 配置不验证

```bash
# ❌ 错误
vim Dockerfile
git add .
git commit -m "update docker"
git push  # 构建失败

# ✅ 正确
vim Dockerfile
docker build -t test .  # 本地验证
git add .
git commit -m "fix(docker): xxx"
git push
```

### 错误 3：忽略 ruff/black/mypy 警告

```bash
# ❌ 错误
ruff check src/  # 显示警告
# 忽略警告直接提交

# ✅ 正确
ruff check src/ --fix  # 自动修复
black src/  # 格式化
mypy src/   # 类型检查
# 确认无警告后提交
```

---

## 📚 参考文档

- [pre-commit 文档](https://pre-commit.com/)
- [ruff 文档](https://docs.astral.sh/ruff/)
- [black 文档](https://black.readthedocs.io/)
- [pytest 文档](https://docs.pytest.org/)

---

*本文档由 AI Agent 维护，如有更新需求请在 PR 中说明。*
