# 开发者手册

本文档面向开发者，介绍如何构建、测试和贡献代码。

---

## 目录

- [架构概述](#架构概述)
- [开发环境搭建](#开发环境搭建)
- [Docker 镜像构建](#docker-镜像构建)
- [代码结构](#代码结构)
- [测试指南](#测试指南)
- [贡献指南](#贡献指南)

---

## 架构概述

```
zhihusync/
├── Web 界面 (FastAPI + Jinja2)
├── 爬虫引擎 (Playwright)
├── 数据存储 (SQLite + 本地文件)
└── 定时任务 (APScheduler)
```

---

## 开发环境搭建

### 方式一：本地 Python 环境

```bash
# 1. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.\.venv\Scripts\Activate.ps1  # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装 Playwright 浏览器
playwright install chromium

# 4. 准备目录结构
mkdir -p data/html data/meta data/static/images

# 5. 复制测试 cookie（如有）
cp test/cookies.json data/meta/cookies.json

# 6. 启动服务
python -m src.app --mode both
```

### 方式二：Docker 开发

```bash
# 1. 构建基础镜像（只需执行一次）
./build-base.sh  # 或 .\build-base.ps1

# 2. 启动开发容器
docker-compose up -d --build

# 3. 查看日志
docker-compose logs -f
```

---

## Docker 镜像构建

### 镜像分层策略

为了减少构建时间和镜像大小，我们采用**多阶段构建**：

```
zhihusync-base:latest  (约 1.5GB)
    ├── Python 3.11
    ├── Playwright
    ├── Chromium
    └── Firefox

zhihusync:latest  (约 100MB)
    └── 应用代码
```

### 构建基础镜像

基础镜像包含浏览器环境，变动较少，可长期缓存：

```bash
# Linux/Mac
./build-base.sh

# Windows PowerShell
.\build-base.ps1

# 或手动构建
docker build -f Dockerfile.base -t zhihusync-base:latest .
```

构建时间：约 5-10 分钟（主要耗时在下载浏览器）

### 构建应用镜像

应用镜像基于基础镜像，只包含代码，构建快速：

```bash
# 标准构建
docker-compose build

# 无缓存构建（强制重新构建）
docker-compose build --no-cache

# 构建并启动
docker-compose up -d --build
```

构建时间：约 10-30 秒

### 镜像管理

```bash
# 查看镜像
docker images zhihusync*

# 删除旧镜像
docker rmi zhihusync:latest

# 清理所有未使用镜像
docker system prune -a

# 导出/导入基础镜像（分享给团队成员）
docker save zhihusync-base:latest | gzip > zhihusync-base.tar.gz
docker load < zhihusync-base.tar.gz
```

---

## 代码结构

```
src/
├── __init__.py          # 包初始化
├── __main__.py          # 入口模块
├── app.py               # 应用启动器（Web + 定时任务）
├── web.py               # FastAPI Web 服务
├── crawler.py           # Playwright 爬虫
├── db.py                # 数据库管理
├── models.py            # SQLAlchemy 数据模型
├── storage.py           # 文件存储管理
├── config_loader.py     # 配置加载
├── login.py             # 登录处理
├── main.py              # 定时任务服务
└── alerts.py            # 告警通知

templates/               # Jinja2 模板
├── index.html           # 仪表盘
├── config.html          # 配置页面
├── content.html         # 内容浏览
└── logs.html            # 日志查看

static/                  # 静态资源
├── css/
├── js/
└── images/

data/                    # 数据目录（Docker 挂载）
├── html/                # 备份的 HTML 文件
├── meta/                # 数据库和日志
│   ├── zhihusync.db
│   ├── cookies.json
│   └── zhihusync.log
└── static/images/       # 下载的图片
```

---

## 测试指南

### 单元测试

```bash
# 运行所有测试
python -m pytest test/

# 运行特定测试
python -m pytest test/test_crawler.py -v

# 生成覆盖率报告
python -m pytest --cov=src --cov-report=html
```

### API 测试

```bash
# 启动测试服务器
python -m src.app --mode web &

# 测试接口
curl http://localhost:6067/api/stats
curl http://localhost:6067/api/setup/status

# 停止测试服务器
kill %1
```

### 集成测试

```bash
# 构建并运行完整测试
docker-compose -f docker-compose.test.yml up --build
```

---

## 贡献指南

### 提交 Issue

- 描述问题时提供环境信息（OS、Python 版本、Docker 版本）
- 提供复现步骤
- 附上错误日志

### 提交 PR

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/xxx`)
3. 提交更改 (`git commit -am 'Add xxx'`)
4. 推送分支 (`git push origin feature/xxx`)
5. 创建 Pull Request

### 代码规范

- 遵循 PEP 8
- 使用类型注解
- 添加文档字符串
- 保持测试覆盖率 > 80%

---

## 常见问题

### 1. 基础镜像构建失败（下载浏览器超时）

```bash
# 设置镜像代理
export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright

# 重试构建
./build-base.sh
```

### 2. 应用镜像构建提示 "基础镜像不存在"

```bash
# 先构建基础镜像
./build-base.sh

# 再构建应用镜像
docker-compose build
```

### 3. 如何更新基础镜像中的浏览器版本

```bash
# 删除旧基础镜像
docker rmi zhihusync-base:latest

# 重新构建
./build-base.sh

# 重新构建应用
docker-compose up -d --build
```

---

## 相关文档

- [README.md](README.md) - 用户文档
- [DOCKER_BUILD.md](DOCKER_BUILD.md) - Docker 构建详情
- [TEST_REPORT.md](TEST_REPORT.md) - 测试报告

---

*最后更新: 2026-03-03*
