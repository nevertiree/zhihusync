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
| 推送代码到 `master` 分支 | `latest`, `full`, `minimal` |
| 推送 tag `v0.7.1` | `v0.7.1`, `full-v0.7.1`, `minimal-v0.7.1` |
| 手动触发 (workflow_dispatch) | 自定义版本号 |

## 📦 镜像标签说明

| 标签 | Dockerfile | 大小 | 说明 |
|------|------------|------|------|
| `nevertiree26/zhihusync:latest` | Dockerfile | ~1.8GB | 标准版，仅 Chromium，推荐 |
| `nevertiree26/zhihusync:full` | Dockerfile.full | ~2.3GB | 完整版，Chromium + Firefox |
| `nevertiree26/zhihusync:minimal` | Dockerfile.minimal | ~600MB | 精简版，首次启动下载浏览器 |
| `nevertiree26/zhihusync:v0.7.1` | Dockerfile | ~1.8GB | 版本标签（标准版） |
| `nevertiree26/zhihusync:full-v0.7.1` | Dockerfile.full | ~2.3GB | 版本标签（完整版） |
| `nevertiree26/zhihusync:minimal-v0.7.1` | Dockerfile.minimal | ~600MB | 版本标签（精简版） |

## 🚀 使用方式

```bash
# 标准版（推荐，约 1.8GB）
docker pull nevertiree26/zhihusync:latest
docker-compose -f docker-compose.hub.yml up -d

# 完整版（需要 Firefox 备选，约 2.3GB）
docker pull nevertiree26/zhihusync:full
docker run -d -p 6067:6067 nevertiree26/zhihusync:full

# 精简版（存储紧张，约 600MB，首次启动下载浏览器）
docker pull nevertiree26/zhihusync:minimal
docker run -d -p 6067:6067 nevertiree26/zhihusync:minimal
```

## 🔧 手动触发构建

1. 打开 GitHub 仓库 → Actions → Build and Push Docker Image
2. 点击 "Run workflow"
3. 输入版本号（如 `v0.7.1`）
4. 点击 "Run workflow"

## 📊 查看构建状态

- GitHub: https://github.com/nevertiree/zhihusync/actions
- Docker Hub: https://hub.docker.com/r/nevertiree26/zhihusync

## ⚠️ 镜像拉取超时解决

如果镜像太大导致拉取超时：

1. **使用精简版**（约 600MB）：
   ```bash
   docker pull nevertiree26/zhihusync:minimal
   ```

2. **配置镜像加速**（Docker Desktop → Settings）：
   ```json
   {
     "registry-mirrors": [
       "https://docker.mirrors.ustc.edu.cn",
       "https://hub-mirror.c.163.com"
     ]
   }
   ```
