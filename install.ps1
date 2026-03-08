# zhihusync 全自动安装脚本 (Windows)
# 使用方法: irm https://raw.githubusercontent.com/nevertiree/zhihusync/master/install.ps1 | iex

# 设置执行策略检查
if ($ExecutionContext.SessionState.LanguageMode -eq "FullLanguage") {
    $ErrorActionPreference = "Stop"
}

# 颜色输出函数
function Write-Color {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,

        [Parameter(Mandatory = $true)]
        [string]$Color
    )

    $colors = @{
        "Red"     = "Red"
        "Green"   = "Green"
        "Yellow"  = "Yellow"
        "Cyan"    = "Cyan"
        "Blue"    = "Blue"
    }

    Write-Host $Message -ForegroundColor $colors[$Color]
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

# 检查 Docker
function Test-Docker {
    Write-Color "🔍 检查 Docker 环境..." "Yellow"

    try {
        $dockerVersion = docker --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            try {
                $dockerInfo = docker info 2>$null
                if ($LASTEXITCODE -eq 0) {
                    Write-Color "✅ Docker 已安装: $dockerVersion" "Green"
                    return $true
                }
            }
            catch {
                Write-Color "⚠️  Docker 已安装但无法连接，可能需要启动 Docker Desktop" "Yellow"
                return $false
            }
        }
    }
    catch {
        # Docker 未安装
    }

    return $false
}

# 安装 Docker 指引
function Install-DockerGuide {
    Write-Color "⚠️  Docker 未安装或无法连接" "Yellow"
    Write-Host ""
    Write-Color "📥 Windows Docker 安装指南:" "Cyan"
    Write-Host ""
    Write-Host "   方法 1 (推荐): Docker Desktop"
    Write-Host "     1. 下载安装: https://docs.docker.com/desktop/install/windows-install/"
    Write-Host "     2. 安装时勾选 'Use WSL 2 instead of Hyper-V'"
    Write-Host "     3. 启动 Docker Desktop"
    Write-Host ""
    Write-Host "   方法 2: 命令行安装 (Windows 10/11)"
    Write-Host "     winget install Docker.DockerDesktop"
    Write-Host ""

    Read-Host "Docker 安装完成后，按回车键继续..."

    # 重新检查
    try {
        $dockerInfo = docker info 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Color "❌ Docker 仍然不可用，请检查安装" "Red"
            exit 1
        }
    }
    catch {
        Write-Color "❌ Docker 仍然不可用，请检查安装" "Red"
        exit 1
    }

    Write-Color "✅ Docker 就绪" "Green"
    Write-Host ""
}

# 配置数据目录
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
    Write-Host "     • D:\zhihusync\data          (D盘)"
    Write-Host "     • C:\Users\$env:USERNAME\zhihusync  (用户目录)"
    Write-Host "     • \\NAS\backup\zhihusync    (NAS 网络路径)"
    Write-Host ""

    # 默认路径
    $defaultDir = "$env:USERPROFILE\zhihusync\data"

    while ($true) {
        $dataDir = Read-Host "请输入数据保存目录 [默认: $defaultDir]"

        # 使用默认值
        if ([string]::IsNullOrWhiteSpace($dataDir)) {
            $dataDir = $defaultDir
        }

        # 解析路径
        $dataDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($dataDir)

        # 检查目录是否存在
        if (Test-Path -Path $dataDir -PathType Container) {
            Write-Host ""
            Write-Color "⚠️  目录已存在: $dataDir" "Yellow"
            $confirm = Read-Host "是否继续使用此目录? [Y/n]"
            if ($confirm -notmatch '^[Nn]$') {
                break
            }
        }
        else {
            # 目录不存在，询问用户是否创建
            Write-Host ""
            $confirm = Read-Host "目录不存在，是否创建? [Y/n]"
            if ($confirm -match '^[Nn]$') {
                Write-Host "   已取消，请重新选择目录"
                Write-Host ""
                continue
            }

            # 尝试创建目录
            try {
                New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
                Write-Color "✅ 目录创建成功" "Green"
                break
            }
            catch {
                Write-Color "❌ 无法创建目录: $dataDir" "Red"
                Write-Host "   请检查权限或选择其他位置"
                Write-Host ""
            }
        }
    }

    $script:DATA_DIR = $dataDir
    $script:CONFIG_DIR = Join-Path (Split-Path $dataDir -Parent) "config"
    New-Item -ItemType Directory -Path $script:CONFIG_DIR -Force | Out-Null

    Write-Host ""
    Write-Color "✅ 数据目录: $script:DATA_DIR" "Green"
    Write-Color "✅ 配置目录: $script:CONFIG_DIR" "Green"
    Write-Host ""
}

# 配置知乎用户 ID
function Configure-Zhihu {
    Write-Color "⚙️  配置知乎账号" "Yellow"
    Write-Host ""
    Write-Color "📋 如何获取知乎用户 ID:" "Cyan"
    Write-Host "   1. 浏览器登录知乎 https://www.zhihu.com"
    Write-Host "   2. 点击头像 → 我的主页"
    Write-Host "   3. 地址栏 URL 格式: https://www.zhihu.com/people/xxxxx"
    Write-Host "   4. xxxxx 就是你的用户 ID"
    Write-Host ""
    Write-Color "   示例:" "Blue"
    Write-Host "     • https://www.zhihu.com/people/zhang-san-123 → zhang-san-123"
    Write-Host "     • https://www.zhihu.com/people/wang-wu → wang-wu"
    Write-Host ""

    $zhihuId = Read-Host "请输入知乎用户 ID (可直接回车稍后在网页配置)"

    $script:ZHIHU_USER_ID = $zhihuId
    Write-Host ""
}

# 启动服务
function Start-Service {
    Write-Color "🚀 启动 zhihusync 服务..." "Yellow"
    Write-Host ""

    # 创建必要的子目录（Docker 挂载需要）
    Write-Color "📁 创建数据子目录..." "Blue"
    $subDirs = @("html", "meta", "images", "static")
    foreach ($dir in $subDirs) {
        $fullPath = Join-Path $script:DATA_DIR $dir
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
    Write-Color "✅ 子目录创建完成" "Green"
    Write-Host ""

    # 停止可能存在的旧容器
    docker rm -f zhihusync 2>$null | Out-Null

    # 转换 Windows 路径为 Docker 格式 (使用 / 分隔符)
    $dataDirDocker = $script:DATA_DIR -replace '\\', '/'
    $configDirDocker = $script:CONFIG_DIR -replace '\\', '/'

    # 使用 docker run 直接启动
    $dockerArgs = @(
        "run", "-d"
        "--name", "zhihusync"
        "--restart", "unless-stopped"
        "-p", "6067:6067"
        "-v", "$dataDirDocker/html:/app/data/html"
        "-v", "$dataDirDocker/meta:/app/data/meta"
        "-v", "$dataDirDocker/images:/app/data/images"
        "-v", "$dataDirDocker/static:/app/data/static"
        "-v", "$configDirDocker:/app/config"
        "-e", "ZHIHUSYNC_ZHIHU_USER_ID=$script:ZHIHU_USER_ID"
        "-e", "ZHIHUSYNC_ZHIHU_SCAN_INTERVAL=60"
        "-e", "ZHIHUSYNC_BROWSER_HEADLESS=true"
        "-e", "ZHIHUSYNC_LOGGING_LEVEL=INFO"
        "-e", "PLAYWRIGHT_BROWSER=chromium"
        "-e", "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1"
        "nevertiree26/zhihusync:latest"
    )

    try {
        & docker @dockerArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Docker run failed with exit code $LASTEXITCODE"
        }
    }
    catch {
        Write-Color "❌ 服务启动失败: $_" "Red"
        exit 1
    }

    Write-Color "✅ 服务启动成功！" "Green"
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
    Write-Host "   $script:DATA_DIR"
    Write-Host ""
    Write-Color "📝 下一步操作:" "Yellow"
    Write-Host "   1. 访问 http://localhost:6067"
    if ([string]::IsNullOrWhiteSpace($script:ZHIHU_USER_ID)) {
        Write-Host "   2. 在网页中配置知乎用户 ID"
        Write-Host "   3. 配置知乎 Cookie（按页面指引操作）"
        Write-Host "   4. 开始自动备份！"
    }
    else {
        Write-Host "   2. 配置知乎 Cookie（按页面指引操作）"
        Write-Host "   3. 开始自动备份！"
    }
    Write-Host ""
    Write-Color "🔧 常用命令:" "Blue"
    Write-Host "   查看日志: docker logs -f zhihusync"
    Write-Host "   停止服务: docker stop zhihusync"
    Write-Host "   启动服务: docker start zhihusync"
    Write-Host ""
    Write-Color "⚠️  重要提醒:" "Red"
    Write-Host "   数据保存在: $script:DATA_DIR"
    Write-Host "   请确保此目录安全，定期备份！"
    Write-Host ""
}

# 主流程
function Main {
    Show-Welcome

    if (-not (Test-Docker)) {
        Install-DockerGuide
    }

    Configure-DataDir
    Configure-Zhihu
    Start-Service
    Show-Completion
}

# 执行
Main
