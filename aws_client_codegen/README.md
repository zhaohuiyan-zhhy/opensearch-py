# Combined OSS/AOS/AOSS Python Client Code Generation

This package contains the OpenAPI overlay processing used to generate one
standard Python client for OSS OpenSearch, Amazon OpenSearch Service (AOS), and
Amazon OpenSearch Serverless (AOSS).

The unified generator:

1. Reads `api_spec/opensearch-openapi.yaml`.
2. Applies update actions from
   `api_spec/overlays/amazon-managed.overlay.yaml`.
3. Applies update actions from
   `api_spec/overlays/amazon-serverless.overlay.yaml`.
4. Ignores overlay remove actions so the complete base API remains available.
5. Generates the additive API union into the standard sync and async clients.

Distribution annotations are retained as specification metadata. They do not
filter the unified API surface and no runtime distribution checks are added.

## Review Layout

- `api_spec/`: bundled OpenSearch OpenAPI specification, overlays, and overlay
  processing.
- `templates/`: templates used only by the AOS/AOSS generated packages.
- `generate_api.py`: unified standard-client generation and drift check.
- `generate_aos_api.py` and `generate_aoss_api.py`: compatibility generators
  for the existing distribution-specific clients.
- `tests/cases/`: code-generation and generated-surface test implementations.
- `live_tests/`: credentialed AOS and AOSS coverage tests.
- `docs/`: unified and distribution-specific design documentation.

The unified generated sources remain in:

- `opensearchpy/client`
- `opensearchpy/_async/client`
- `opensearchpy/plugins`
- `opensearchpy/_async/plugins`

## Generate And Check

```shell
nox -rs generate
nox -rs generate -- --check
```

The direct compatibility command uses the same unified inputs:

```shell
python utils/generate_api.py
python -m aws_client_codegen.generate_api --check
```

Distribution-specific compatibility clients can still be generated or checked:

```shell
nox -rs generate_aos
nox -rs generate_aoss
nox -rs generate_aos -- --check
nox -rs generate_aoss -- --check
```

## Live Tests

```shell
python -m aws_client_codegen.live_tests.aos \
  --endpoint https://example.us-east-1.es.amazonaws.com \
  --username example

python -m aws_client_codegen.live_tests.aoss \
  --endpoint https://collection-id.aoss.us-east-1.on.aws \
  --region us-east-1 \
  --profile example
```
