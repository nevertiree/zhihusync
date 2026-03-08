# zhihusync 卸载脚本 (Windows)
# 使用方法: irm https://raw.githubusercontent.com/nevertiree/zhihusync/master/uninstall.ps1 | iex

# 设置执行策略检查
if ($ExecutionContext.SessionState.LanguageMode -eq "FullLanguage") {
    $ErrorActionPreference = "Stop"
}

# 可能的镜像名称
$DOCKER_IMAGES = @(
    "nevertiree26/zhihusync:latest",
    "nevertiree26/zhihusync",
    "zhihusync:latest",
    "zhihusync"
)

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

# 显示警告
function Show-Warning {
    Clear-Host
    Write-Color @"
╔═══════════════════════════════════════════════════════════╗
║                     ⚠️  警告！⚠️                         ║
║                                                           ║
║   此操作将删除 zhihusync 容器及相关数据                   ║
║   包括：Docker 容器、备份的知乎回答、数据库、图片等        ║
║                                                           ║
║   数据删除后无法恢复！请确保已备份重要数据！              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"@ "Red"
    Write-Host ""
}

# 检查 Docker
function Test-Docker {
    try {
        $dockerVersion = docker --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            try {
                $dockerInfo = docker info 2>$null
                if ($LASTEXITCODE -eq 0) {
                    return $true
                }
            }
            catch {
                Write-Color "⚠️  Docker 未运行，请启动 Docker Desktop" "Yellow"
                return $false
            }
        }
    }
    catch {
        Write-Color "⚠️  Docker 未安装，可能已手动卸载" "Yellow"
    }
    return $false
}

# 查找已存在的容器
function Find-Container {
    $container = docker ps -aq --filter "name=zhihusync" 2>$null
    if ($LASTEXITCODE -eq 0 -and $container) {
        return $container
    }
    return $null
}

# 从 Docker 容器获取挂载的数据目录
function Get-DataDirFromContainer {
    param([string]$ContainerId)

    if ([string]::IsNullOrWhiteSpace($ContainerId)) {
        return $null
    }

    # 从容器的挂载点获取数据目录
    # 查找形如 "Source": "C:\Users\xxx\zhihusync\data\html" 的挂载
    $inspect = docker inspect $ContainerId 2>$null | ConvertFrom-Json
    if ($inspect -and $inspect.Mounts) {
        $htmlMount = $inspect.Mounts | Where-Object { $_.Destination -eq "/app/data/html" }
        if ($htmlMount) {
            # 获取父目录 (去掉 \html)
            $dataDir = Split-Path $htmlMount.Source -Parent
            return $dataDir
        }
    }
    return $null
}

# 获取容器使用的镜像
function Get-ImageFromContainer {
    param([string]$ContainerId)

    if ([string]::IsNullOrWhiteSpace($ContainerId)) {
        return $null
    }

    $inspect = docker inspect $ContainerId 2>$null | ConvertFrom-Json
    if ($inspect -and $inspect[0].Config) {
        return $inspect[0].Config.Image
    }
    return $null
}

# 配置数据目录（优先从容器获取，用户确认）
function Configure-DataDir {
    Write-Color "💾 配置数据目录位置" "Yellow"
    Write-Host ""

    # 优先从容器获取
    $detectedDir = $null
    if ($script:CONTAINER_ID) {
        $detectedDir = Get-DataDirFromContainer -ContainerId $script:CONTAINER_ID
    }

    if ($detectedDir -and (Test-Path $detectedDir)) {
        Write-Color "📌 从容器检测到数据目录:" "Cyan"
        Write-Host "   $detectedDir"
        Write-Host ""
        $confirm = Read-Host "确认卸载此目录? [Y/n]"
        if ($confirm -notmatch '^[Nn]$') {
            $script:DATA_DIR = $detectedDir
            $script:CONFIG_DIR = Join-Path (Split-Path $detectedDir -Parent) "config"
            return $true
        }
    }

    Write-Color "📌 请输入数据保存目录：" "Cyan"
    Write-Host "   这是 zhihusync 保存备份数据的位置，卸载将删除此目录"
    Write-Host ""

    while ($true) {
        Write-Host ""
        $dataDir = Read-Host "请输入数据目录路径"

        # 不能为空
        if ([string]::IsNullOrWhiteSpace($dataDir)) {
            Write-Color "❌ 请输入有效的目录路径" "Red"
            continue
        }

        # 解析路径
        $dataDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($dataDir)

        # 检查目录是否存在
        if (Test-Path -Path $dataDir -PathType Container) {
            Write-Host ""
            Write-Color "⚠️  发现目录: $dataDir" "Yellow"
            $confirm = Read-Host "确认卸载此目录的数据? [y/N]"
            if ($confirm -match '^[Yy]$') {
                $script:DATA_DIR = $dataDir
                $script:CONFIG_DIR = Join-Path (Split-Path $dataDir -Parent) "config"
                return $true
            }
            # 用户不确认，继续循环
            Write-Color "请重新输入正确的数据目录" "Cyan"
        }
        else {
            Write-Host ""
            Write-Color "❌ 目录不存在: $dataDir" "Red"
            $retry = Read-Host "是否尝试其他路径? [Y/n]"
            if ($retry -match '^[Nn]$') {
                return $false
            }
        }
    }
}

# 询问是否备份数据
function Ask-ForBackup {
    if (-not $script:DATA_DIR -or -not (Test-Path $script:DATA_DIR)) {
        return
    }

    # 计算数据目录大小
    $dataSize = (Get-ChildItem $script:DATA_DIR -Recurse -ErrorAction SilentlyContinue |
                Measure-Object -Property Length -Sum).Sum
    $sizeString = if ($dataSize -gt 1GB) {
        "{0:N2} GB" -f ($dataSize / 1GB)
    } elseif ($dataSize -gt 1MB) {
        "{0:N2} MB" -f ($dataSize / 1MB)
    } else {
        "{0:N2} KB" -f ($dataSize / 1KB)
    }

    Write-Host ""
    Write-Color "📦 数据目录大小: $sizeString" "Cyan"
    $backupChoice = Read-Host "是否在卸载前备份数据? [y/N]"

    if ($backupChoice -match '^[Yy]$') {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupDir = "$script:DATA_DIR.backup.$timestamp"
        Write-Color "📁 备份数据到: $backupDir" "Blue"

        try {
            Copy-Item -Path $script:DATA_DIR -Destination $backupDir -Recurse -Force
            Write-Color "✅ 数据备份成功" "Green"
            $script:BACKUP_DIR = $backupDir
        }
        catch {
            Write-Color "❌ 数据备份失败: $_" "Red"
            $continueAnyway = Read-Host "是否继续卸载? [y/N]"
            if ($continueAnyway -notmatch '^[Yy]$') {
                exit 0
            }
        }
    }
}

# 最终确认
function Final-Confirm {
    param([string]$ContainerId)

    Write-Host ""
    Write-Color "═══════════════════════════════════════════════════════════" "Red"
    Write-Color "                    最终确认" "Red"
    Write-Color "═══════════════════════════════════════════════════════════" "Red"
    Write-Host ""

    if ($ContainerId) {
        Write-Host "🐳 Docker 容器: zhihusync ($ContainerId)"
        $image = Get-ImageFromContainer -ContainerId $ContainerId
        if ($image) {
            Write-Host "🖼️  容器镜像: $image"
        }
    }
    else {
        Write-Host "🐳 Docker 容器: 未找到运行中的容器"
    }

    if ($script:DATA_DIR) {
        Write-Host "📁 数据目录: $($script:DATA_DIR)"
        Write-Host "⚙️  配置目录: $($script:CONFIG_DIR)"
    }

    if ($script:BACKUP_DIR) {
        Write-Host "💾 备份位置: $($script:BACKUP_DIR)"
    }

    Write-Host ""
    Write-Color "⚠️  以上数据和容器将被永久删除，无法恢复！" "Red"
    Write-Host ""

    $confirm = Read-Host "请输入 DELETE 确认卸载"

    if ($confirm -ne "DELETE") {
        Write-Color "❌ 卸载已取消" "Yellow"
        exit 0
    }
}

# 查找并删除相关镜像
function Find-AndRemoveImages {
    Write-Color "🖼️  检查 Docker 镜像..." "Blue"

    $foundImages = @()

    # 查找所有可能的镜像
    foreach ($img in $DOCKER_IMAGES) {
        $exists = docker images --format "{{.Repository}}:{{.Tag}}" | Select-String -Pattern "^$([regex]::Escape($img))$" -Quiet
        if ($exists) {
            $foundImages += $img
        }
    }

    # 同时查找没有标签的镜像（ dangling ）
    $dangling = docker images --filter "dangling=true" --format "{{.ID}}" 2>$null

    if ($foundImages.Count -eq 0 -and -not $dangling) {
        Write-Color "   未找到相关镜像" "Cyan"
        return
    }

    if ($foundImages.Count -gt 0) {
        Write-Host ""
        Write-Color "发现以下镜像:" "Cyan"
        foreach ($img in $foundImages) {
            Write-Host "   • $img"
        }
    }

    Write-Host ""
    $deleteImage = Read-Host "是否删除这些 Docker 镜像? [y/N]"
    if ($deleteImage -match '^[Yy]$') {
        foreach ($img in $foundImages) {
            Write-Color "   删除: $img" "Blue"
            docker rmi $img 2>$null | Out-Null
        }

        # 删除 dangling 镜像
        if ($dangling) {
            Write-Color "   清理悬空镜像..." "Blue"
            $dangling | ForEach-Object { docker rmi $_ 2>$null | Out-Null }
        }

        Write-Color "✅ Docker 镜像已删除" "Green"
    }
    Write-Host ""
}

# 执行卸载
function Perform-Uninstall {
    param([string]$ContainerId)

    Write-Color "🗑️  开始卸载..." "Yellow"
    Write-Host ""

    # 停止并删除容器
    if ($ContainerId) {
        Write-Color "📦 停止并删除 Docker 容器..." "Blue"
        docker stop zhihusync 2>$null | Out-Null
        docker rm -f zhihusync 2>$null | Out-Null
        Write-Color "✅ Docker 容器已删除" "Green"
        Write-Host ""
    }

    # 删除镜像
    Find-AndRemoveImages

    # 删除数据目录
    if ($script:DATA_DIR -and (Test-Path $script:DATA_DIR)) {
        Write-Color "📁 删除数据目录..." "Blue"
        Remove-Item -Path $script:DATA_DIR -Recurse -Force
        if ($script:CONFIG_DIR -and (Test-Path $script:CONFIG_DIR)) {
            Remove-Item -Path $script:CONFIG_DIR -Recurse -Force
        }
        Write-Color "✅ 数据目录已删除" "Green"
        Write-Host ""
    }

    Write-Color @"
╔═══════════════════════════════════════════════════════════╗
║                   ✅ 卸载完成！                           ║
╚═══════════════════════════════════════════════════════════╝
"@ "Green"
    Write-Host ""

    if ($script:BACKUP_DIR) {
        Write-Color "💾 数据已备份到:" "Cyan"
        Write-Host "   $($script:BACKUP_DIR)"
        Write-Host ""
    }

    Write-Color "📋 残留检查清单:" "Cyan"
    Write-Host "   • Docker 卷: docker volume ls | findstr zhihusync"
    Write-Host "   • 网络配置: docker network ls | findstr zhihusync"
    Write-Host "   • 所有镜像: docker images | findstr zhihusync"
    Write-Host ""
    Write-Color "如需重新安装，请访问:" "Yellow"
    Write-Host "   https://github.com/nevertiree/zhihusync"
    Write-Host ""
}

# 主流程
function Main {
    Show-Warning

    # 检查 Docker
    $dockerAvailable = Test-Docker

    # 查找容器（保存到全局变量供后续使用）
    $script:CONTAINER_ID = $null
    if ($dockerAvailable) {
        $script:CONTAINER_ID = Find-Container
    }

    # 配置数据目录（会使用 CONTAINER_ID 自动检测）
    if (-not (Configure-DataDir)) {
        Write-Color "❌ 卸载已取消" "Yellow"
        exit 0
    }

    # 询问是否备份
    Ask-ForBackup

    # 最终确认
    Final-Confirm -ContainerId $script:CONTAINER_ID

    # 执行卸载
    Perform-Uninstall -ContainerId $script:CONTAINER_ID
}

# 执行
Main
