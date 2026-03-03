# Docker 构建与部署指南

## 问题描述

在国内构建 Docker 镜像时，可能会遇到以下错误：

```
E: Failed to fetch http://deb.debian.org/debian/pool/main/f/fonts-noto-cjk/...
500  reading HTTP response body: unexpected EOF
```

这是因为 Debian 官方源在国内访问不稳定。

---

## 🎁 镜像特性

### 浏览器已打包（NAS 友好）

从 v0.3.0 开始，Docker 镜像**已内置 Chromium 和 Firefox 浏览器**：

- ✅ 构建时自动下载浏览器
- ✅ 运行时无需下载，开箱即用
- ✅ NAS 网络不稳定也能正常使用
- ✅ 支持自动检测和手动切换浏览器

**浏览器路径**: `/app/ms-playwright`

**切换浏览器**（通过环境变量）：
```yaml
environment:
  - PLAYWRIGHT_BROWSER=auto     # 自动检测（默认）
  # - PLAYWRIGHT_BROWSER=chromium  # 强制使用 Chromium
  # - PLAYWRIGHT_BROWSER=firefox   # 强制使用 Firefox
```

---

## 解决方案

### 方法一：使用国内镜像源（已配置）

当前 Dockerfile 已配置阿里云镜像源：

```dockerfile
RUN rm -f /etc/apt/sources.list.d/*.list && \
    echo "deb http://mirrors.aliyun.com/debian bookworm main" > /etc/apt/sources.list
```

**构建命令：**
```bash
cd zhihusync
docker-compose build --no-cache
```

**注意**：构建时需要下载浏览器（约 150MB），请确保网络稳定。如果构建失败，会重试 3 次。

### 方法二：使用预构建镜像

如果方法一仍然失败，使用已包含 Playwright 的预构建镜像：

```bash
# 使用替代配置
docker-compose -f docker-compose.alternative.yml up -d
```

### 方法三：手动配置 Docker 镜像加速

#### 1. Docker Desktop 设置

打开 Docker Desktop → Settings → Docker Engine，添加：

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
```

#### 2. 配置 daemon.json

**Linux:**
```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

**Windows:**
在 `%USERPROFILE%\.docker\daemon.json` 添加上述配置。

#### 3. 重启 Docker
```bash
# Linux
sudo systemctl restart docker

# Windows/Mac
# 重启 Docker Desktop
```

---

## 验证构建

### 1. 检查网络连通性

```bash
# 测试 Debian 源
docker run --rm python:3.11-slim bash -c "apt-get update && echo 'OK'"

# 测试 PyPI
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 分步构建调试

```bash
# 先测试基础镜像
docker run -it python:3.11-slim bash

# 在容器内执行：
apt-get update
apt-get install -y libglib2.0-0 libnss3
```

### 3. 完整构建

```bash
# 清理缓存
docker-compose down -v
docker system prune -f

# 重新构建
docker-compose build --no-cache --progress=plain 2>&1 | tee build.log
```

---

## 常见问题

### Q: 构建卡在 `apt-get update`

**解决：** 检查网络连接，尝试更换 DNS：
```bash
# 临时使用阿里云 DNS
docker build --dns 223.5.5.5 --dns 223.6.6.6 .
```

### Q: `playwright install` 下载慢

**解决：** 使用国内镜像或预下载：
```bash
# 手动下载浏览器
pip install playwright
playwright install chromium

# 然后构建时跳过安装
# 修改 Dockerfile: # RUN playwright install chromium
```

### Q: 镜像体积过大

**解决：** 使用多阶段构建（已优化）：
```dockerfile
# 构建阶段
FROM python:3.11 as builder
...

# 运行阶段
FROM python:3.11-slim
COPY --from=builder /app /app
```

---

## 备用构建脚本

创建 `build.sh`：

```bash
#!/bin/bash
set -e

echo "🚀 开始构建 zhihusync..."

# 检测网络状况
echo "📡 检测网络..."
if ! curl -s http://mirrors.aliyun.com > /dev/null; then
    echo "⚠️  阿里云镜像不可达，尝试其他源..."
fi

# 清理旧镜像
echo "🧹 清理旧镜像..."
docker-compose down -v 2>/dev/null || true
docker rmi zhihusync-zhihusync 2>/dev/null || true

# 构建
echo "🔨 构建镜像..."
if docker-compose build; then
    echo "✅ 构建成功！"
    echo ""
    echo "启动服务: docker-compose up -d"
    echo "访问: http://localhost:6067"
else
    echo "❌ 构建失败，尝试使用预构建镜像..."
    docker-compose -f docker-compose.alternative.yml up -d
fi
```

---

## 获取帮助

如果以上方法都失败：

1. **使用本地运行**：`python run_local.py`
2. **使用 WSL2**：在 WSL2 中运行 Docker
3. **GitHub Codespaces**：使用云端开发环境
