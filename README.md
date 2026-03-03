# zhihusync - 知乎点赞内容备份工具

自动备份知乎用户点赞的回答和评论，防止内容被删除后无法找回。提供友好的 Web 管理界面，轻松配置和查看备份内容。

![Dashboard](https://img.shields.io/badge/Dashboard-Available-brightgreen)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![Python](https://img.shields.io/badge/Python-3.11-yellow)

## ✨ 功能特性

- ✅ **Web 管理界面** - 可视化操作，无需命令行
- ✅ **Cookie 配置** - 通过网页粘贴 Cookie，一键保存
- ✅ **实时同步状态** - 查看同步进度和日志
- ✅ **内容浏览器** - 查看、搜索、管理已备份的回答
- ✅ **自动备份** - 定期扫描用户点赞内容
- ✅ **完整保存** - 保留回答内容和评论
- ✅ **样式还原** - 尽量保留知乎原生 CSS 样式
- ✅ **元数据记录** - 记录作者、点赞数、时间等信息
- ✅ **图片下载** - 自动下载图片到本地
- ✅ **增量更新** - 只同步新内容，避免重复

## 🚀 快速开始

### 方式一：使用 Docker（推荐，NAS 适用）

**特点：** 浏览器已打包在镜像中，开箱即用，无需运行时下载

```bash
# 1. 克隆项目并进入目录
cd zhihusync

# 2. 【首次】构建基础镜像（包含 Chrome + Playwright，只需执行一次）
./build-base.sh        # Linux/Mac
# 或
.\build-base.ps1       # Windows PowerShell

# 3. 构建并启动应用
docker-compose up -d --build

# 4. 访问 Web 界面完成配置
open http://localhost:6067
```

**为什么需要基础镜像？**
浏览器安装包较大（~200MB），且下载容易受网络影响。基础镜像将浏览器环境预先打包，应用构建时直接复用，大幅提升构建速度。

### 方式二：本地开发测试

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装 Playwright 浏览器
playwright install chromium

# 3. 启动服务
python -m src.app --mode both

# 4. 访问 http://localhost:6067 完成配置
```

---

## 📖 详细配置指南

### 首次使用配置步骤

#### 第一步：配置 Cookie（必需）

知乎需要登录后才能访问点赞内容，请按以下步骤获取 Cookie：

**方法 1：使用 EditThisCookie 插件（推荐）**

1. 安装 [EditThisCookie](https://www.editthiscookie.com/) 浏览器扩展
2. 在浏览器中登录 [知乎](https://www.zhihu.com)
3. 点击浏览器工具栏的 EditThisCookie 图标
4. 点击 "Export" → "Export as JSON"
5. 复制导出的 JSON 内容

**方法 2：手动从开发者工具复制**

1. 在浏览器中登录 [知乎](https://www.zhihu.com)
2. 按 `F12` 打开开发者工具
3. 切换到 **Application/应用** 标签
4. 在左侧选择 **Cookies** → `https://www.zhihu.com`
5. 右键点击表格 → "Copy all / 复制全部"
6. 将内容粘贴到 Web 界面的 Cookie 输入框

**方法 3：使用控制台命令**

```javascript
// 在 Console 标签页执行以下代码
JSON.stringify(document.cookie.split(';').map(c => {
  const [n, ...v] = c.trim().split('=');
  return {name: n, value: v.join('='), domain: '.zhihu.com'};
}))
```

> ⚠️ **注意**：Cookie 会定期过期（通常 1-3 个月），过期后需要重新配置。

#### 第二步：设置用户 ID（必需）

用户 ID 用于识别要备份哪个账号的点赞内容：

1. 登录知乎后，点击右上角头像 → **我的主页**
2. 查看地址栏 URL，格式为 `https://www.zhihu.com/people/xxx`
3. 其中的 `xxx` 就是你的用户 ID
4. 将用户 ID 填入 Web 界面的配置页面

**示例：**
```
URL: https://www.zhihu.com/people/zhang-san-123
用户 ID: zhang-san-123
```

#### 第三步：高级设置（可选）

| 设置项 | 说明 | 建议值 |
|--------|------|--------|
| 扫描间隔 | 自动同步的时间间隔（分钟） | 30-120 |
| 最大条目数 | 每次同步最多获取多少条 | 50-100 |
| 保存评论 | 是否同时备份评论内容 | 是 |
| 无头模式 | 是否在后台运行浏览器 | 是 |

#### 第四步：开始同步

完成上述配置后：

1. 返回仪表盘页面
2. 点击"开始同步"按钮
3. 等待同步完成（首次同步可能需要较长时间）

---

## 📁 界面说明

### 仪表盘

显示系统概览，包括：
- 统计卡片（已备份回答数、评论数等）
- 同步进度（实时显示）
- 同步历史
- 快速操作入口

### 备份内容

浏览和管理已备份的回答：
- 列表查看所有备份内容
- 搜索功能（按标题、作者）
- 分页浏览
- 删除不需要的备份

### 配置

完整的配置管理页面：
- Cookie 配置（支持 🧪 **测试登录** 按钮，验证 Cookie 有效性）
- 用户 ID 设置
- 高级选项
- 配置指南和 FAQ

> 💡 **Cookie 测试功能**：在配置页面点击「测试登录」按钮，系统会启动浏览器验证 Cookie 是否有效，无需等到同步时才发现登录失效。

### 日志

实时查看系统日志：
- 实时日志流
- 同步历史详情
- 错误诊断

---

## 📂 目录结构

```
zhihusync/
├── config/
│   └── config.yaml          # 主配置文件
├── data/                    # 数据目录 (持久化)
│   ├── html/                # 保存的 HTML 文件
│   │   └── {question_id}_{title}/
│   │       └── {answer_id}.html
│   ├── meta/                # 元数据和日志
│   │   ├── zhihusync.db     # SQLite 数据库
│   │   ├── zhihusync.log    # 日志文件
│   │   └── cookies.json     # 登录凭证
│   └── static/
│       └── images/          # 下载的图片资源
├── src/                     # 源代码
├── templates/               # Web 界面模板
├── static/                  # Web 静态资源
├── docker-compose.yml       # Docker Compose 配置
├── Dockerfile               # Docker 镜像定义
└── README.md               # 本文件
```

---

## ⚙️ 配置说明

### 通过 Web 界面配置

访问 http://localhost:6067/config 进行可视化配置。

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ZHIHU_USER_ID` | 知乎用户ID | - |
| `SCAN_INTERVAL` | 扫描间隔(分钟) | 60 |
| `HEADLESS` | 无头模式 | true |
| `LOG_LEVEL` | 日志级别 | INFO |
| `PLAYWRIGHT_BROWSER` | 浏览器类型: auto/chromium/firefox | auto |

> **NAS 用户注意**：Docker 镜像已打包 Chromium 和 Firefox 浏览器，开箱即用，无需运行时下载。如遇兼容性问题，可通过 `PLAYWRIGHT_BROWSER=firefox` 切换浏览器。

### 配置文件 (config.yaml)

```yaml
zhihu:
  user_id: ""                    # 知乎用户ID
  scan_interval: 60              # 扫描间隔(分钟)
  max_items_per_scan: 50         # 每次扫描最大条目
  save_comments: true            # 是否保存评论

storage:
  html_path: "/app/data/html"
  db_path: "/app/data/meta/zhihusync.db"
  download_images: true
  images_path: "/app/data/static/images"

browser:
  headless: true
  request_delay: 2.0             # 请求间隔(秒)
```

---

## 🛠️ 命令行工具

```bash
# 查看帮助
make help

# 启动服务
make up

# 查看日志
make logs

# 查看统计
make stats

# 手动触发同步
curl -X POST http://localhost:6067/api/sync/start

# 备份数据
make backup

# 停止服务
make down

# 清理所有数据（谨慎使用）
make clean
```

---

## 🔌 API 接口

Web 服务提供以下 REST API：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/stats` | GET | 获取统计信息 |
| `/api/setup/status` | GET | 获取配置状态 |
| `/api/config` | GET/POST | 获取/更新配置 |
| `/api/cookies` | POST | 更新 Cookie |
| `/api/cookies/check` | GET | 检查 Cookie 状态 |
| `/api/sync/start` | POST | 开始同步 |
| `/api/sync/stop` | POST | 停止同步 |
| `/api/sync/status` | GET | 同步状态 |
| `/api/sync/history` | GET | 同步历史 |
| `/api/answers` | GET | 获取回答列表 |
| `/api/answers/{id}` | DELETE | 删除回答 |
| `/api/logs` | GET | 获取日志 |

---

## ❓ 常见问题

### Q: Cookie 有效期多久？

知乎 Cookie 通常有效期为 1-3 个月，过期后需要重新配置。如果同步失败且日志显示登录失效，请重新获取 Cookie。

### Q: 如何找到自己的用户 ID？

登录知乎后，点击右上角头像 → 我的主页，地址栏中的 URL 格式为 `https://www.zhihu.com/people/xxx`，其中的 `xxx` 就是你的用户 ID。

### Q: 同步失败怎么办？

1. 检查 Cookie 是否有效
2. 检查用户 ID 是否正确
3. 查看日志页面的错误信息
4. 尝试增加请求间隔时间

### Q: 备份的数据在哪里？

备份的 HTML 文件保存在 `data/html` 目录下，数据库文件在 `data/meta/zhihusync.db`。

### Q: 可以备份多个账号吗？

目前一个实例只支持一个账号。如需备份多个账号，需要启动多个实例，分别配置不同的用户 ID 和数据目录。

### Q: 如何查看备份的内容？

1. 通过 Web 界面的"备份内容"页面浏览
2. 直接在文件系统中打开 `data/html` 目录下的 HTML 文件
3. 启动 Nginx 服务（`make nginx`）通过浏览器访问

---

## ⚠️ 注意事项

1. **Cookie 过期** - 知乎 Cookie 会过期，失效后需要重新配置
2. **请求频率** - 已设置合理延迟，避免触发风控
3. **数据安全** - 备份数据保存在本地，不会上传
4. **首次同步** - 首次同步可能需要较长时间，请耐心等待

---

## 🐛 故障排除

### 无法登录
- 检查 Cookie 是否正确复制
- 确认 Cookie 未过期（在浏览器中重新登录后复制）
- 查看日志获取详细信息

### 同步失败
- 检查网络连接
- 确认用户ID正确
- 查看日志中的错误信息

### 端口占用
如果 6067 端口被占用，修改 `docker-compose.yml`：
```yaml
ports:
  - "8091:6067"  # 使用 8091 端口
```

---

## 🏗️ 技术栈

- **后端**: FastAPI + SQLAlchemy + APScheduler
- **前端**: 原生 HTML/JS + CSS3
- **爬虫**: Playwright + BeautifulSoup4
- **容器**: Docker + Docker Compose

---

## 📄 许可证

MIT License

---

## 📝 更新日志

### v0.2.0
- 新增 Web 管理界面
- 支持可视化配置 Cookie
- 实时同步进度显示
- 内容浏览器支持搜索和分页
- 新增配置引导 Banner

### v0.1.0
- 初始版本
- 支持点赞内容备份
- 支持评论备份
- Docker 化部署
