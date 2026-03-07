#!/usr/bin/env pwsh
# zhihusync 一键安装脚本 (Windows/Linux 通用)
# 使用方法: powershell -Command "& { Invoke-Expression (Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/nevertiree/zhihusync/master/install.ps1').Content }"
# 或本地运行: ./install.ps1

param(
    [string]$InstallDir = "",
    [switch]$Silent = $false
)

$ErrorActionPreference = "Stop"

# 颜色输出
function Write-Color($Text, $Color = "White") {
    Write-Host $Text -ForegroundColor $Color
}

# 检查 Docker
function Test-Docker {
    try {
        $dockerVersion = docker --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $true, $dockerVersion
        }
    } catch {
        return $false, "Docker 未安装"
    }
    return $false, "Docker 未安装"
}

# 检查 Docker Compose
function Test-DockerCompose {
    try {
        # 尝试新命令格式
        $composeVersion = docker compose version 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $true, $composeVersion
        }
        # 尝试旧命令格式
        $composeVersion = docker-compose --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $true, $composeVersion
        }
    } catch {
        return $false, "Docker Compose 未安装"
    }
    return $false, "Docker Compose 未安装"
}

# 显示欢迎信息
function Show-Welcome {
    Clear-Host
    Write-Color @"
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🔄 zhihusync - 知乎点赞内容自动备份工具                    ║
║                                                           ║
║   一键安装，自动备份你的知乎点赞内容                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"@ "Cyan"
    Write-Host ""
}

# 显示系统信息
function Show-SystemInfo {
    Write-Color "📋 系统信息:" "Yellow"
    Write-Host "   操作系统: $($env:OS)"
    Write-Host "   PowerShell 版本: $($PSVersionTable.PSVersion)"
    Write-Host ""
}

# 检查环境
function Test-Environment {
    Write-Color "🔍 检查环境依赖..." "Yellow"

    $dockerOk, $dockerInfo = Test-Docker
    $composeOk, $composeInfo = Test-DockerCompose

    if (-not $dockerOk) {
        Write-Color "❌ Docker 未安装" "Red"
        Write-Host ""
        Write-Color "请按以下步骤安装 Docker:" "Yellow"
        if ($IsLinux -or $env:OS -like "*Linux*") {
            Write-Host "   Linux: curl -fsSL https://get.docker.com | sh"
        } else {
            Write-Host "   Windows: https://docs.docker.com/desktop/install/windows-install/"
        }
        exit 1
    }
    Write-Color "✅ $dockerInfo" "Green"

    if (-not $composeOk) {
        Write-Color "⚠️  Docker Compose 未安装" "Yellow"
    } else {
        Write-Color "✅ $composeInfo" "Green"
    }
    Write-Host ""
}

# 配置安装
function Configure-Install {
    param([string]$DefaultDir)

    Write-Color "⚙️  配置安装选项" "Yellow"

    # 安装目录
    if ($DefaultDir) {
        $script:InstallPath = $DefaultDir
    } else {
        $defaultPath = if ($IsLinux -or $env:OS -like "*Linux*") {
            "$env:HOME/zhihusync"
        } else {
            "$env:USERPROFILE/zhihusync"
        }

        if (-not $Silent) {
            Write-Host "默认安装目录: $defaultPath"
            $customPath = Read-Host "请输入安装目录 (直接回车使用默认)"
            if ($customPath) {
                $script:InstallPath = $customPath
            } else {
                $script:InstallPath = $defaultPath
            }
        } else {
            $script:InstallPath = $defaultPath
        }
    }

    Write-Color "📁 安装目录: $script:InstallPath" "Green"
    Write-Host ""
}

# 创建目录结构
function Initialize-Directory {
    Write-Color "📂 创建目录结构..." "Yellow"

    $dirs = @(
        "$script:InstallPath",
        "$script:InstallPath/data/html",
        "$script:InstallPath/data/meta",
        "$script:InstallPath/data/images",
        "$script:InstallPath/data/static",
        "$script:InstallPath/config"
    )

    foreach ($dir in $dirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }

    Write-Color "✅ 目录创建完成" "Green"
    Write-Host ""
}

# 下载配置文件
function Download-Config {
    Write-Color "⬇️  下载配置文件..." "Yellow"

    $baseUrl = "https://raw.githubusercontent.com/nevertiree/zhihusync/master"
    $files = @{
        "docker-compose.hub.yml" = "$script:InstallPath/docker-compose.yml"
        ".env.example" = "$script:InstallPath/.env.example"
    }

    foreach ($file in $files.GetEnumerator()) {
        $url = "$baseUrl/$($file.Key)"
        $output = $file.Value
        try {
            Invoke-WebRequest -Uri $url -OutFile $output -UseBasicParsing
            Write-Host "   ✅ $($file.Key)"
        } catch {
            Write-Color "   ❌ 下载失败: $($file.Key)" "Red"
            exit 1
        }
    }

    # 创建 .env 文件
    $envContent = @"
# zhihusync 配置文件
# 知乎用户 ID (必填，在浏览器中登录知乎后，访问个人主页 URL 中的用户 ID)
ZHIHU_USER_ID=

# 扫描间隔（分钟）
SCAN_INTERVAL=60

# 是否无头模式运行浏览器
HEADLESS=true

# 日志级别 (DEBUG/INFO/WARNING/ERROR)
LOG_LEVEL=INFO

# 浏览器类型 (chromium/firefox/auto)
PLAYWRIGHT_BROWSER=chromium
"@

    $envContent | Out-File -FilePath "$script:InstallPath/.env" -Encoding UTF8

    Write-Color "✅ 配置文件下载完成" "Green"
    Write-Host ""
}

# 启动服务
function Start-Service {
    Write-Color "🚀 启动 zhihusync 服务..." "Yellow"

    Set-Location $script:InstallPath

    # 先停止可能存在的旧容器（忽略错误）
    cmd /c "docker compose down 2>nul"

    # 使用 docker compose 启动
    cmd /c "docker compose up -d 2>nul"
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        # 尝试旧版命令
        cmd /c "docker-compose down 2>nul"
        cmd /c "docker-compose up -d 2>nul"
        $exitCode = $LASTEXITCODE
    }

    if ($exitCode -eq 0) {
        Write-Color "✅ 服务启动成功！" "Green"
    } else {
        Write-Color "⚠️  服务启动可能有问题，请检查日志" "Yellow"
    }
    Write-Host ""
}

# 显示完成信息
function Show-Completion {
    Write-Color @"
╔═══════════════════════════════════════════════════════════╗
║                   ✅ 安装完成！                           ║
╚═══════════════════════════════════════════════════════════╝
"@ "Green"
    Write-Host ""
    Write-Color "📱 访问 Web 界面:" "Yellow"
    Write-Host "   http://localhost:6067"
    Write-Host ""
    Write-Color "📁 安装目录:" "Yellow"
    Write-Host "   $script:InstallPath"
    Write-Host ""
    Write-Color "⚙️  配置文件:" "Yellow"
    Write-Host "   $script:InstallPath/.env"
    Write-Host ""
    Write-Color "📝 下一步:" "Yellow"
    Write-Host "   1. 编辑 .env 文件，配置你的知乎用户 ID"
    Write-Host "   2. 访问 http://localhost:6067 配置 Cookie"
    Write-Host "   3. 开始自动备份！"
    Write-Host ""
    Write-Color "🔧 常用命令:" "Yellow"
    Write-Host "   启动: docker compose up -d"
    Write-Host "   停止: docker compose down"
    Write-Host "   日志: docker compose logs -f"
    Write-Host ""
}

# 主流程
function Main {
    Show-Welcome
    Show-SystemInfo
    Test-Environment
    Configure-Install -DefaultDir $InstallDir
    Initialize-Directory
    Download-Config
    Start-Service
    Show-Completion
}

# 执行主流程
Main
