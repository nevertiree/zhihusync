# 版本管理规范

本文档定义 zhihusync 项目的版本管理策略。

## 📌 版本号格式

采用 [语义化版本控制](https://semver.org/lang/zh-CN/) (Semantic Versioning)：

```
主版本号.次版本号.修订号 (MAJOR.MINOR.PATCH)

例如: 1.0.0, 1.2.3, 2.0.0
```

### 版本号递增规则

| 版本号 | 递增时机 | 示例 |
|--------|----------|------|
| **MAJOR** | 不兼容的 API 修改 | 架构重构、破坏性变更 |
| **MINOR** | 向下兼容的功能新增 | 新功能、新特性 |
| **PATCH** | 向下兼容的问题修复 | Bug 修复、性能优化 |

## 🌿 分支管理策略

```
main/master (生产分支)
  ↑
develop (开发分支)
  ↑
feature/* (功能分支)
  ↑
hotfix/* (紧急修复分支)
  ↑
release/* (发布分支)
```

### 分支说明

| 分支 | 用途 | 保护级别 |
|------|------|----------|
| `master` | 生产环境代码 | 🔒 受保护，必须通过 PR |
| `develop` | 开发集成 | 🔒 受保护，必须通过 PR |
| `feature/*` | 新功能开发 | 自由分支 |
| `hotfix/*` | 生产环境紧急修复 | 🔒 需审核 |
| `release/*` | 版本发布准备 | 🔒 需审核 |

## 🏷️ 标签管理

### 创建版本标签

```bash
# 1. 确保在 master 分支且代码已合并
git checkout master
git pull origin master

# 2. 创建标签
git tag -a v1.0.0 -m "Release version 1.0.0"

# 3. 推送标签到远程
git push origin v1.0.0
```

### 标签命名规范

- 版本标签: `v1.0.0`, `v1.2.0`
- 预发布标签: `v1.0.0-beta.1`, `v1.0.0-rc.1`
- 紧急修复标签: `v1.0.1-hotfix.1`

## 🐳 Docker 镜像版本

Docker 镜像标签与 Git 标签同步：

| Git 标签 | Docker 镜像 |
|----------|-------------|
| `v1.0.0` | `nevertiree26/zhihusync:v1.0.0` |
| `latest` | `nevertiree26/zhihusync:latest` |

### 发布流程

1. 在 GitHub 创建 Release
2. GitHub Actions 自动构建并推送 Docker 镜像
3. 镜像标签与 Git 标签一致

## 📋 发布检查清单

发布新版本前，确保完成以下检查：

- [ ] 版本号在代码中已更新
- [ ] CHANGELOG.md 已更新
- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] Docker 镜像构建成功
- [ ] 安装脚本测试通过

## 🚀 版本发布流程

### 标准发布流程

```bash
# 1. 从 develop 创建 release 分支
git checkout develop
git pull origin develop
git checkout -b release/v1.1.0

# 2. 更新版本号（如有必要）
# 修改 pyproject.toml、__init__.py 等

# 3. 提交版本更新
git add .
git commit -m "chore(release): 准备 v1.1.0 发布"
git push origin release/v1.1.0

# 4. 创建 PR 合并到 master
# 在 GitHub 上操作

# 5. 合并后打标签
git checkout master
git pull origin master
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0

# 6. 同步到 develop
git checkout develop
git merge master
git push origin develop
```

### 紧急修复流程 (Hotfix)

```bash
# 1. 从 master 创建 hotfix 分支
git checkout master
git checkout -b hotfix/v1.0.1

# 2. 修复问题并提交
# ...

# 3. 创建 PR 合并到 master 和 develop
git push origin hotfix/v1.0.1

# 4. 合并后打标签
git checkout master
git tag -a v1.0.1 -m "Hotfix v1.0.1"
git push origin v1.0.1
```

## 📚 历史版本

| 版本 | 发布日期 | 主要变更 |
|------|----------|----------|
| v1.0.0 | 2026-03-07 | 项目重构，统一版本管理 |

---

*本文档由项目维护者维护，如有疑问请提交 Issue。*
