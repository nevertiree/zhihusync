// zhihusync Cookie Helper - Background Script

// 安装时初始化
chrome.runtime.onInstalled.addListener(() => {
  console.log('zhihusync Cookie Helper 已安装');
});

// 监听来自 content script 的消息（如果需要）
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getCookies') {
    chrome.cookies.getAll({ domain: 'zhihu.com' }, (cookies) => {
      sendResponse({ cookies });
    });
    return true; // 保持消息通道开放
  }
});