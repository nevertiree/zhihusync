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

// 确认对话框
function confirm(message) {
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
});

// 键盘快捷键
document.addEventListener('keydown', function(e) {
    // ESC 关闭模态框
    if (e.key === 'Escape') {
        closeModal();
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
