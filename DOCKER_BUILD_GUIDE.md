# Docker 构建优化指南

## 问题背景

之前的构建频繁超时，主要原因是：
1. `fonts-noto-cjk` 包体积巨大（56MB）且下载不稳定
2. apt 源混乱（bookworm 和 trixie 混合）
3. 所有依赖在一个层，代码变更触发全量重建

## 解决方案对比

| 方案 | 构建时间 | 最终大小 | 适用场景 | 依赖网络 |
|------|----------|----------|----------|----------|
| Dockerfile (基础镜像) | 10-30秒 | ~500MB | 开发/生产 | 需 Docker Hub |
| Dockerfile.local | 3-8分钟 | ~500MB | 离线环境 | 仅国内镜像源 |
| Dockerfile.multistage | 5-10分钟 | ~350MB | 生产发布 | 需 Docker Hub |
| Dockerfile.minimal | 2-5分钟 | ~200MB | 网络好，空间敏感 | 首次启动下载浏览器 |

## 快速开始

### 方案A: 使用预构建镜像（推荐）

```bash
# 直接拉取运行，无需构建
docker pull nevertiree/zhihusync:latest
docker-compose up -d
```

### 方案B: 本地完整构建（离线可用）

```bash
# 使用本地构建版本
docker build -t zhihusync:latest -f Dockerfile.local .
docker-compose up -d
```

### 方案C: 多阶段构建（生产优化）

```bash
# 构建更小的生产镜像
docker build -t zhihusync:latest -f Dockerfile.multistage .
```

## 发布流程（维护者使用）

### 1. 构建并推送基础镜像（每月更新）

```bash
# 构建基础镜像（包含所有重型依赖）
docker build -t nevertiree/zhihusync-base:latest -f Dockerfile.base .

# 测试基础镜像
docker run --rm nevertiree/zhihusync-base:latest playwright --version

# 推送至 Docker Hub
docker push nevertiree/zhihusync-base:latest
```

### 2. 构建并推送应用镜像（每次发布）

```bash
# 版本号
VERSION=$(cat VERSION.md | grep -oP '\d+\.\d+\.\d+')

# 构建多架构镜像
docker buildx create --use
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t nevertiree/zhihusync:latest \
  -t nevertiree/zhihusync:${VERSION} \
  --push .
```

## 缓存优化策略

### 本地开发缓存

```bash
# 使用 BuildKit 缓存
docker build \
  --cache-from=type=local,src=/tmp/.buildx-cache \
  --cache-to=type=local,dest=/tmp/.buildx-cache \
  -t zhihusync:latest .
```

### CI/CD 缓存（GitHub Actions）

```yaml
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: nevertiree/zhihusync:latest
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

## 故障排查

### 构建超时

```bash
# 增加超时时间
docker build --progress=plain -t zhihusync:latest . 2>&1 | tee build.log

# 单独测试 apt 安装
docker run --rm python:3.11-slim-bookworm apt-get update
```

### 字体问题

如果移除 `fonts-noto-cjk` 后出现中文乱码：

```dockerfile
# 方案1: 使用更小的 Noto 字体（仅 CJK）
RUN apt-get install -y fonts-noto-cjk-extra

# 方案2: 下载特定字体文件
RUN wget -O /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc \
    https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/NotoSansCJK-Regular.ttc
```

## 镜像大小分析

```bash
# 查看每层大小
docker history zhihusync:latest

# 详细分析
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  wagoodman/dive:latest zhihusync:latest
```

## 文件说明

| 文件 | 用途 | 构建时间 | 大小 |
|------|------|----------|------|
| `Dockerfile` | 主文件，使用预构建基础镜像 | 10-30s | ~500MB |
| `Dockerfile.local` | 离线完整构建 | 3-8min | ~500MB |
| `Dockerfile.base` | 基础镜像（预构建） | 5-10min | ~480MB |
| `Dockerfile.multistage` | 多阶段生产构建 | 5-10min | ~350MB |
| `Dockerfile.minimal` | 最小镜像（运行时下载浏览器） | 2-5min | ~200MB |
| `Dockerfile.full` | 完整版（含 Firefox） | 8-15min | ~800MB |
