@echo off
chcp 65001 >nul
echo ===========================================
echo  知乎 Cookie 获取工具 (调试版)
echo ===========================================
echo.

REM 检查 uv
call uv --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 需要安装 uv 包管理器
    echo 访问: https://github.com/astral-sh/uv
    pause
    exit /b 1
)

echo 正在启动浏览器调试工具...
echo.

cd /d "%~dp0\.."
uv run python scripts/debug_cookie.py

echo.
pause
