#!/usr/bin/env pwsh
# zhihusync 全自动安装脚本 (Windows)
# 使用方法: powershell -Command "& { Invoke-Expression (Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/nevertiree/zhihusync/master/install.ps1').Content }"

param(
    [string]$DataDir = ""
)

$ErrorActionPreference = "Stop"

# 颜色输出
function Write-Color($Text, $Color = "White") {
    Write-Host $Text -ForegroundColor $Color
}

# 显示欢迎信息
function Show-Welcome {
    Clear-Host
    Write-Color @"
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🔄 zhihusync - 知乎点赞内容自动备份工具                    ║
║                                                           ║
║   全自动安装，只需配置数据保存位置                          ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"@ "Cyan"
    Write-Host ""
}

# 检查并安装 Docker
function Install-Docker {
    Write-Color "🔍 检查 Docker 环境..." "Yellow"

    # 检查 Docker 是否已安装
    try {
        $dockerVersion = docker --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Color "✅ Docker 已安装: $dockerVersion" "Green"
            return
        }
    } catch {}

    Write-Color "⚠️  Docker 未安装，准备自动安装..." "Yellow"
    Write-Host ""

    # Windows 安装 Docker Desktop
    Write-Color "📥 请下载并安装 Docker Desktop:" "Cyan"
    Write-Host "   https://docs.docker.com/desktop/install/windows-install/"
    Write-Host ""
    Write-Color "⚠️  安装完成后请:"
    Write-Host "   1. 启动 Docker Desktop"
    Write-Host "   2. 等待 Docker 启动完成（状态栏图标停止动画）"
    Write-Host "   3. 重新运行此安装脚本"
    Write-Host ""

    $openBrowser = Read-Host "是否现在打开下载页面? [Y/n]"
    if ($openBrowser -ne "n") {
        Start-Process "https://docs.docker.com/desktop/install/windows-install/"
    }

    exit 1
}

# 配置数据目录（核心配置）
function Configure-DataDir {
    Write-Color "💾 配置数据保存目录（重要！）" "Yellow"
    Write-Host ""
    Write-Color "📌 数据目录用于保存：" "Cyan"
    Write-Host "   • 备份的知乎回答 HTML 文件"
    Write-Host "   • 数据库（备份记录、元数据）"
    Write-Host "   • 下载的图片"
    Write-Host ""
    Write-Color "⚠️  请选择一个安全的位置，数据丢失无法恢复！" "Red"
    Write-Host ""

    # 显示参考示例
    Write-Color "📋 路径参考示例：" "Blue"
    Write-Host "   Windows:"
    Write-Host "     • $($env:USERPROFILE)\zhihusync\data    (推荐，用户目录)"
    Write-Host "     • D:\zhihusync\data                    (D盘数据盘)"
    Write-Host "     • E:\Backup\zhihusync                 (备份盘)"
    Write-Host ""
    Write-Host "   NAS/服务器:"
    Write-Host "     • \\NAS\backup\zhihusync               (网络存储)"
    Write-Host ""

    # 默认路径
    $defaultDir = "$env:USERPROFILE\zhihusync\data"

    while ($true) {
        $input = Read-Host "请输入数据保存目录 [默认: $defaultDir]"

        # 使用默认值
        if ([string]::IsNullOrWhiteSpace($input)) {
            $script:DataPath = $defaultDir
        } else {
            $script:DataPath = $input
        }

        # 检查/创建目录
        if (Test-Path $script:DataPath) {
            Write-Host ""
            Write-Color "⚠️  目录已存在: $($script:DataPath)" "Yellow"
            $confirm = Read-Host "是否继续使用此目录? [Y/n]"
            if ($confirm -eq "n") { continue }
            break
        } else {
            try {
                New-Item -ItemType Directory -Path $script:DataPath -Force | Out-Null
                Write-Color "✅ 目录创建成功" "Green"
                break
            } catch {
                Write-Color "❌ 无法创建目录: $($script:DataPath)" "Red"
                Write-Host "   请检查权限或选择其他位置"
                Write-Host ""
            }
        }
    }

    $script:ConfigPath = Join-Path (Split-Path $script:DataPath -Parent) "config"
    New-Item -ItemType Directory -Path $script:ConfigPath -Force | Out-Null

    Write-Host ""
    Write-Color "✅ 数据目录: $($script:DataPath)" "Green"
    Write-Color "✅ 配置目录: $($script:ConfigPath)" "Green"
    Write-Host ""
}

# 配置知乎用户 ID
function Configure-Zhihu {
    Write-Color "⚙️  配置知乎账号" "Yellow"
    Write-Host ""
    Write-Color "📋 如何获取知乎用户 ID：" "Cyan"
    Write-Host "   1. 浏览器登录知乎 https://www.zhihu.com"
    Write-Host "   2. 点击头像 → 我的主页"
    Write-Host "   3. 地址栏 URL 格式: https://www.zhihu.com/people/xxxxx"
    Write-Host "   4. xxxxx 就是你的用户 ID"
    Write-Host ""
    Write-Color "📋 示例：" "Blue"
    Write-Host "     • https://www.zhihu.com/people/zhang-san-123 → zhang-san-123"
    Write-Host "     • https://www.zhihu.com/people/wang-wu → wang-wu"
    Write-Host ""

    $script:ZhihuUserId = Read-Host "请输入知乎用户 ID (可直接回车稍后在网页配置)"
    Write-Host ""
}

# 启动服务
function Start-Zhihusync {
    Write-Color "🚀 启动 zhihusync 服务..." "Yellow"
    Write-Host ""

    # 停止可能存在的旧容器
    docker rm -f zhihusync 2>&1 | Out-Null

    # 使用 docker run 直接启动（无需下载任何文件）
    $runArgs = @(
        "run", "-d",
        "--name", "zhihusync",
        "--restart", "unless-stopped",
        "-p", "6067:6067",
        "-v", "$($script:DataPath)/html:/app/data/html",
        "-v", "$($script:DataPath)/meta:/app/data/meta",
        "-v", "$($script:DataPath)/images:/app/data/images",
        "-v", "$($script:DataPath)/static:/app/data/static",
        "-v", "$($script:ConfigPath):/app/config",
        "-e", "ZHIHUSYNC_ZHIHU_USER_ID=$($script:ZhihuUserId)",
        "-e", "ZHIHUSYNC_ZHIHU_SCAN_INTERVAL=60",
        "-e", "ZHIHUSYNC_BROWSER_HEADLESS=true",
        "-e", "ZHIHUSYNC_LOGGING_LEVEL=INFO",
        "-e", "PLAYWRIGHT_BROWSER=chromium",
        "-e", "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1",
        "nevertiree26/zhihusync:latest"
    )

    & docker @runArgs

    if ($LASTEXITCODE -eq 0) {
        Write-Color "✅ 服务启动成功！" "Green"
    } else {
        Write-Color "❌ 服务启动失败" "Red"
        exit 1
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
    Write-Color "📱 访问 Web 界面:" "Cyan"
    Write-Host "   http://localhost:6067"
    Write-Host ""
    Write-Color "💾 数据保存位置（重要！）:" "Yellow"
    Write-Host "   $($script:DataPath)"
    Write-Host ""
    Write-Color "📝 下一步操作:" "Yellow"

    if ([string]::IsNullOrWhiteSpace($script:ZhihuUserId)) {
        Write-Host "   1. 访问 http://localhost:6067"
        Write-Host "   2. 在网页中配置知乎用户 ID"
    } else {
        Write-Host "   1. 访问 http://localhost:6067"
    }
    Write-Host "   2. 配置知乎 Cookie（按页面指引操作）"
    Write-Host "   3. 开始自动备份！"
    Write-Host ""
    Write-Color "🔧 常用命令:" "Blue"
    Write-Host "   查看日志: docker logs -f zhihusync"
    Write-Host "   停止服务: docker stop zhihusync"
    Write-Host "   启动服务: docker start zhihusync"
    Write-Host "   重启服务: docker restart zhihusync"
    Write-Host ""
    Write-Color "⚠️  重要提醒:" "Red"
    Write-Host "   数据保存在: $($script:DataPath)"
    Write-Host "   请确保此目录安全，定期备份！"
    Write-Host ""
}

# 主流程
function Main {
    Show-Welcome
    Install-Docker
    Configure-DataDir
    Configure-Zhihu
    Start-Zhihusync
    Show-Completion
}

# 执行
Main
