// zhihusync Cookie Helper - Popup Script

document.addEventListener('DOMContentLoaded', () => {
  const getCookieBtn = document.getElementById('get-cookie-btn');
  const copyCookieBtn = document.getElementById('copy-cookie-btn');
  const serverUrlInput = document.getElementById('server-url');
  const statusDiv = document.getElementById('status');
  const previewDiv = document.getElementById('cookie-preview');
  
  let currentCookies = null;
  
  // 加载保存的服务器地址
  chrome.storage.local.get(['zhihusync_server'], (result) => {
    if (result.zhihusync_server) {
      serverUrlInput.value = result.zhihusync_server;
    }
  });
  
  // 显示状态消息
  function showStatus(message, type = 'info') {
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
    
    // 3秒后自动隐藏成功消息
    if (type === 'success') {
      setTimeout(() => {
        statusDiv.className = 'status';
      }, 3000);
    }
  }
  
  // 获取知乎 Cookie
  async function getZhihuCookies() {
    try {
      // 尝试多种方式获取知乎 cookie
      let allCookies = [];
      
      // 方式1: 获取 .zhihu.com 域名下的 cookie
      try {
        const cookies1 = await chrome.cookies.getAll({ domain: '.zhihu.com' });
        console.log('方式1 (.zhihu.com):', cookies1.length, '个');
        allCookies = allCookies.concat(cookies1);
      } catch (e) {
        console.log('方式1 失败:', e);
      }
      
      // 方式2: 获取 zhihu.com 域名下的 cookie
      try {
        const cookies2 = await chrome.cookies.getAll({ domain: 'zhihu.com' });
        console.log('方式2 (zhihu.com):', cookies2.length, '个');
        allCookies = allCookies.concat(cookies2);
      } catch (e) {
        console.log('方式2 失败:', e);
      }
      
      // 方式3: 获取 www.zhihu.com 下的 cookie
      try {
        const cookies3 = await chrome.cookies.getAll({ domain: 'www.zhihu.com' });
        console.log('方式3 (www.zhihu.com):', cookies3.length, '个');
        allCookies = allCookies.concat(cookies3);
      } catch (e) {
        console.log('方式3 失败:', e);
      }
      
      // 方式4: 通过 url 获取所有 cookie
      try {
        const cookies4 = await chrome.cookies.getAll({ url: 'https://www.zhihu.com' });
        console.log('方式4 (url):', cookies4.length, '个');
        allCookies = allCookies.concat(cookies4);
      } catch (e) {
        console.log('方式4 失败:', e);
      }
      
      // 去重
      const seen = new Set();
      const cookies = allCookies.filter(c => {
        const key = `${c.name}@${c.domain}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      
      console.log('去重后共:', cookies.length, '个');
      console.log('Cookie 名称:', cookies.map(c => c.name));
      
      if (!cookies || cookies.length === 0) {
        throw new Error('未找到知乎 Cookie，请确保已登录知乎');
      }
      
      // 检查关键 cookie
      const hasZCO = cookies.some(c => c.name === 'z_c0');
      if (!hasZCO) {
        throw new Error('未找到关键 Cookie (z_c0)，请重新登录知乎');
      }
      
      // 转换为 storage_state 格式
      const storageState = {
        cookies: cookies.map(c => ({
          name: c.name,
          value: c.value,
          domain: c.domain,
          path: c.path,
          httpOnly: c.httpOnly,
          secure: c.secure,
          ...(c.expirationDate && { expires: Math.floor(c.expirationDate) }),
          ...(c.sameSite && { sameSite: c.sameSite })
        })),
        origins: []
      };
      
      return storageState;
    } catch (error) {
      console.error('getZhihuCookies 错误:', error);
      throw error;
    }
  }
  
  // 发送 Cookie 到服务器
  async function sendCookiesToServer(cookies) {
    const serverUrl = serverUrlInput.value.trim() || 'http://localhost:6067';
    
    // 保存服务器地址
    chrome.storage.local.set({ zhihusync_server: serverUrl });
    
    const response = await fetch(`${serverUrl}/api/cookies`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        cookies: JSON.stringify(cookies),
        format: 'json'
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '服务器返回错误');
    }
    
    return await response.json();
  }
  
  // 获取并发送 Cookie
  getCookieBtn.addEventListener('click', async () => {
    try {
      getCookieBtn.disabled = true;
      getCookieBtn.textContent = '⏳ 获取中...';
      showStatus('正在获取知乎 Cookie...', 'info');
      
      // 获取 cookie
      console.log('开始获取 Cookie...');
      const cookies = await getZhihuCookies();
      currentCookies = cookies;
      
      console.log('获取到的 Cookie:', cookies);
      
      // 显示预览
      const cookieCount = cookies.cookies.length;
      const cookieNames = cookies.cookies.map(c => c.name).join(', ');
      previewDiv.textContent = `已获取 ${cookieCount} 个 Cookie:\n` + 
        cookies.cookies.map(c => `• ${c.name} (${c.domain})`).join('\n');
      previewDiv.classList.add('show');
      
      showStatus(`获取到 ${cookieCount} 个 Cookie，正在发送...`, 'info');
      
      // 发送到服务器
      console.log('发送到服务器:', serverUrlInput.value);
      const result = await sendCookiesToServer(cookies);
      
      console.log('服务器响应:', result);
      showStatus(result.message || 'Cookie 保存成功！', 'success');
      
      // 显示复制按钮
      copyCookieBtn.style.display = 'block';
      
    } catch (error) {
      console.error('错误详情:', error);
      showStatus('错误: ' + (error.message || '获取失败'), 'error');
    } finally {
      getCookieBtn.disabled = false;
      getCookieBtn.textContent = '🍪 获取知乎 Cookie';
    }
  });
  
  // 复制到剪贴板
  copyCookieBtn.addEventListener('click', async () => {
    if (!currentCookies) return;
    
    try {
      const cookieText = JSON.stringify(currentCookies, null, 2);
      await navigator.clipboard.writeText(cookieText);
      showStatus('已复制到剪贴板', 'success');
    } catch (error) {
      showStatus('复制失败: ' + error.message, 'error');
    }
  });
  
  // 检查当前页面是否为知乎
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentTab = tabs[0];
    if (!currentTab.url || !currentTab.url.includes('zhihu.com')) {
      showStatus('⚠️ 请先打开知乎网站 (zhihu.com)', 'info');
    }
  });
});