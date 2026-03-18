# 常见问题

## Cookie 有效期多久？

知乎 Cookie 通常有效期为 1-3 个月，过期后需要重新配置。

---

## 可以备份多个账号吗？

目前一个实例只支持一个账号。如需备份多个账号，需要启动多个实例，使用不同的数据目录和端口：

```bash
# 实例 1 - 账号 A
docker run -d --name zhihusync-a -p 6067:6067 -v ~/data-a:/app/data nevertiree26/zhihusync:latest

# 实例 2 - 账号 B
docker run -d --name zhihusync-b -p 6068:6067 -v ~/data-b:/app/data nevertiree26/zhihusync:latest
```

---

## 备份的数据在哪里？

- HTML 文件: `data/html/`
- 数据库: `data/meta/zhihusync.db`
- 图片: `data/static/images/`

---

## 如何查看备份内容？

1. 通过 Web 界面的"内容浏览"页面
2. 直接打开 `data/html` 目录下的 HTML 文件

---

## 如何卸载？

使用一键卸载脚本：

```bash
# Linux / macOS / WSL2
curl -fsSL https://raw.githubusercontent.com/nevertiree/zhihusync/master/uninstall.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/nevertiree/zhihusync/master/uninstall.ps1 | iex
```

卸载脚本会：
- 自动检测数据目录
- 必须用户确认才会删除
- 需要输入 DELETE 最终确认

---

## 如何更新到最新版本？

```bash
# 拉取最新镜像
docker pull nevertiree26/zhihusync:latest

# 重启容器
docker restart zhihusync
```

或使用 docker-compose：

```bash
docker-compose pull
docker-compose up -d
```
