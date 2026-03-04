@echo off
chcp 65001 >nul
echo ===========================================
echo  知乎 Cookie 自动获取工具
echo ===========================================
echo.

cd /d "%~dp0\.."

REM 检查 playwright
uv run python -c "import playwright" 2>nul
if errorlevel 1 (
    echo 正在安装 playwright...
    uv add playwright
    uv run playwright install chromium
)

echo 正在启动自动获取工具...
echo.

uv run python scripts/get_cookie_auto.py

echo.
pause
