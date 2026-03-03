# zhihusync - 知乎点赞内容备份服务
# 生产版本：基于预构建的基础镜像

FROM zhihusync-base:latest

# 设置工作目录
WORKDIR /app

# 复制应用代码（这一层会在代码变更时重新构建，但浏览器环境已存在）
COPY src/ /app/src/
COPY config/ /app/config/
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY entrypoint.sh /app/

# 创建数据目录并设置权限
RUN mkdir -p /app/data/html /app/data/meta /app/data/static/images && \
    chmod +x /app/entrypoint.sh

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV ZHIHUSYNC_ENV=docker
# 默认浏览器类型：auto（自动检测）
ENV PLAYWRIGHT_BROWSER=auto
# 禁用运行时浏览器下载（已打包在基础镜像中）
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# 暴露端口
EXPOSE 6067

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6067/api/stats')" || exit 1

# 启动命令
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "src.app", "--mode", "both"]
