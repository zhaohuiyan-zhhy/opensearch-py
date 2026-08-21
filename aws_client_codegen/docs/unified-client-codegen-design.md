# OSS/AOS/AOSS 统一 Python Client 生成设计

## 结论

标准 `OpenSearch` 和 `AsyncOpenSearch` Client 由三份固定输入生成：

```text
opensearch-openapi.yaml
        +
amazon-managed.overlay.yaml
        +
amazon-serverless.overlay.yaml
        |
        v
按顺序应用 update，忽略 remove
        |
        v
opensearch-unified.yaml
        |
        v
现有 Python parser、method templates 和 unasync
        |
        v
opensearchpy/_async/client + opensearchpy/_async/plugins
        |
        v
opensearchpy/client + opensearchpy/plugins
```

这与 Java `aws-client-codegen/UnifiedSpecGenerator` 的语义一致。生成结果是 OSS、AOS 和
AOSS API 的 additive union，不根据 endpoint 类型在运行时隐藏方法。

## 合并规则

生成器按以下顺序处理输入：

1. 读取 base OpenAPI。
2. 应用 AOS overlay 的所有 `update` action。
3. 应用 AOSS overlay 的所有 `update` action。
4. 跳过两个 overlay 中的所有 `remove: true` action。
5. 不执行 `x-distributions` 或 `x-distributions-excluded` 过滤。
6. 校验全部 local `$ref`。

`update` 使用 mapping deep merge，后应用的 AOSS update 在相同字段上覆盖先前值。数组作为
完整值替换。Overlay target 不存在、action 无效或 `$ref` 悬空时立即失败。

忽略 `remove` 是统一客户端的关键约束。例如 AOSS overlay 可以删除 AOSS 不支持的 CAT
接口，但统一客户端仍需保留这些 OSS/AOS 接口。调用目标服务不支持的方法时，由服务返回
错误。

## 生成流程

入口为：

```text
aws_client_codegen/generate_api.py
```

它将合并 spec 写到：

```text
build/aws-api-spec/opensearch-unified.yaml
```

随后把本地 spec 交给现有 `utils/generate_api.py` parser。Parser、Jinja method template、
override 和 async-to-sync 规则均继续复用，不维护第二套标准客户端模板。

统一生成器验证过滤掉 parser 明确跳过的手写 ISM namespace 后，spec 中每个
`x-operation-group` 都有对应生成方法，并额外断言 AOS UltraWarm 与 AOSS snapshot
operation 存在。

当前固定输入生成 529 个 path 和 476 个 Python method。主要 AWS 增量包括：

- 标准 Client 新增 `client.ultrawarm` namespace。
- UltraWarm namespace 包含与 Java overlay 一致的 `update_migration` endpoint。
- `snapshot.get` 接受 AOSS cross-collection preflight body。
- AOSS snapshot restore 和 repository schema 更新进入统一 spec。

## 命令

生成并格式化标准 Client：

```bash
nox -rs generate
```

检测提交的生成代码是否漂移：

```bash
nox -rs generate -- --check
```

`--check` 在临时目录复制手写 Client 外壳，重新生成、isort 和 Black，然后逐目录比较同步与
异步的 client/plugin 文件。

直接入口也可使用：

```bash
python -m aws_client_codegen.generate_api
python -m aws_client_codegen.generate_api --check
```

## 兼容边界

现有 `AOSOpenSearch`、`AOSSOpenSearch` 及其独立生成命令暂时保留，避免删除已发布的公开
API。主生成流程和标准 `OpenSearch` Client 使用统一 spec；独立命令仍可用于
distribution-filtered 诊断和兼容验证。

生成器不负责 SigV4、凭证、endpoint discovery、TLS 或重试。标准 transport 继续根据 Client
构造参数处理这些运行时能力。
