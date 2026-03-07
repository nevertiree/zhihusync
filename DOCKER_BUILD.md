# Docker 构建与部署指南

## 快速选择

| 部署方式 | 命令 | 适用场景 |
|----------|------|----------|
| **Docker Hub（推荐）** | `docker-compose -f docker-compose.hub.yml up -d` | 网络不稳定，不想构建 |
| **本地标准版** | `docker-compose up -d` | 本地构建，约 1.8GB |
| **本地完整版** | `docker-compose --profile full up -d` | 需要 Firefox 备选，约 2.3GB |
| **本地精简版** | `docker-compose --profile minimal up -d` | 存储紧张，约 600MB |

---

## 镜像说明

### 标准版（推荐）`Dockerfile`
- **大小**: 约 1.8GB
- **浏览器**: 仅 Chromium
- **适用**: 大多数用户，网络一般，存储充足
- **构建**: `docker-compose up -d`

### 完整版 `Dockerfile.full`
- **大小**: 约 2.3GB
- **浏览器**: Chromium + Firefox
- **适用**: 需要浏览器备选方案的用户
- **构建**: `docker-compose --profile full up -d`

### 精简版 `Dockerfile.minimal`
- **大小**: 约 600MB（首次启动下载 400MB 浏览器）
- **浏览器**: 运行时下载 Chromium
- **适用**: 存储紧张，网络良好的用户
- **构建**: `docker-compose --profile minimal up -d`

---

## 常见问题

### 拉取超时 / 镜像太大

**方案 1: 使用精简版**
```bash
docker-compose --profile minimal up -d
```

**方案 2: 使用 Docker Hub 预构建镜像**
```bash
docker-compose -f docker-compose.hub.yml up -d
```

**方案 3: 配置镜像加速**
```json
// Docker Desktop → Settings → Docker Engine
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
```

### 构建卡在 apt-get update

检查网络连接，尝试更换 DNS：
```bash
docker build --dns 223.5.5.5 --dns 223.6.6.6 .
```

### 浏览器下载慢

已配置国内镜像源，如需修改请编辑 Dockerfile：
```dockerfile
ENV PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
```

---

## 高级配置

### 使用 Nginx 静态文件服务
```bash
# 标准版 + Nginx
docker-compose --profile nginx up -d

# Hub 版 + Nginx
docker-compose -f docker-compose.hub.yml --profile nginx up -d
```

### 开发模式（代码热更新）

使用 legacy 配置：
```bash
docker-compose -f docker/legacy/docker-compose.quick.yml up -d
```

---

## 旧版文件

已归档到 `docker/legacy/` 目录：
- `Dockerfile.base` - 基础镜像（已合并到主 Dockerfile）
- `Dockerfile.alpine` - Alpine 版本
- `Dockerfile.chromium` - Chromium 版本（现为默认）
- `Dockerfile.quick` - 快速开发版本
- `docker-compose.build.yml` - 旧构建配置
- `docker-compose.alternative.yml` - 替代方案
- `docker-compose.quick.yml` - 快速开发配置
