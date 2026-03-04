# zhihusync 自动化测试模块

## 目录结构

```
tests/
├── README.md                 # 本文件
├── conftest.py              # pytest 全局配置和 fixtures
├── pytest.ini              # pytest 配置文件
├── run_tests.py            # 测试运行脚本
├── unit/                   # 单元测试（快速，无外部依赖）
│   ├── __init__.py
│   ├── test_crawler.py     # 爬虫单元测试
│   └── test_storage.py     # 存储单元测试
├── integration/            # 集成测试（需要运行中的服务）
│   ├── __init__.py
│   ├── test_api.py         # API 集成测试
│   └── test_full_sync.py   # 全量同步测试
├── e2e/                    # 端到端测试（需要浏览器）
│   ├── __init__.py
│   └── test_web_ui.py      # Web UI E2E 测试
├── fixtures/               # 测试数据和资源
│   ├── cookies.json        # 测试用 Cookie
│   └── test_users.json     # 测试用户数据
└── reports/                # 测试报告目录
```

## 快速开始

### 运行所有测试

```bash
cd tests
python run_tests.py
```

### 运行特定类型测试

```bash
# 仅单元测试
python run_tests.py unit

# 仅 API 集成测试
python run_tests.py api

# 仅 E2E 测试
python run_tests.py e2e

# 完整测试（包括慢速同步测试）
python run_tests.py full
```

### 使用 pytest 直接运行

```bash
# 所有测试
pytest

# 单元测试
pytest tests/unit -v

# 集成测试（需要服务运行）
pytest tests/integration -v

# E2E 测试（需要浏览器）
pytest tests/e2e -v
```

## 测试标记

| 标记 | 说明 | 示例 |
|------|------|------|
| `unit` | 单元测试 | `pytest -m unit` |
| `integration` | 集成测试 | `pytest -m integration` |
| `e2e` | 端到端测试 | `pytest -m e2e` |
| `slow` | 慢速测试 | `pytest -m slow` |
| `api` | API 测试 | `pytest -m api` |

## 环境要求

### 单元测试
- Python 3.8+
- 项目依赖已安装

### 集成测试
- Docker 服务运行中
- `docker-compose up -d`

### E2E 测试
- Docker 服务运行中
- Chrome/Edge 浏览器
- Selenium WebDriver

## 测试数据

测试数据位于 `fixtures/` 目录：
- `cookies.json` - 知乎 Cookie（用于集成测试）
- `test_users.json` - 测试用户配置

## 报告

测试报告和历史记录保存在 `reports/` 目录。

查看历史报告：
- [测试报告 V2](../TEST_REPORT_V2.md)
- [完整同步测试报告](../FULL_SYNC_TEST_REPORT.md)
