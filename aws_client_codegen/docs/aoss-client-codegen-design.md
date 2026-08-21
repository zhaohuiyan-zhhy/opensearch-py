# AOSS 数据面 Python Client 自动生成设计

## 1. 结论

AOSS Client 由仓库内固定的 OpenSearch OpenAPI 和 AOSS Overlay 生成：

```text
aws_client_codegen/api_spec/opensearch-openapi.yaml
        +
aws_client_codegen/api_spec/overlays/amazon-serverless.overlay.yaml
        |
        v
Overlay 合并、amazon-serverless 过滤、$ref 校验
        |
        v
build/aoss-api-spec/opensearch-aoss.yaml
        |
        v
复用 OSS parser 和 method templates
        |
        v
opensearchpy/_async/aoss
        |
        v
unasync
        |
        v
opensearchpy/aoss
```

它是一套完整、独立的 AOSS 数据面 Client，不继承 OSS `OpenSearch` 或 AOS
`AOSOpenSearch`。这样不会因为继承而重新暴露已经从 AOSS spec 删除的接口。

当前输入生成：

- 373 个 AOSS path。
- 359 个 Python method。
- 同步和异步各 38 个 Python 文件。

多个 path 可以共享同一个 `x-operation-group`，因此 path 数量通常大于 method 数量。

## 2. 范围

本实现包含：

- AOSS 数据面 REST API。
- 同步 `AOSSOpenSearch`。
- 异步 `AsyncAOSSOpenSearch`。
- 固定输入、可重复生成和 `--check` 漂移检查。
- AOSS SigV4 live smoke test。

不包含：

- AOSS AWS 控制面 API。
- 凭证获取、endpoint discovery 或 region 推断。
- 强类型 request/response model。
- 需要外部 KMS、snapshot repository、模型或 connector 的测试资源创建。

代码生成只决定 HTTP method、path、query、body 和方法文档。endpoint、凭证和
SigV4 service 在构造 Client 时交给 transport。

## 3. 生成入口

AOS 和 AOSS 共用 `aws_client_codegen/generate_aos_api.py` 中的通用能力。`ClientConfig` 固定每种
distribution 的输入、输出、类名和 surface 验证规则。

AOSS 入口为：

```text
aws_client_codegen/generate_aoss_api.py
```

关键配置为：

```python
ClientConfig(
    label="AOSS",
    distribution="amazon-serverless",
    overlay_path=... / "amazon-serverless.overlay.yaml",
    async_output=Path("opensearchpy/_async/aoss"),
    sync_output=Path("opensearchpy/aoss"),
    async_class_name="AsyncAOSSOpenSearch",
    sync_class_name="AOSSOpenSearch",
)
```

生成器不接受 spec 或 Overlay 路径参数。更新输入后必须在同一个变更中重新生成并审查
Client 差异。

## 4. Overlay 的处理

先把 Overlay 应用到 base spec，再递归执行 `amazon-serverless` distribution filter：

- `x-distributions` 不包含 `amazon-serverless` 的节点被删除。
- `x-distributions-excluded` 包含 `amazon-serverless` 的节点被删除。
- Overlay `remove: true` 显式删除 AOSS 不支持的 path 或 property。
- Overlay `update` 深度合并 AOSS 新增或不同的 schema。
- 过滤后删除不含 HTTP operation 的空 path。
- 所有 local `$ref` 必须仍可解析，否则生成立即失败。

当前 AOSS Overlay 的主要动作如下。

### 4.1 删除接口

- 删除 root `HEAD /`，所以 AOSS Client 不生成 `ping()`。
- 删除 AOSS 不支持的 CAT API，只保留 aliases、indices 和 templates。
- 删除 node API。
- 删除 cluster health、settings、state、stats、reroute 等 cluster-management API。
- UltraWarm/cold API 由 base spec 的 distribution annotation 排除，不会进入 AOSS Client。

### 4.2 修改接口

- 从 field caps request body 删除 `fields`，保留同名 query parameter。
- 放宽 resolve-index response 的 required 字段，适配 AOSS 实际响应。
- snapshot restore 新增 `sourceCollectionId` 和 `allow_regex`。
- snapshot GET 新增包含 `sourceCollectionId` 的 preflight body。
- snapshot repository 新增 `crypto_settings`。

Python OSS parser 只识别通过 `$ref` 引用的 request body。Overlay 因此把 snapshot GET 的
body 建模为 `components.requestBodies.aoss.snapshot.get`，再从 operation 引用它。如果直接
使用 inline body，生成器会明确失败，避免静默漏掉 body。

## 5. Parser 和模板复用

合并后的 AOSS spec 继续进入原 OSS `read_modules()`：

```text
x-operation-group: snapshot.restore
        |
        v
namespace = snapshot
method = restore
        |
        v
API.to_python()
```

`API.to_python()` 继续使用 OSS 的方法模板，负责：

- 函数签名和 docstring。
- required 参数检查。
- `@query_params`。
- HTTP method 和 `_make_path(...)`。
- `transport.perform_request(...)`。

新增的 AOS package templates 只负责独立 package、root class、namespace class 和 plugins
facade 的外壳，AOSS 复用同一套 templates。同步 Client 由 async Client 通过 `unasync`
生成，不维护第二套方法模板。

## 6. 生成与检查

生成：

```bash
nox -rs generate_aoss
```

检查仓库内生成代码是否与 spec 和 Overlay 一致：

```bash
nox -rs generate_aoss -- --check
```

禁止手工修改：

```text
opensearchpy/_async/aoss/**
opensearchpy/aoss/**
```

接口变化必须修改 base spec、Overlay 或生成器，再重新执行生成命令。

## 7. 使用 AOSS Client

AOSS 使用 SigV4 service `aoss`。例如：

```python
import boto3

from opensearchpy import (
    AOSSOpenSearch,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)

credentials = boto3.Session(profile_name="my-profile").get_credentials()
auth = RequestsAWSV4SignerAuth(credentials, "us-east-1", "aoss")

client = AOSSOpenSearch(
    hosts=[{"host": "<collection-id>.aoss.us-east-1.on.aws", "port": 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)
```

认证不是生成代码中的接口特例。生成方法最终调用同一个 transport，transport 使用构造
Client 时提供的 endpoint 和 signer 发出请求。

## 8. 验证

自动测试覆盖：

- bundled spec 和 Overlay 路径。
- distribution filter 与 Overlay 删除后的反向 surface 断言。
- snapshot、field caps 和 resolve-index schema 变化。
- 过滤后 operation group 与 parser 生成方法集合完全一致。
- 同步和异步方法的 HTTP method、path、query 和 body。
- AOS 与 AOSS 两套生成目录的漂移检查。

真实 AOSS smoke test：

```bash
python -m aws_client_codegen.live_tests.aoss \
  --endpoint https://<collection-endpoint> \
  --region us-east-1 \
  --profile <aws-profile>
```

该脚本使用随机前缀并在 `finally` 中清理资源。当前覆盖 component template、index
template、index metadata、mapping、analyze、validate query、文档 CRUD、bulk、mget、
search、msearch、field caps、alias、CAT 和 PIT。一次真实 collection 验证结果为
`44 PASS / 0 FAIL / 3 SKIP`。

明确跳过：

- snapshot：需要 repository、KMS 和 cross-collection 配置。
- pipeline/plugin：需要 processor、模型、connector 或其他外部资源。
- `indices.put_settings`：需要先确认一个 AOSS 允许修改且不会影响共享 collection 的 setting。

## 9. 当前边界

生成链路可以保证“生成结果与过滤后的 spec 一致”，不能自动证明 Overlay 完整描述了产品
支持面。若 AOSS 实际不支持某个 base-spec operation，但 base spec 没有 distribution
annotation、Overlay 也没有删除它，生成器仍会忠实生成该方法。

因此 Overlay 维护需要同时依赖：

1. AOSS API 参考文档。
2. 产品 delta/Overlay 的权威制品。
3. 正向和反向 surface test。
4. 对低风险、可清理接口的真实资源验证。

发现 surface 缺口时，应在 API spec 或 Overlay 中修复并重新生成，不能直接删除生成文件。
