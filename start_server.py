#!/usr/bin/env python
"""启动Web服务"""
import sys
sys.path.insert(0, 'src')

from web import start_web

if __name__ == "__main__":
    print("🚀 启动 zhihusync Web 服务...")
    print("📍 访问地址: http://localhost:6067")
    start_web(host="0.0.0.0", port=6067)
