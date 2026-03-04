# zhihusync Cookie Helper

一键获取知乎 Cookie 并发送到 zhihusync 服务器的浏览器扩展。

## 安装方法

### Chrome / Edge (Chromium 内核)

1. 下载 `zhihusync-extension.zip` 并解压
2. 打开浏览器扩展管理页面:
   - Chrome: `chrome://extensions/`
   - Edge: `edge://extensions/`
3. 开启"开发者模式" (右上角开关)
4. 点击"加载已解压的扩展程序"
5. 选择解压后的扩展文件夹

### Firefox (暂不支持)

目前仅支持 Chromium 内核浏览器 (Chrome, Edge, 360浏览器等)。

## 使用方法

1. **登录知乎**: 确保已在浏览器中登录 zhihu.com
2. **点击扩展图标**: 点击浏览器工具栏上的 🚀 图标
3. **设置服务器地址**: 默认为 `http://localhost:6067`，根据实际情况修改
4. **获取 Cookie**: 点击"获取知乎 Cookie"按钮
5. **完成**: Cookie 将自动发送到 zhihusync 服务器

## 功能特点

- ✅ 一键获取知乎所有 Cookie
- ✅ 自动验证关键 Cookie (z_c0)
- ✅ 自动发送到服务器
- ✅ 支持复制到剪贴板
- ✅ 保存服务器地址配置

## 注意事项

- 扩展需要访问知乎网站的权限以读取 Cookie
- 扩展需要访问本地服务器的权限以发送 Cookie
- 如果服务器不在本地，请修改服务器地址

## 手动获取 Cookie (备用方法)

如果扩展无法使用，可以手动获取:

1. 打开知乎网站并登录
2. 按 F12 打开开发者工具
3. 切换到 Application/应用 → Cookies → zhihu.com
4. 复制所有 Cookie
5. 粘贴到 zhihusync 配置页面的"手动配置"中