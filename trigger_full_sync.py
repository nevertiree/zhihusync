#!/usr/bin/env python
"""触发全量同步"""
import time
import requests

def wait_for_service(max_retries=30):
    """等待服务启动"""
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:6067/api/stats", timeout=2)
            if response.status_code == 200:
                print("✅ 服务已就绪")
                return True
        except:
            pass
        print(f"⏳ 等待服务启动... ({i+1}/{max_retries})")
        time.sleep(1)
    return False

def trigger_full_sync():
    """触发全量同步"""
    print("🚀 正在触发全量采集...")
    try:
        response = requests.post("http://localhost:6067/api/sync/init", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {data.get('message', '全量同步已启动')}")
            return True
        else:
            print(f"❌ 启动失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def check_status():
    """检查同步状态"""
    print("\n📊 同步状态检查 (每5秒刷新，按Ctrl+C停止)")
    print("-" * 60)
    try:
        while True:
            try:
                response = requests.get("http://localhost:6067/api/sync/status", timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status', 'unknown')
                    message = data.get('message', '')
                    progress = data.get('progress', 0)

                    status_emoji = {
                        'idle': '⏸️',
                        'running': '🔄',
                        'success': '✅',
                        'failed': '❌'
                    }.get(status, '❓')

                    print(f"\r{status_emoji} [{status.upper()}] {message} ({progress}%)", end='', flush=True)

                    if status in ['success', 'failed']:
                        print(f"\n\n{'='*60}")
                        print(f"同步结束: {message}")
                        break

            except Exception as e:
                print(f"\r⚠️ 获取状态失败: {e}", end='', flush=True)

            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n⏹️ 用户停止监控")

if __name__ == "__main__":
    print("="*60)
    print("🚀 zhihusync 全量采集工具")
    print("="*60)

    if wait_for_service():
        if trigger_full_sync():
            check_status()
    else:
        print("❌ 服务未启动，请手动启动服务后重试")
