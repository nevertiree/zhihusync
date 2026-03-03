<div align="center">

# 🔄 zhihusync

**自动备份知乎点赞内容，防止珍贵回答丢失**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[English](README_EN.md) | 简体中文

</div>

---

## 📖 简介

zhihusync 是一个自动备份知乎用户点赞内容的工具。它通过定时扫描你的知乎点赞记录，将回答和文章保存为本地 HTML 文件，即使原内容被删除或作者注销账号，你仍然可以查看备份的内容。

### 为什么需要这个工具？

- 📝 **内容消失** - 知乎回答经常被作者删除或账号注销
- 🔒 **账号封禁** - 优质答主可能被封禁导致内容无法访问
- 📚 **知识沉淀** - 将散落的知识整理成可本地浏览的档案
- 🔍 **全文搜索** - 本地备份支持快速搜索关键信息

---

## ✨ 功能特性

| 功能 | 描述 | 状态 |
|------|------|------|
| 🌐 **Web 管理界面** | 可视化操作，无需命令行 | ✅ |
| 🔐 **Cookie 配置** | 通过网页粘贴 Cookie，一键保存 | ✅ |
| 📊 **实时状态** | 查看同步进度和日志 | ✅ |
| 📁 **内容浏览** | 查看、搜索、管理已备份内容 | ✅ |
| ⏰ **自动同步** | 定时扫描新点赞内容 | ✅ |
| 💾 **完整保存** | 保留回答内容和评论 | ✅ |
| 🎨 **样式还原** | 保留知乎原生 CSS 样式 | ✅ |
| 🏷️ **元数据记录** | 记录作者、点赞数、时间等 | ✅ |
| 🖼️ **图片下载** | 自动下载图片到本地 | ✅ |
| 🔄 **增量更新** | 只同步新内容，避免重复 | ✅ |

---

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

使用预构建的 Playwright 镜像，无需手动安装浏览器：

```bash
# 克隆项目
git clone https://github.com/yourusername/zhihusync.git
cd zhihusync

# 启动服务
docker-compose -f docker-compose.quick.yml up -d

# 访问 Web 界面
open http://localhost:6067
```

### 方式二：本地运行

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

## 📸 界面预览

### 仪表盘
显示统计信息、同步状态和快速操作

### 内容浏览器
查看、搜索和管理已备份的回答

### 配置页面
可视化配置 Cookie、用户 ID 和同步选项

---

## ⚙️ 配置指南

### 1. 获取知乎 Cookie

**使用 EditThisCookie 插件（推荐）：**

1. 安装 [EditThisCookie](https://www.editthiscookie.com/) 浏览器扩展
2. 登录 [知乎](https://www.zhihu.com)
3. 点击扩展图标 → Export → Export as JSON
4. 将 JSON 粘贴到 Web 界面的 Cookie 输入框

**或使用浏览器开发者工具：**

```javascript
// 在 Console 中执行
JSON.stringify(document.cookie.split(';').map(c => {
  const [n, ...v] = c.trim().split('=');
  return {name: n, value: v.join('='), domain: '.zhihu.com'};
}))
```

### 2. 获取用户 ID

1. 登录知乎，点击头像 → **我的主页**
2. 地址栏 URL: `https://www.zhihu.com/people/xxx`
3. `xxx` 就是你的用户 ID

### 3. 高级配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 扫描间隔 | 自动同步时间间隔（分钟） | 30 |
| 最大条目数 | 每次同步最多获取条数 | 50 |
| 保存评论 | 是否备份评论内容 | true |
| 无头模式 | 是否在后台运行浏览器 | true |

---

## 📂 项目结构

```
zhihusync/
├── 📁 config/                 # 配置文件
│   └── config.yaml
├── 📁 data/                   # 数据目录（持久化）
│   ├── 📁 html/              # 备份的 HTML 文件
│   ├── 📁 meta/              # 元数据和日志
│   │   ├── zhihusync.db      # SQLite 数据库
│   │   ├── zhihusync.log     # 日志文件
│   │   └── cookies.json      # 登录凭证
│   └── 📁 static/            # 图片等静态资源
├── 📁 src/                    # 源代码
│   ├── crawler.py            # 爬虫核心
│   ├── web.py                # Web 服务
│   ├── storage.py            # 存储管理
│   ├── db.py                 # 数据库操作
│   └── ...
├── 📁 templates/              # Web 模板
├── 📁 static/                 # Web 静态资源
├── docker-compose.yml         # Docker 配置
├── Dockerfile                 # 镜像定义
└── README.md                  # 本文件
```

---

## 🔌 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/stats` | GET | 获取统计信息 |
| `/api/setup/status` | GET | 获取配置状态 |
| `/api/config` | GET/POST | 获取/更新配置 |
| `/api/cookies` | POST | 更新 Cookie |
| `/api/cookies/check` | GET | 检查 Cookie 状态 |
| `/api/cookies/test` | POST | 测试 Cookie 登录 |
| `/api/sync/start` | POST | 开始同步 |
| `/api/sync/stop` | POST | 停止同步 |
| `/api/sync/status` | GET | 同步状态 |
| `/api/sync/history` | GET | 同步历史 |
| `/api/answers` | GET | 获取回答列表 |
| `/api/answers/{id}` | DELETE | 删除回答 |
| `/api/logs` | GET | 获取日志 |

---

## ❓ 常见问题

### Cookie 有效期多久？

知乎 Cookie 通常有效期为 1-3 个月，过期后需要重新配置。

### 可以备份多个账号吗？

目前一个实例只支持一个账号。如需备份多个账号，需要启动多个实例。

### 备份的数据在哪里？

- HTML 文件: `data/html/`
- 数据库: `data/meta/zhihusync.db`
- 图片: `data/static/images/`

### 如何查看备份内容？

1. 通过 Web 界面的"内容浏览"页面
2. 直接打开 `data/html` 目录下的 HTML 文件

---

## 🛠️ 技术栈

- **后端**: [FastAPI](https://fastapi.tiangolo.com/) + [SQLAlchemy](https://www.sqlalchemy.org/)
- **前端**: 原生 HTML/JS + [Tailwind CSS](https://tailwindcss.com/)
- **爬虫**: [Playwright](https://playwright.dev/) + [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)
- **调度**: [APScheduler](https://apscheduler.readthedocs.io/)
- **容器**: [Docker](https://www.docker.com/) + [Docker Compose](https://docs.docker.com/compose/)

---

## ☕ 支持项目

如果这个项目对你有帮助，欢迎请开发者喝杯咖啡！

<p align="center">
  <a href="https://www.buymeacoffee.com/yourusername" target="_blank">
    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50">
  </a>
</p>

### 捐赠方式

| 方式 | 链接/二维码 |
|------|------------|
| 💚 微信支付 | 扫码支付 |
| 💙 支付宝 | 扫码支付 |
| 🌐 Buy Me a Coffee | [buymeacoffee.com/yourusername](https://www.buymeacoffee.com/yourusername) |
| 💖 GitHub Sponsors | [github.com/sponsors/yourusername](https://github.com/sponsors/yourusername) |

> 所有捐赠将用于项目维护（服务器、域名等）以及给开发者续杯咖啡 ☕

### 特别感谢

感谢所有支持这个项目的朋友们！🙏

---

## 📄 许可证

[MIT License](LICENSE) © 2026 zhihusync

---

## 🙏 致谢

- [Playwright](https://playwright.dev/) - 强大的浏览器自动化工具
- [FastAPI](https://fastapi.tiangolo.com/) - 现代、快速的 Web 框架
- [Tailwind CSS](https://tailwindcss.com/) - 实用的 CSS 框架
