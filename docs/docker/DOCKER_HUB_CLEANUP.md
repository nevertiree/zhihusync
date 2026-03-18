# Docker Hub 镜像清理指南

## 清理旧版本镜像标签

### 需要删除的镜像标签

以下旧版本标签需要从 Docker Hub 删除：

- `v0.3.0`
- `v0.4.0`
- `v0.5.0`
- `v0.6.0`

### 手动删除步骤

#### 方法 1: Docker Hub Web 界面

1. 访问 https://hub.docker.com/r/nevertiree26/zhihusync/tags
2. 登录 Docker Hub 账号
3. 找到需要删除的标签
4. 点击标签右侧的删除按钮（垃圾桶图标）
5. 确认删除

#### 方法 2: 使用 Docker Hub API

```bash
# 设置 Docker Hub 认证信息
export DOCKER_HUB_USERNAME="nevertiree26"
export DOCKER_HUB_PASSWORD="your-password"

# 获取 JWT Token
TOKEN=$(curl -s -H "Content-Type: application/json" -X POST -d "{\"username\": \"$DOCKER_HUB_USERNAME\", \"password\": \"$DOCKER_HUB_PASSWORD\"}" https://hub.docker.com/v2/users/login/ | jq -r .token)

# 删除标签 (例如 v0.3.0)
curl -X DELETE \
  -H "Authorization: JWT $TOKEN" \
  "https://hub.docker.com/v2/repositories/nevertiree26/zhihusync/tags/v0.3.0/"

# 删除其他标签
curl -X DELETE \
  -H "Authorization: JWT $TOKEN" \
  "https://hub.docker.com/v2/repositories/nevertiree26/zhihusync/tags/v0.4.0/"

curl -X DELETE \
  -H "Authorization: JWT $TOKEN" \
  "https://hub.docker.com/v2/repositories/nevertiree26/zhihusync/tags/v0.5.0/"

curl -X DELETE \
  -H "Authorization: JWT $TOKEN" \
  "https://hub.docker.com/v2/repositories/nevertiree26/zhihusync/tags/v0.6.0/"
```

### 保留的镜像标签

清理后，Docker Hub 应只保留以下标签：

| 标签 | 说明 |
|------|------|
| `latest` | 最新稳定版 |
| `v1.0.0` | 当前正式版本 |

### 验证清理

```bash
# 列出所有标签
curl -s "https://hub.docker.com/v2/repositories/nevertiree26/zhihusync/tags/?page_size=100" | jq -r '.results[].name'
```

---

## 版本发布后的自动化清理策略

### 保留策略

- 保留最新的 `latest` 标签
- 保留最近 3 个版本标签
- 自动清理超过 3 个版本的旧标签

### 建议

建议定期（每季度）手动清理 Docker Hub 上的旧版本标签，以节省存储空间。
