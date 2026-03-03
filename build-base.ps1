# 构建基础镜像（包含 Chrome + Playwright）
# 这个镜像只需构建一次，后续应用构建会复用它

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "构建 zhihusync-base 基础镜像" -ForegroundColor Cyan
Write-Host "包含: Python 3.11 + Playwright + Chromium + Firefox" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 构建基础镜像
docker build `
    -f Dockerfile.base `
    -t zhihusync-base:latest `
    .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 基础镜像构建失败" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ 基础镜像构建完成！" -ForegroundColor Green
Write-Host ""
Write-Host "镜像信息:" -ForegroundColor Cyan
docker images zhihusync-base:latest

Write-Host ""
Write-Host "基础镜像大小:" -ForegroundColor Cyan
docker images zhihusync-base:latest --format "{{.Size}}"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "提示: 现在可以构建应用镜像了" -ForegroundColor Green
Write-Host "  docker-compose build" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Green
