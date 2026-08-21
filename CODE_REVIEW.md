# Code Review: 统一 OSS/AOS/AOSS 客户端生成

审阅范围：当前工作区（未提交）针对 OSS/AOS/AOSS 客户端统一化的改动。

结论：**生成逻辑、Java overlay 对齐和真实资源验证均已通过，没有发现阻塞合入的问题。**

---

## 一、验证结果

### 本地生成与回归

| 检查 | 结果 |
|---|---|
| 统一客户端漂移检查 `python -m aws_client_codegen.generate_api --check` | 通过 |
| AOS 客户端漂移检查 `python -m aws_client_codegen.generate_aos_api --check` | 通过 |
| AOSS 客户端漂移检查 `python -m aws_client_codegen.generate_aoss_api --check` | 通过 |
| 统一/AOS/AOSS 的 spec、同步客户端、异步客户端测试 | `36 passed` |
| `git diff --check` | 通过 |
| AOSS live runner 的 Black、isort、flake8 | 通过 |

### 真实资源测试

| 目标 | 客户端 | 结果 | 清理 |
|---|---|---|---|
| AOS `test-yzh` | `AOSOpenSearch` / `AsyncAOSOpenSearch` | `83 PASS / 0 FAIL / 24 SKIP` | 索引、异步索引、data stream、模板、pipeline、ISM policy 均确认不存在 |
| AOSS collection `6rceodx4d32o1mqw1nla` | `AOSSOpenSearch` + SigV4 (`aoss`) | `44 PASS / 0 FAIL / 3 SKIP` | 索引、index template、component template 均删除并验证 |
| AOS `test-yzh` | 标准统一 `OpenSearch` | 创建索引、自动 ID 写入、按 ID 读取、删除索引全部通过 | 已确认临时索引不存在 |
| AOSS collection `6rceodx4d32o1mqw1nla` | 标准统一 `OpenSearch` + SigV4 (`aoss`) | 创建索引、写入、最终一致读取、删除索引全部通过 | 已确认临时索引不存在 |

机器可读报告：

- `/tmp/aos-live-smoke-report.json`
- `/tmp/aoss-live-smoke-report.json`

AOS 的跳过项主要来自该域启用了 Optimized Engine（append-only，部分 search/count/update API 被域代理限制），以及 snapshot、UltraWarm、remote store 等需要额外资源或会修改域级配置的操作。AOSS 的 3 个跳过类别是 snapshot、依赖外部资源的 pipeline/plugin 操作，以及未确认可变 setting 的 `indices.put_settings`。

---

## 二、实现评价

- `apply_additive_overlay` 只应用 AOS/AOSS overlay 的 `update`，忽略 `remove`，生成 `OSS ∪ AOS 新增 ∪ AOSS 新增` 的超集客户端，与 Java 客户端策略一致。
- 核心实现集中在 `aws_client_codegen/`；旧的 `utils/generate_*`、测试入口和文档入口保留为兼容薄壳。
- Python 请求体使用不透明的 `body: Any`，因此 Java 侧 `field_caps` 的 query/body 同名字段处理不需要移植。
- AOSS live runner 使用项目已声明依赖的 `botocore.session.Session` 加载 profile，不再依赖未声明的 `boto3`。

---

## 三、已处理的原 review 问题

### UltraWarm 已与 Java overlay 对齐

统一客户端现在包含 7 个 UltraWarm 操作：

- `migrate_to_warm`
- `migrate_to_hot`
- `migrate_to_cold`
- `cancel_migration`
- `get_migration_status`
- `list_migration_status`
- `update_migration`

`update_migration` 支持可选请求体。`migrate_to_cold` 的参数与
`opensearch-java/aws-client-codegen/overlays/amazon-managed.overlay.yaml`
一致，仅包含 `index` 和 `cluster_manager_timeout`；原 review 推测的时间范围请求体不属于当前 Java overlay。

### OSS spec 额外更新是预期结果

刷新 vendored base spec 后，标准同步和异步客户端额外生成了以下 OSS 变化：

1. `msearch` 新增 `allow_partial_results` query 参数。
2. `snapshot.get` 新增可选 `body`。
3. `search_relevance.delete_scheduled_experiments`。
4. `search_relevance.get_scheduled_experiments`。
5. `search_relevance.post_scheduled_experiments`。

这些变化来自 base OSS spec，不来自 AOS/AOSS overlay。PR 描述应明确说明本次统一生成同时有意包含了这次 OSS spec 刷新。

---

## 四、提交前注意

`aws_client_codegen/`、统一客户端测试、统一设计文档和生成的 UltraWarm 客户端当前仍有未跟踪文件。提交前需要完整 `git add`，避免只提交兼容入口而漏掉 codegen 主体。
