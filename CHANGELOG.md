# Changelog

所有版本变更记录请参见 [Releases](https://github.com/nevertiree/zhihusync/releases)。

## [1.1.0] - 2026-03-08

### 🚀 Docker 构建优化

#### 新增
- 多阶段构建 Dockerfile（镜像体积减少 30-40%）
- 本地构建 fallback 机制（Docker Hub 不可用时自动切换）
- Dockerfile.local 用于离线构建（移除 fonts-noto-cjk 解决超时问题）
- 安装脚本智能镜像获取策略

#### 改进
- 安装脚本 (install.sh/install.ps1):
  - 支持 Docker Hub 拉取失败时本地构建
  - 添加服务就绪检测（30次重试）
  - 优化错误提示和用户体验

- 卸载脚本 (uninstall.sh/uninstall.ps1):
  - 支持检测多种镜像标签
  - 添加数据备份功能（自动显示目录大小）
  - 支持清理 dangling 镜像

#### 修复
- 修复 Docker 构建超时问题（移除 56MB 的 fonts-noto-cjk 包）
- 统一使用 bookworm 源，避免 trixie 混合

---

## [1.0.0] - 2026-03-07

### 🎉 正式发布

- 项目首次正式发布 v1.0.0 版本
- 引入标准化版本管理机制
- 引入标准化分支管理流程 (Git Flow)

### ✨ 主要功能

- 知乎点赞内容自动备份
- Docker 一键安装部署
- Web 管理界面
- 多平台支持 (Linux/Windows/macOS)

### 🔧 技术栈

- Python 3.10+
- FastAPI + SQLAlchemy
- Playwright 浏览器自动化
- Docker + Docker Compose

---

*历史开发版本 (v0.3.0 - v0.6.0) 已归档，详见 Git 历史记录。*
