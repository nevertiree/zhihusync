# 安装指南

## 方式一：一键安装（推荐）

### Linux / macOS / WSL2

```bash
curl -fsSL https://raw.githubusercontent.com/nevertiree/zhihusync/master/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/nevertiree/zhihusync/master/install.ps1 | iex
```

安装脚本会：
- ✅ 自动检查 Docker 环境
- ✅ 交互式配置数据目录
- ✅ 可选配置知乎用户 ID
- ✅ 自动拉取镜像并启动服务

安装完成后访问：**http://localhost:6067**

---

## 方式二：Docker Hub 直接部署

```bash
# 创建目录
mkdir zhihusync && cd zhihusync

# 下载 docker-compose 配置
curl -O https://raw.githubusercontent.com/nevertiree/zhihusync/master/docker-compose.hub.yml

# 启动服务
docker-compose -f docker-compose.hub.yml up -d
```

---

## 方式三：本地构建部署

克隆项目并本地构建：

```bash
# 克隆项目
git clone https://github.com/nevertiree/zhihusync.git
cd zhihusync

# 标准版构建（推荐，仅 Chromium，约 1.8GB）
docker-compose up -d

# 完整版（Chromium + Firefox，约 2.3GB）
docker-compose --profile full up -d

# 精简版（首次启动下载浏览器，约 600MB）
docker-compose --profile minimal up -d
```

---

## 方式四：本地运行（开发）

```bash
# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium

# 启动服务
python -m src.app

# 访问 http://localhost:6067
```

---

## 版本信息

| 类型 | 版本/地址 |
|------|----------|
| **Git 版本** | v1.1.0 |
| **Docker Image** | `nevertiree26/zhihusync:v1.1.0` |
| **Docker Hub** | https://hub.docker.com/r/nevertiree26/zhihusync |
| **GitHub Release** | https://github.com/nevertiree/zhihusync/releases |
