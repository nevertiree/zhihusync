# 配置指南

## 1. 获取知乎 Cookie

### 方式一：EditThisCookie 插件（推荐）

1. 安装 [EditThisCookie](https://www.editthiscookie.com/) 浏览器扩展
2. 登录 [知乎](https://www.zhihu.com)
3. 点击扩展图标 → Export → Export as JSON
4. 将 JSON 粘贴到 Web 界面的 Cookie 输入框

### 方式二：浏览器开发者工具

在知乎页面按 F12 打开开发者工具，在 Console 中执行：

```javascript
JSON.stringify(document.cookie.split(';').map(c => {
  const [n, ...v] = c.trim().split('=');
  return {name: n, value: v.join('='), domain: '.zhihu.com'};
}))
```

复制输出的 JSON 粘贴到配置页面。

---

## 2. 获取用户 ID

1. 登录知乎，点击头像 → **我的主页**
2. 地址栏 URL: `https://www.zhihu.com/people/xxx`
3. `xxx` 就是你的用户 ID

---

## 3. 高级配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 扫描间隔 | 自动同步时间间隔（分钟） | 30 |
| 最大条目数 | 每次同步最多获取条数 | 50 |
| 保存评论 | 是否备份评论内容 | true |
| 无头模式 | 是否在后台运行浏览器 | true |

---

## 4. 数据目录

数据目录用于保存所有备份内容：

| 路径 | 说明 |
|------|------|
| `data/html/` | 备份的知乎回答 HTML 文件 |
| `data/meta/` | 数据库（备份记录、元数据） |
| `data/images/` | 下载的图片 |
| `data/static/` | 静态资源（头像等） |

**建议路径：**
- **Windows**: `D:\zhihusync\data` 或 `E:\zhihusync\data`
- **Linux**: `$HOME/zhihusync/data` 或 `/opt/zhihusync/data`
- **NAS**: 挂载的共享文件夹

⚠️ **请务必确保数据目录安全，定期备份！**
