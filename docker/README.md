# Docker 配置归档目录

此目录包含已归档的旧版 Docker 配置文件。

## 当前推荐配置（项目根目录）

| 文件 | 用途 |
|------|------|
| `Dockerfile` | 标准版（Chromium，约 1.8GB）- 推荐 |
| `Dockerfile.full` | 完整版（Chromium + Firefox，约 2.3GB） |
| `Dockerfile.minimal` | 精简版（运行时下载浏览器，约 600MB） |
| `docker-compose.yml` | 本地构建配置（支持多 profile） |
| `docker-compose.hub.yml` | Docker Hub 预构建镜像配置 |

## 已归档文件

### legacy/ 目录

| 原文件 | 说明 | 归档原因 |
|--------|------|----------|
| `Dockerfile.base` | 基础镜像 | 功能合并到主 Dockerfile |
| `Dockerfile.alpine` | Alpine 版本 | 维护复杂，使用场景少 |
| `Dockerfile.quick` | 快速开发版 | 功能被精简版替代 |
| `Dockerfile.chromium.backup` | Chromium 备份 | 现为默认 Dockerfile |
| `docker-compose.build.yml` | 多方案构建配置 | 功能合并到主 compose |
| `docker-compose.alternative.yml` | 替代方案 | 使用场景少 |
| `docker-compose.quick.yml` | 快速开发配置 | 功能被主 compose 替代 |

## 迁移指南

### 从旧配置迁移

**原命令:**
```bash
docker-compose -f docker-compose.build.yml up -d
docker-compose -f docker-compose.build.yml --profile alpine up -d
```

**新命令:**
```bash
docker-compose up -d                    # 标准版（替代原 chromium）
# Alpine 版本不再维护，请使用标准版或精简版
docker-compose --profile minimal up -d  # 精简版（约 600MB）
```

### 如需使用旧配置

旧配置文件仍可使用：
```bash
docker-compose -f docker/legacy/docker-compose.build.yml up -d
```
