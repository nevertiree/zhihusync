# API 接口文档

## 基础信息

- **Base URL**: `http://localhost:6067`
- **Content-Type**: `application/json`

---

## 接口列表

### 统计信息

```http
GET /api/stats
```

获取备份统计信息。

**响应示例：**
```json
{
  "total_answers": 100,
  "total_comments": 500,
  "last_sync": "2026-03-18 10:00:00"
}
```

---

### 配置管理

```http
GET /api/config
```

获取当前配置。

```http
POST /api/config
```

更新配置。

**请求体：**
```json
{
  "zhihu_user_id": "your-user-id",
  "scan_interval": 30,
  "max_items_per_scan": 50
}
```

---

### Cookie 管理

```http
POST /api/cookies
```

更新 Cookie。

**请求体：**
```json
{
  "cookies": [{"name": "z_c0", "value": "xxx", "domain": ".zhihu.com"}]
}
```

```http
GET /api/cookies/check
```

检查 Cookie 状态。

```http
POST /api/cookies/test
```

测试 Cookie 登录状态。

---

### 同步任务

```http
POST /api/sync/start
```

开始同步任务。

```http
POST /api/sync/stop
```

停止同步任务。

```http
GET /api/sync/status
```

获取同步状态。

```http
GET /api/sync/history
```

获取同步历史记录。

---

### 回答管理

```http
GET /api/answers
```

获取回答列表。

**查询参数：**
- `page`: 页码，默认 1
- `per_page`: 每页数量，默认 20
- `search`: 搜索关键词

```http
DELETE /api/answers/{id}
```

删除指定回答。

---

### 日志

```http
GET /api/logs
```

获取日志内容。

**查询参数：**
- `lines`: 行数，默认 100
