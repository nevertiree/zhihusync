# 测试文档

本文档介绍 zhihusync 的测试体系和使用方法。

## 测试结构

```
tests/
├── unit/                      # 单元测试（无外部依赖）
│   ├── test_crawler.py
│   └── test_storage.py
├── integration/               # 集成测试（需要数据库等）
│   ├── test_api.py
│   ├── test_full_sync.py
│   └── test_extraction_errors_api.py  # 提取错误 API 测试
├── e2e/                       # 端到端测试（需要浏览器）
│   ├── test_web_ui.py
│   └── test_extraction_errors.py      # 提取错误 UI 测试
├── fixtures/                  # 测试数据
├── conftest.py               # Pytest 配置
└── run_tests.py              # 测试运行器
```

## 运行测试

### 方法 1: 使用 Makefile（推荐）

```bash
# 运行所有测试
make test

# 运行单元测试
make test-unit

# 运行集成测试
make test-integration

# 运行 E2E 测试（带浏览器界面）
make test-e2e

# 运行 E2E 测试（无头模式，适合 CI）
make test-e2e-ci

# 专门测试提取错误功能
make test-errors

# 生成测试报告
make test-report
```

### 方法 2: 使用测试运行器

```bash
# 运行所有测试
python tests/run_tests.py

# 运行特定类型测试
python tests/run_tests.py unit
python tests/run_tests.py api
python tests/run_tests.py e2e
python tests/run_tests.py errors  # 提取错误功能测试

# 完整测试（包含同步测试）
python tests/run_tests.py full
```

### 方法 3: 直接使用 pytest

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/unit/ -v -m unit

# 运行集成测试
pytest tests/integration/ -v -m integration

# 运行 E2E 测试
pytest tests/e2e/ -v -m e2e

# 运行特定测试文件
pytest tests/e2e/test_extraction_errors.py -v -s
```

## 提取错误功能测试

### 测试内容

提取错误功能的测试包括：

1. **API 测试** (`test_extraction_errors_api.py`)
   - 获取错误列表
   - 标记单个错误为已解决
   - 批量标记为已解决
   - 删除错误记录
   - 统计信息验证

2. **UI 测试** (`test_extraction_errors.py`)
   - 页面加载
   - 按钮显示/隐藏
   - 按钮点击交互
   - 确认对话框
   - JavaScript 控制台错误检查

### 手动测试脚本

```bash
# 运行手动测试脚本
bash scripts/test_extraction_errors.sh
```

这个脚本会：
1. 检查服务状态
2. 测试 API 接口
3. 测试标记全部为已解决
4. 打开调试页面

### 调试页面

访问 `http://localhost:6067/static/test_errors.html` 可以打开调试页面，用于：
- 检查 JavaScript 函数是否存在
- 模拟错误数据
- 测试按钮功能
- 查看浏览器控制台日志

## E2E 测试环境准备

### 安装依赖

```bash
pip install selenium webdriver-manager
```

### 安装浏览器驱动

ChromeDriver 会自动安装，或者手动安装：

```bash
# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# macOS
brew install chromedriver

# Windows
# 下载 ChromeDriver 并添加到 PATH
```

### 启动测试服务器

```bash
# 使用 Docker
make web

# 或使用 Python
cd src && python -m app
```

## CI/CD 集成

项目包含 GitHub Actions 配置 (`.github/workflows/tests.yml`)，会自动运行：

- 单元测试（Python 3.10, 3.11, 3.12）
- 集成测试
- E2E 测试
- 代码质量检查（Ruff, Black, MyPy）

## 测试标记

使用 pytest 标记来分类测试：

- `@pytest.mark.unit`: 单元测试
- `@pytest.mark.integration`: 集成测试
- `@pytest.mark.e2e`: 端到端测试
- `@pytest.mark.api`: API 测试
- `@pytest.mark.slow`: 慢速测试

运行特定标记的测试：

```bash
pytest -v -m e2e
pytest -v -m "not slow"
```

## 常见问题

### E2E 测试失败

1. **服务未运行**: 确保服务在 `http://localhost:6067` 运行
2. **浏览器驱动问题**: 检查 ChromeDriver 是否安装正确
3. **元素未找到**: 可能是页面加载慢，增加等待时间

### 调试 E2E 测试

```bash
# 使用有头模式（显示浏览器界面）
pytest tests/e2e/test_extraction_errors.py -v --headed -s

# 保留浏览器窗口（调试用）
pytest tests/e2e/test_extraction_errors.py -v --headed --pdb
```

### API 测试失败

1. 检查服务是否运行
2. 检查数据库连接
3. 查看测试输出中的详细错误信息

## 添加新测试

### 添加单元测试

```python
# tests/unit/test_new_feature.py
import pytest

@pytest.mark.unit
def test_something():
    assert True
```

### 添加集成测试

```python
# tests/integration/test_new_api.py
import pytest

@pytest.mark.integration
@pytest.mark.api
def test_api_endpoint(client):
    response = client.get("/api/endpoint")
    assert response.status_code == 200
```

### 添加 E2E 测试

```python
# tests/e2e/test_new_ui.py
import pytest

selenium = pytest.importorskip("selenium")

@pytest.mark.e2e
class TestNewFeature:
    def test_ui(self, driver, base_url):
        driver.get(f"{base_url}/page")
        assert "Expected" in driver.title
```
