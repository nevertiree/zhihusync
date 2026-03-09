/* zhihusync 管理界面通用脚本 */

// 显示 Toast 通知
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    }[type] || 'ℹ️';

    toast.innerHTML = `
        <span>${icon}</span>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// 更新侧边栏状态
function updateSidebarStatus(status) {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');

    const statusMap = {
        'idle': { text: '就绪', class: '' },
        'running': { text: '同步中...', class: 'running' },
        'success': { text: '就绪', class: 'success' },
        'failed': { text: '失败', class: 'failed' }
    };

    const info = statusMap[status] || statusMap['idle'];

    dot.className = 'status-dot ' + info.class;
    text.textContent = info.text;
}

// 关闭模态框
function closeModal() {
    const modal = document.getElementById('detail-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// 打开模态框
function openModal(title, content) {
    const modal = document.getElementById('detail-modal');
    const titleEl = document.getElementById('modal-title');
    const bodyEl = document.getElementById('modal-body');

    if (titleEl) titleEl.textContent = title;
    if (bodyEl) bodyEl.innerHTML = content;
    if (modal) modal.classList.add('active');
}

// 格式化日期
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN');
}

// 格式化相对时间
function timeAgo(dateStr) {
    if (!dateStr) return '-';

    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);

    if (diff < 60) return '刚刚';
    if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
    if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
    if (diff < 604800) return Math.floor(diff / 86400) + ' 天前';

    return formatDate(dateStr);
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 确认对话框 - 使用原生 confirm，避免命名冲突
function showConfirm(message) {
    return window.confirm(message);
}

// API 请求封装
async function api(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };

    const res = await fetch(url, { ...defaultOptions, ...options });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
}

// 初始化代码高亮（如果页面有代码块）
document.addEventListener('DOMContentLoaded', function() {
    // 为所有表格行添加点击效果
    document.querySelectorAll('.data-table tbody tr').forEach(row => {
        row.addEventListener('click', function(e) {
            if (e.target.tagName !== 'A' && e.target.tagName !== 'BUTTON') {
                this.classList.toggle('selected');
            }
        });
    });

    // 自动隐藏成功消息
    document.querySelectorAll('.alert-success').forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 3000);
    });

    // 获取并更新同步状态
    fetchSyncStatus();
    // 每 5 秒刷新一次状态
    setInterval(fetchSyncStatus, 5000);
});

// 获取同步状态
async function fetchSyncStatus() {
    try {
        const res = await fetch('/api/sync/status');
        if (res.ok) {
            const data = await res.json();
            updateSidebarStatus(data.status);
        }
    } catch (e) {
        console.error('获取同步状态失败:', e);
    }
}

// 键盘快捷键
document.addEventListener('keydown', function(e) {
    // ESC 关闭模态框
    if (e.key === 'Escape') {
        closeModal();
        // ESC 也关闭侧边栏
        closeSidebar();
    }

    // Ctrl/Cmd + R 刷新
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        if (typeof loadLogs === 'function') {
            loadLogs();
        }
        if (typeof loadStats === 'function') {
            loadStats();
        }
    }
});

// ==================== 侧边栏悬停展开/点击关闭 ====================
(function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');
    
    if (!sidebar || !mainContent) return;
    
    // 页面加载时：检查是否需要保持展开状态（从其他页面跳转过来）
    if (sessionStorage.getItem('sidebarKeepOpen') === 'true') {
        sidebar.classList.add('expanded');
        // 清除标记，下次点击主内容区时才会收起
    }
    
    // 鼠标进入侧边栏展开
    sidebar.addEventListener('mouseenter', function() {
        sidebar.classList.add('expanded');
    });
    
    // 注意：不在 mouseleave 时收起，保持展开状态
    
    // 点击主内容区关闭
    mainContent.addEventListener('click', function() {
        if (sidebar.classList.contains('expanded')) {
            sidebar.classList.remove('expanded');
            // 清除保持展开的标记
            sessionStorage.removeItem('sidebarKeepOpen');
        }
    });
    
    // 点击侧边栏内的链接时，设置标记保持展开状态
    sidebar.addEventListener('click', function(e) {
        const link = e.target.closest('a');
        // 如果点击的是链接，设置标记让新页面保持展开
        if (link) {
            sessionStorage.setItem('sidebarKeepOpen', 'true');
            // 链接点击正常执行，不阻止
            return;
        }
        e.stopPropagation();
    });
})();

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar && sidebar.classList.contains('expanded')) {
        sidebar.classList.remove('expanded');
    }
}

// ==================== 初始化采集 ====================

async function startInitSync() {
    const btn = document.getElementById('init-sync-btn');
    const status = document.getElementById('init-sync-status');

    // 确认对话框
    if (!showConfirm('确定要开始初始化采集吗？\n\n这将：\n- 重新爬取全部历史点赞数据\n- 可能需要较长时间（取决于点赞数量）\n- 可以中途停止')) {
        return;
    }

    try {
        btn.disabled = true;
        btn.textContent = '🚀 初始化采集中...';
        status.textContent = '启动中...';

        const res = await fetch('/api/sync/init', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await res.json();

        if (data.status === 'started') {
            showToast(data.message, 'success');
            status.textContent = '采集中，请查看日志页面了解进度';

            // 3秒后跳转到日志页面
            setTimeout(() => {
                window.location.href = '/logs';
            }, 3000);
        } else if (data.status === 'error') {
            showToast(data.message, 'error');
            btn.disabled = false;
            btn.textContent = '🚀 开始初始化采集';
            status.textContent = '';
        }
    } catch (err) {
        showToast('启动失败: ' + err.message, 'error');
        btn.disabled = false;
        btn.textContent = '🚀 开始初始化采集';
        status.textContent = '';
    }
}
