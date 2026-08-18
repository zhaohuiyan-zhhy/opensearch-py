# AOS 数据面 Python Client 自动生成设计

## 1. 结论

本方案新增一条与 OSS 生成器并行的 AOS 生成流水线：

```text
OpenSearch OpenAPI
        +
AOS OpenAPI Overlay
        |
        v
合并、amazon-managed 过滤、$ref 校验
        |
        v
完整 AOS OpenAPI
        |
        v
复用 OSS parser 和 API method templates
        |
        v
opensearchpy/_async/aos
        |
        v
unasync
        |
        v
opensearchpy/aos
```

核心约束如下：

1. `utils/generate_api.py` 保持不变。
2. AOS 使用独立入口 `utils/generate_aos_api.py`。
3. AOS Client 的唯一接口依据是 `API spec + Overlay`。
4. 生成完整 AOS Client，不继承 OSS `OpenSearch` 来补充少量差异。
5. REST 方法继续使用 OSS Jinja method templates。
6. 原模板不能描述完整独立包时，增加 AOS package templates。
7. AOS 和 AOSS 使用同一套通用生成能力及各自独立配置，不生成 AWS 控制面 Client。

## 2. 背景

OSS `opensearch-py` 已有以下生成流程：

```text
published opensearch-openapi.yaml
        |
        v
utils/generate_api.py
        |
        v
opensearchpy/_async/client + opensearchpy/_async/plugins
        |
        v
unasync
        |
        v
opensearchpy/client + opensearchpy/plugins
```

AOS 数据面与 OSS 数据面高度相似，但接口集合和接口定义并不完全相同：

- AOS 有额外 endpoint，例如 UltraWarm migration。
- 某些 OSS path 在 `amazon-managed` 中被排除。
- 同一个 operation group 的部分 path 可能被排除，其他 path 仍然保留。
- 后续 AOS 可能修改已有 endpoint 的参数、body 或 HTTP method。

因此不能仅将 AOS 专有方法手写到 OSS Client 上，也不能假设 OSS Client 暴露的每个方法
都能在 AOS 使用。AOS Client 应由过滤后的完整 AOS OpenAPI 决定。

## 3. 目标与非目标

### 3.1 目标

- 从仓库内固定的基础 OpenAPI 和 AOS Overlay 生成 Client。
- 支持 Overlay `update`、`remove` 和 distribution annotation。
- Overlay target 或 local `$ref` 失效时立即失败。
- 生成完整同步和异步 AOS Client。
- 保持生成方法的签名、docstring、参数检查和请求调用风格与 OSS 一致。
- 生成 core namespace、plugin namespace 和 plugins facade。
- 提供 `--check` 检测生成代码漂移。
- 生成代码禁止手工修改。

### 3.2 非目标

- AOS/AOSS 控制面 Client。
- SigV4 签名、凭证获取和刷新。
- AWS endpoint resolver。
- TLS、重试、连接池和节点选择策略。
- request/response 强类型模型。
- 自动发现最新 spec 或 Overlay。

认证、endpoint 和连接配置仍由构造 Client 时传入的 transport 参数处理，不进入 REST API
代码生成。

## 4. 权威输入

生成器固定读取仓库内的两个输入：

```text
utils/aos_api_spec/opensearch-openapi.yaml
utils/aos_api_spec/overlays/amazon-managed.overlay.yaml
```

这两个文件随 Client 仓库提交，生成命令不接受文件路径参数。更新输入时，应从版本化的
AOS API-spec 制品同步 base spec 和 Overlay，在同一个变更中重新生成 Client 并审查差异。
不能在生成时直接使用不固定的 `latest`，否则同一个 Client commit 无法重复生成。

Overlay 的 `extends: ../opensearch-openapi.yaml` 表达仓库内的逻辑依赖。当前 Overlay engine
仍通过固定路径传入两个文档，不根据 `extends` 动态下载或寻找其他文件。

## 5. 输出

中间 AOS OpenAPI：

```text
build/aos-api-spec/opensearch-aos.yaml
```

最终异步 Client：

```text
opensearchpy/_async/aos/
  __init__.py
  client/
    __init__.py
    cat.py
    indices.py
    ultrawarm.py
    plugins.py
    ...
  plugins/
    sql.py
    ml.py
    ...
```

最终同步 Client：

```text
opensearchpy/aos/
```

当前输入生成：

- 452 个 AOS path。
- 409 个 Python method。
- 同步和异步各 40 个 Python 文件。

path 数量大于 method 数量是正常的。多个 OpenAPI path 可以拥有相同
`x-operation-group`，最终合并为一个 Python 方法。

## 6. 组件设计

### 6.1 独立入口

实现：

```text
utils/generate_aos_api.py
```

职责：

1. 接收基础 spec 和 Overlay。
2. 构造完整 AOS OpenAPI。
3. 调用未修改的 OSS parser。
4. 使用模板生成完整 async package。
5. 使用 `unasync` 生成 sync package。
6. 格式化生成文件。
7. 在 `--check` 模式比较临时生成目录和仓库目录。

该入口不调用 OSS `dump_modules()`，因为后者的输出路径固定为
`opensearchpy/_async/client` 和 `opensearchpy/_async/plugins`，还会修改 OSS 根 Client。

### 6.2 Overlay engine

实现：

```text
utils/aos_api_spec/overlay.py
```

当前支持 Overlay 1.0 中本项目使用的子集：

- exact JSONPath target。
- mapping `update`。
- `remove: true`。
- mapping deep merge。

支持的 target 示例：

```text
$.paths
$.paths['/_some/path'].get
$.components.parameters
```

当前不支持 wildcard、filter expression 等复杂 JSONPath。原因是现有 Overlay 只使用 exact
target，受限语法可以在基础 spec 结构变化时准确失败。如果未来 Overlay 使用复杂 JSONPath，
应采用完整的 OpenAPI Overlay 实现，而不是不断扩展自定义 parser。

### 6.3 Distribution filter

合并后递归处理：

```yaml
x-distributions:
  - amazon-managed
```

以及：

```yaml
x-distributions-excluded:
  - amazon-managed
```

规则为：

- 没有标记：保留。
- `x-distributions` 不包含 `amazon-managed`：删除。
- `x-distributions-excluded` 包含 `amazon-managed`：删除。

过滤对象不限于 operation，也包括 component、schema property 和数组成员。过滤后删除不再
包含 HTTP operation 的空 path item。

过滤发生在 path/operation 层，不是 method 名层。例如 `indices.clear_cache` 的无 index
path 可以被 AOS 排除，但带 index 的 path 仍然保留，最终 Python 方法也仍然存在，只是可选
path 集合发生变化。

### 6.4 `$ref` 校验

distribution filter 可能删除 component。生成前遍历全部 local `$ref`：

```text
#/components/...
```

每个 JSON Pointer 都必须可以在过滤后的文档中解析。这样可以阻止保留 operation 引用已经
删除的 parameter、request body、response 或 schema。

### 6.5 OSS parser 复用

不复制 OSS `read_modules()` 的数百行转换逻辑，也不修改原文件。AOS 生成器构造一个只包含
`text` 的本地 response，并在受控 context 中临时替换 `generate_api.requests.get` 的返回值：

```text
AOS distribution document
        |
        v
LocalSpecResponse.text
        |
        v
unmodified generate_api.read_modules()
```

选择该适配方式的原因：

- 用户要求不修改原 `generate_api.py`。
- 原 `read_modules()` 内部固定下载远程 spec，没有 document/path 参数。
- 临时替换只包围一次同步 parser 调用，不影响生成结果和运行时 Client。
- parser、patch rules、operation grouping 和 API object 都与 OSS 使用同一份实现。

它的限制是依赖 OSS generator 的内部入口。如果未来 OSS generator 正式提供
`read_modules(document)`，应删除该适配层并直接调用公共入口。

原 parser 还会硬编码跳过 `ism` namespace，因为 OSS Client 使用手写的 Index Management
Client。独立 AOS package 没有这个手写兜底，而且本方案要求接口来自 AOS spec，因此 AOS
适配层在调用 parser 前临时将 `ism.*` 映射到内部 namespace，解析后再恢复为 `ism`。这样
不修改 OSS generator，同时由模板生成 spec 中的 12 个 ISM 方法：

```text
AOS spec: ism.get_policy
        |
        v
parser alias: _aos_codegen_ism.get_policy
        |
        v
restore: client.plugins.ism.get_policy
```

### 6.6 Method templates

每个 API 仍调用：

```python
API.to_python()
```

因此继续复用：

```text
utils/templates/base
utils/templates/func_params
utils/templates/required
utils/templates/url
utils/templates/substitutions
utils/templates/overrides/**
```

这些模板决定：

- Python 方法签名。
- `@query_params`。
- required path/body 校验。
- docstring。
- HTTP method。
- `_make_path(...)`。
- `transport.perform_request(...)`。

AOS Overlay 新增的 UltraWarm operation 没有专用 Python 模板，它们直接使用 OSS
`base` method template。

### 6.7 新增 package templates

新增：

```text
utils/templates/aos/module
utils/templates/aos/root_client
utils/templates/aos/plugins_client
utils/templates/aos/package_init
```

原 OSS method templates 只生成方法体，不能描述一个新的独立 package。OSS
`Module.dump()` 又依赖已经存在的 OSS 文件头和固定目录，所以不能用于 AOS 输出。新增模板
负责：

- namespace class 外壳。
- `AsyncAOSOpenSearch` 根类。
- namespace 初始化。
- plugins facade。
- package import 和 `__all__`。
- 生成文件声明。

`tasks.get` override 使用 `warnings`，`ping` override 使用 `TransportError`。原 OSS 文件
通过既有手写 header 提供这些 import；AOS 是从空目录生成，因此新模板必须显式补充这些
依赖。这是模板差异，不是 API 特例。

### 6.8 完整 Client 而不是继承 OSS

`AsyncAOSOpenSearch` 继承通用底层 `Client`，不继承 `AsyncOpenSearch`：

```text
generic Client
    |
    +-- transport
    |
    +-- AsyncAOSOpenSearch
          +-- AOS root methods
          +-- AOS namespace clients
          +-- AOS plugin clients
```

原因：

- 继承 OSS facade 会继续暴露 AOS spec 已删除的接口。
- 已有 namespace 发生参数变化时，简单增加一个 delta namespace 无法完整覆盖。
- 完整生成可以让 Python API surface 与过滤后的 AOS OpenAPI 一一对应。
- AOS 与 OSS 的升级节奏可以独立验证。

代价是会提交数百个与 OSS 当前相同的方法。这里优先保证 AOS spec 是接口事实来源，而不是
减少生成文件数量。

### 6.9 Async-first

与 OSS 保持一致：

1. 只直接生成 async 文件。
2. `unasync` 将 `_async/aos` 转换为 `aos`。
3. 替换：

```text
AsyncAOSOpenSearch -> AOSOpenSearch
AsyncTransport     -> Transport
```

这样同步和异步 Client 不会形成两套独立模板。

## 7. 与 OSS 实现的差异

| 项目 | OSS | AOS | 原因 |
| --- | --- | --- | --- |
| 入口 | `generate_api.py` | `generate_aos_api.py` | 不改变既有 OSS 流程 |
| 输入 | 固定下载 OSS latest | 仓库内固定 spec + Overlay | AOS 需要两个固定版本输入 |
| spec 处理 | 直接解析 | 合并、distribution filter、ref 校验 | 形成真实 AOS 接口集合 |
| parser | `read_modules()` | 复用同一个 `read_modules()` | 保持转换规则一致 |
| ISM | parser 跳过，使用手写 Client | alias 后从 spec 生成 | 独立 AOS package 没有 OSS 手写兜底 |
| method template | OSS templates | 同一套 OSS templates | 方法行为不分叉 |
| package shell | 既有文件和 header | 新增 AOS templates | OSS dump 路径和 scaffolding 固定 |
| Client 继承 | OSS `Client` | 通用 `Client` | 避免泄露被 AOS 排除的方法 |
| 输出 | `client/`、`plugins/` | 独立 `aos/` package | 两种 API surface 隔离 |
| 同步生成 | `unasync` | `unasync` | 保持一致 |
| 漂移检查 | 依赖常规生成 | `--check` 临时目录比较 | CI 禁止手工修改生成文件 |

## 8. 一条 API 的完整转换

Overlay 定义：

```yaml
/_ultrawarm/migration/{index}/_warm:
  post:
    x-operation-group: ultrawarm.migrate_to_warm
    x-distributions:
      - amazon-managed
    parameters:
      - $ref: "#/components/parameters/ultrawarm.migrate___path.index"
      - $ref: "#/components/parameters/ultrawarm.migrate___query.cluster_manager_timeout"
```

转换步骤：

1. `$.paths` update 将 path 合并到基础 spec。
2. distribution filter 保留 `amazon-managed` operation。
3. `$ref` validator 验证两个 parameter。
4. OSS parser 使用 `x-operation-group` 拆分：

```text
namespace = ultrawarm
name = migrate_to_warm
```

5. parser 将 `index` 转为 required path part。
6. parser 将 `cluster_manager_timeout` 转为 query parameter。
7. `utils/templates/base` 生成异步方法。
8. `utils/templates/aos/module` 将方法放入 `UltrawarmClient`。
9. root template 创建 `self.ultrawarm`。
10. `unasync` 生成同步方法。

最终调用：

```python
client.ultrawarm.migrate_to_warm(
    index="logs-2026",
    cluster_manager_timeout="1m",
)
```

最终请求：

```text
POST /_ultrawarm/migration/logs-2026/_warm
```

## 9. 命令

直接运行：

```bash
python -m utils.generate_aos_api
```

通过 nox：

```bash
nox -rs generate_aos
```

检查生成漂移：

```bash
nox -rs generate_aos -- --check
```

`--check` 仍会写中间 AOS spec，但最终 Client 写入临时目录，然后与仓库中的 async/sync AOS
目录逐文件比较。

## 10. 文件所有权

允许手工修改：

```text
utils/generate_aos_api.py
utils/aos_api_spec/overlay.py
utils/templates/aos/*
docs/source/aos-client-codegen-design.md
```

从版本化 API-spec 制品同步，不应手工修改：

```text
utils/aos_api_spec/opensearch-openapi.yaml
utils/aos_api_spec/overlays/amazon-managed.overlay.yaml
```

禁止手工修改：

```text
opensearchpy/_async/aos/**
opensearchpy/aos/**
```

接口变化应首先修改 API spec 或 Overlay，再重新生成。

## 11. 测试策略

### 11.1 Overlay

- update 使用 deep merge，不删除已有 sibling。
- include/exclude distribution annotation 生效。
- dangling local `$ref` 立即失败。

### 11.2 Parser 和 template

- 本地 merged spec 能通过未修改的 OSS parser。
- operation group 正确转换为 namespace 和方法名。
- 过滤后 spec 的 operation group 集合必须与生成方法集合完全相等。
- 生成方法包含 body、path 和 `perform_request`。
- 六个 UltraWarm operation 必须全部存在。

### 11.3 Client 行为

- AOS Client 不继承 OSS `OpenSearch` facade。
- Overlay operation 产生正确 HTTP method、path 和 query。
- 基础 spec operation 也存在于独立 AOS Client。
- plugin operation 可以通过 `client.plugins` 调用。
- 同步和异步行为均覆盖。

### 11.4 CI

建议固定 API-spec 和 Overlay 制品版本后执行：

```text
generate_aos --check
pytest focused generator/client tests
black --check
isort --check
flake8
pylint
mypy
sphinx-build -W
```

## 12. 风险与限制

| 风险 | 当前处理 |
| --- | --- |
| Overlay 与基础 spec 不匹配 | exact target 和 `$ref` fail fast |
| 仓库内输入落后于 API-spec 制品 | 通过专用更新变更同步固定版本并重新生成 |
| OSS parser 内部接口变化 | 单测和完整生成检查 |
| 原 method override 依赖既有 header | AOS package template 显式建模 import |
| 完整 Client 产生大量重复代码 | 接受，换取准确 API surface |
| spec 中出现 inline request body | AOS 输入校验立即失败，阻止 OSS parser 静默遗漏 |
| 复杂 JSONPath Overlay | 改用完整 Overlay engine |
| AOS runtime 配置缺失 | 由 transport 构造参数处理，不属于 codegen |

## 13. 后续演进

1. API-spec 项目发布版本化 base spec、AOS Overlay 和可选的 merged spec。
2. 专用更新流程下载固定版本、校验 SHA256，并将输入和重新生成的 Client 一起提交。
3. 如果发布 merged AOS spec，可在更新流程中校验本地 `spec + Overlay` 的合并结果，但用户
   运行生成器时仍不需要选择输入文件。
4. OSS generator 如果提供正式的 document parser API，移除 `LocalSpecResponse` 适配层。
5. AOSS 已使用独立 Overlay、独立输出 package 和独立验收；详细设计见
   `aoss-client-codegen-design.md`。

## 14. 验收标准

- `utils/generate_api.py` 相对仓库 `HEAD` 无修改。
- 存在独立 `generate_aos` nox session。
- base spec 和 Overlay 固定存放在 `utils/aos_api_spec/`，命令不要求路径参数。
- 中间 AOS spec 完成 distribution filter 和 `$ref` 校验。
- 生成完整 AOS root/core/plugin Client。
- REST 方法使用 OSS method templates。
- package scaffolding 使用新增 AOS templates。
- async 和 sync Client 均可导入和发送正确请求。
- `--check` 能识别生成代码漂移。
- 生成器测试、Client 测试、静态检查和文档严格构建通过。
