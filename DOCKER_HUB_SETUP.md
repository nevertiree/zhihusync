# Docker Hub 自动构建配置

GitHub Actions 已配置自动构建和推送 Docker 镜像到 Docker Hub。

## 🔐 配置 Secrets

需要在 GitHub 仓库设置以下 Secrets：

1. 打开 GitHub 仓库 → Settings → Secrets and variables → Actions
2. 点击 "New repository secret"
3. 添加以下两个 secrets：

| Secret Name | Value |
|-------------|-------|
| `DOCKER_USERNAME` | nevertiree26 |
| `DOCKER_PASSWORD` | 你的 Docker Hub 密码或访问令牌 |

> 💡 **建议使用访问令牌**：Docker Hub → Account Settings → Security → New Access Token

## 🚀 触发构建

配置完成后，以下情况会自动触发构建：

| 触发条件 | 构建标签 |
|----------|----------|
| 推送代码到 `master` 分支 | `latest` |
| 推送 tag `v0.7.1` | `v0.7.1`, `v0.7` |
| 手动触发 (workflow_dispatch) | 自定义版本号 |

## 📦 构建的镜像标签

- `nevertiree26/zhihusync:latest` - 默认最新版（完整版）
- `nevertiree26/zhihusync:slim` - 轻量级版本（仅 Chromium）
- `nevertiree26/zhihusync:v0.7.1` - 版本标签

## 🔧 手动触发构建

1. 打开 GitHub 仓库 → Actions → Build and Push Docker Image
2. 点击 "Run workflow"
3. 输入版本号（如 `v0.7.1`）
4. 点击 "Run workflow"

## 📊 查看构建状态

- GitHub: https://github.com/nevertiree/zhihusync/actions
- Docker Hub: https://hub.docker.com/r/nevertiree26/zhihusync
