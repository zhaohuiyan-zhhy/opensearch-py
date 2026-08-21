#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

import argparse
import copy
import filecmp
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple, cast
from unittest.mock import patch

import isort
import requests
import unasync
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from aws_client_codegen.api_spec import build_distribution_spec
from utils import generate_api as oss_generator

CODE_ROOT = Path(__file__).absolute().parent.parent
AOS_SPEC_ROOT = Path(__file__).absolute().parent / "api_spec"
API_SPEC_PATH = AOS_SPEC_ROOT / "opensearch-openapi.yaml"
GENERATED_HEADER_PATH = CODE_ROOT / "utils" / "generated_file_headers.txt"
AWS_TEMPLATE_ENV = Environment(
    autoescape=select_autoescape(["html", "xml"]),
    loader=FileSystemLoader([Path(__file__).absolute().parent / "templates"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
HTTP_METHODS = {
    "delete",
    "get",
    "head",
    "options",
    "patch",
    "post",
    "put",
    "trace",
}
UTILITY_NAMES = (
    "SKIP_IN_PATH",
    "_normalize_hosts",
    "_escape",
    "_make_path",
    "query_params",
    "_bulk_body",
    "_base64_auth_header",
    "AddonClient",
)
LICENSE_HEADER = """# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.
"""
PARSER_NAMESPACE_ALIASES = {"ism": "_aos_codegen_ism"}


@dataclass(frozen=True)
class ClientConfig:
    """Fixed inputs, outputs, and validation rules for one AWS distribution."""

    label: str
    distribution: str
    overlay_path: Path
    merged_spec_path: Path
    async_output: Path
    sync_output: Path
    async_class_name: str
    sync_class_name: str
    nox_session: str
    required_operations: Tuple[str, ...] = ()
    forbidden_operations: Tuple[str, ...] = ()
    required_namespaces: Tuple[str, ...] = ()


AOS_CONFIG = ClientConfig(
    label="AOS",
    distribution="amazon-managed",
    overlay_path=AOS_SPEC_ROOT / "overlays" / "amazon-managed.overlay.yaml",
    merged_spec_path=CODE_ROOT / "build" / "aos-api-spec" / "opensearch-aos.yaml",
    async_output=Path("opensearchpy/_async/aos"),
    sync_output=Path("opensearchpy/aos"),
    async_class_name="AsyncAOSOpenSearch",
    sync_class_name="AOSOpenSearch",
    nox_session="generate_aos",
    required_operations=(
        "ultrawarm.cancel_migration",
        "ultrawarm.get_migration_status",
        "ultrawarm.list_migration_status",
        "ultrawarm.migrate_to_cold",
        "ultrawarm.migrate_to_hot",
        "ultrawarm.migrate_to_warm",
        "ultrawarm.update_migration",
    ),
    required_namespaces=("ism",),
)
DISTRIBUTION = AOS_CONFIG.distribution
OVERLAY_PATH = AOS_CONFIG.overlay_path
MERGED_SPEC_PATH = AOS_CONFIG.merged_spec_path
ASYNC_OUTPUT = AOS_CONFIG.async_output
SYNC_OUTPUT = AOS_CONFIG.sync_output


class LocalSpecResponse:
    """Minimal requests response used to feed a local spec to the OSS parser."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        self.text = yaml.safe_dump(
            document,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )


def generated_header(config: ClientConfig = AOS_CONFIG) -> str:
    """Returns the license and distribution-specific generated-file warning."""
    warning = GENERATED_HEADER_PATH.read_text(encoding="utf-8").strip()
    warning = warning.replace(
        "`nox -rs generate`",
        f"`nox -rs {config.nox_session}`",
    )
    return f"{LICENSE_HEADER}\n{warning}\n"


def module_apis(module: Any) -> List[Any]:
    """Returns APIs collected by the unmodified OSS Module implementation."""
    return cast(List[Any], module._apis)  # pylint: disable=protected-access


def parse_modules(document: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Parses a local distribution spec through the unmodified OSS parser.

    The OSS entry point downloads its input internally and does not accept a
    document argument. Replacing that single HTTP call keeps its parsing and
    method-template behavior unchanged without modifying generate_api.py.
    """
    parser_document = copy.deepcopy(document)
    for path_item in parser_document.get("paths", {}).values():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_group = operation.get("x-operation-group")
            if not isinstance(operation_group, str):
                continue
            for namespace, alias in PARSER_NAMESPACE_ALIASES.items():
                prefix = f"{namespace}."
                if operation_group.startswith(prefix):
                    operation["x-operation-group"] = operation_group.replace(
                        prefix, f"{alias}.", 1
                    )

    response = LocalSpecResponse(parser_document)
    with patch.object(requests, "get", return_value=response):
        modules = oss_generator.read_modules()
    parsed_modules = cast(Dict[str, Any], modules)

    for namespace, alias in PARSER_NAMESPACE_ALIASES.items():
        if alias not in parsed_modules:
            continue
        module = parsed_modules.pop(alias)
        module.namespace = namespace
        module.namespace_new = class_name(namespace)
        for api in module_apis(module):
            api.namespace = namespace
        parsed_modules[namespace] = module

    return parsed_modules


def validate_parser_input(document: Mapping[str, Any]) -> None:
    """Rejects OpenAPI shapes that the unmodified OSS parser silently skips."""
    for path, path_item in document.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            request_body = operation.get("requestBody")
            if isinstance(request_body, dict) and "$ref" not in request_body:
                operation_group = operation.get("x-operation-group", "<unknown>")
                raise ValueError(
                    "The OSS parser requires a referenced requestBody: "
                    f"{method.upper()} {path} ({operation_group})"
                )


def operation_names(modules: Mapping[str, Any]) -> List[str]:
    """Returns normalized generated operation names."""
    return sorted(
        api.name if namespace == "__init__" else f"{namespace}.{api.name}"
        for namespace, module in modules.items()
        for api in module_apis(module)
    )


def spec_operation_names(document: Mapping[str, Any]) -> List[str]:
    """Returns operation groups expected to become Python methods."""
    operations = set()
    for path_item in document.get("paths", {}).values():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_group = operation.get("x-operation-group")
            if not isinstance(operation_group, str):
                raise ValueError("AOS operation is missing x-operation-group")
            if operation_group == "nodes.hot_threads" and "deprecated" in operation:
                continue
            operations.add(operation_group)
    return sorted(operations)


def validate_modules(
    document: Mapping[str, Any],
    modules: Mapping[str, Any],
    config: ClientConfig = AOS_CONFIG,
) -> None:
    """Checks that every filtered operation group was generated."""
    expected_operations = set(spec_operation_names(document))
    operations = set(operation_names(modules))
    if operations != expected_operations:
        missing = sorted(expected_operations - operations)
        unexpected = sorted(operations - expected_operations)
        raise ValueError(
            f"Generated {config.label} operation set does not match the filtered spec; "
            f"missing={missing}, unexpected={unexpected}"
        )

    required = set(config.required_operations)
    missing = sorted(required - operations)
    if missing:
        raise ValueError(
            f"{config.label} Overlay operations were not generated: {missing}"
        )

    forbidden = sorted(set(config.forbidden_operations) & operations)
    if forbidden:
        raise ValueError(
            f"{config.label} excluded operations were generated: {forbidden}"
        )

    missing_namespaces = sorted(set(config.required_namespaces) - set(modules))
    if missing_namespaces:
        raise ValueError(
            f"{config.label} spec namespaces were not generated: "
            f"{missing_namespaces}"
        )


def class_name(namespace: str) -> str:
    """Converts an API namespace to the class name used by the OSS generator."""
    return "".join(word.capitalize() for word in namespace.split("_")) + "Client"


def utility_imports(methods: str, namespaced: bool = False) -> List[str]:
    """Returns client utility imports referenced by rendered methods."""
    imports = [name for name in UTILITY_NAMES if name in methods]
    if namespaced:
        imports.append("NamespacedClient")
    return sorted(imports)


def render_methods(module: Any) -> str:
    """Renders all methods with the existing OSS API Jinja templates."""
    module.sort()
    return "".join(api.to_python() for api in module_apis(module))


def render_template(
    name: str, config: ClientConfig = AOS_CONFIG, **context: Any
) -> str:
    """Renders an AWS package template using the codegen package environment."""
    template = AWS_TEMPLATE_ENV.get_template(f"aos/{name}")
    return (
        template.render(
            header=generated_header(config),
            service_name=config.label,
            **context,
        )
        + "\n"
    )


def write_file(root: Path, relative_path: Path, content: str) -> None:
    """Writes a generated file below an output root."""
    output = root / relative_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def split_modules(
    modules: Mapping[str, Any],
) -> Tuple[Any, List[Tuple[str, Any]], List[Tuple[str, Any]]]:
    """Splits root, core namespace, and plugin modules."""
    if "__init__" not in modules:
        raise ValueError("AOS spec does not contain root client operations")
    root_module = modules["__init__"]
    core = sorted(
        (
            (namespace, module)
            for namespace, module in modules.items()
            if namespace != "__init__" and not module.is_plugin
        ),
        key=lambda item: item[0],
    )
    plugins = sorted(
        (
            (namespace, module)
            for namespace, module in modules.items()
            if namespace != "__init__" and module.is_plugin
        ),
        key=lambda item: item[0],
    )
    return root_module, core, plugins


def render_async_tree(
    output_root: Path,
    modules: Mapping[str, Any],
    config: ClientConfig = AOS_CONFIG,
) -> Path:
    """Generates one complete asynchronous AWS client package."""
    async_root = output_root / config.async_output
    sync_root = output_root / config.sync_output
    shutil.rmtree(async_root, ignore_errors=True)
    shutil.rmtree(sync_root, ignore_errors=True)

    root_module, core_modules, plugin_modules = split_modules(modules)
    root_methods = render_methods(root_module)

    for namespace, module in core_modules:
        methods = render_methods(module)
        write_file(
            output_root,
            config.async_output / "client" / f"{namespace}.py",
            render_template(
                "module",
                config=config,
                class_name=class_name(namespace),
                methods=methods,
                needs_warnings="warnings." in methods,
                utility_imports=utility_imports(methods, namespaced=True),
            ),
        )

    for namespace, module in plugin_modules:
        methods = render_methods(module)
        write_file(
            output_root,
            config.async_output / "plugins" / f"{namespace}.py",
            render_template(
                "module",
                config=config,
                class_name=class_name(namespace),
                methods=methods,
                needs_warnings="warnings." in methods,
                utility_imports=utility_imports(methods, namespaced=True),
            ),
        )

    write_file(
        output_root,
        config.async_output / "client" / "plugins.py",
        render_template(
            "plugins_client",
            config=config,
            plugins=[
                {
                    "namespace": namespace,
                    "class_name": class_name(namespace),
                }
                for namespace, _ in plugin_modules
            ],
        ),
    )
    write_file(
        output_root,
        config.async_output / "client" / "__init__.py",
        render_template(
            "root_client",
            config=config,
            class_name=config.async_class_name,
            core_clients=[
                {
                    "namespace": namespace,
                    "class_name": class_name(namespace),
                }
                for namespace, _ in core_modules
            ],
            methods=root_methods,
            utility_imports=utility_imports(root_methods),
        ),
    )
    write_file(
        output_root,
        config.async_output / "plugins" / "__init__.py",
        render_template(
            "package_init",
            config=config,
            imports=[
                {
                    "module": namespace,
                    "name": class_name(namespace),
                }
                for namespace, _ in plugin_modules
            ],
        ),
    )
    write_file(
        output_root,
        config.async_output / "__init__.py",
        render_template(
            "package_init",
            config=config,
            imports=[{"module": "client", "name": config.async_class_name}],
        ),
    )
    return async_root


def unasync_tree(
    output_root: Path,
    async_root: Path,
    config: ClientConfig = AOS_CONFIG,
) -> Path:
    """Derives the synchronous AWS client package from the async package."""
    sync_root = output_root / config.sync_output
    rule = unasync.Rule(
        fromdir=f"/{config.async_output.as_posix()}/",
        todir=f"/{config.sync_output.as_posix()}/",
        additional_replacements={
            config.async_class_name: config.sync_class_name,
            "AsyncTransport": "Transport",
        },
    )
    unasync.unasync_files(
        [str(path) for path in async_root.rglob("*.py")],
        [rule],
    )
    for path in list(async_root.rglob("*.py")) + list(sync_root.rglob("*.py")):
        isort.file(path, quiet=True)
    oss_generator.blacken(async_root)
    oss_generator.blacken(sync_root)
    return sync_root


def generate_client_tree(
    output_root: Path,
    modules: Mapping[str, Any],
    config: ClientConfig = AOS_CONFIG,
) -> None:
    """Generates complete async and sync AWS client trees."""
    async_root = render_async_tree(output_root, modules, config)
    unasync_tree(output_root, async_root, config)


def compare_directories(expected: Path, actual: Path) -> List[str]:
    """Returns missing, extra, and changed files between generated trees."""
    if not actual.exists():
        return [f"missing directory: {actual}"]
    differences: List[str] = []
    comparison = filecmp.dircmp(expected, actual)
    differences.extend(str(actual / name) for name in comparison.left_only)
    differences.extend(str(actual / name) for name in comparison.right_only)
    differences.extend(str(actual / name) for name in comparison.diff_files)
    for directory in comparison.common_dirs:
        differences.extend(
            compare_directories(expected / directory, actual / directory)
        )
    return differences


def check_generated_tree(
    modules: Mapping[str, Any],
    config: ClientConfig = AOS_CONFIG,
) -> None:
    """Fails when checked-in clients differ from fresh generation."""
    with tempfile.TemporaryDirectory(
        prefix=f"opensearch-py-{config.label.lower()}-codegen-"
    ) as temp:
        temporary_root = Path(temp)
        generate_client_tree(temporary_root, modules, config)
        differences = []
        for relative in (config.async_output, config.sync_output):
            differences.extend(
                compare_directories(
                    temporary_root / relative,
                    CODE_ROOT / relative,
                )
            )
        if differences:
            details = "\n".join(f"- {difference}" for difference in differences)
            raise SystemExit(f"Generated {config.label} client is stale:\n{details}")


def dump_spec(document: Mapping[str, Any], output: Path) -> None:
    """Writes the merged and distribution-filtered AOS OpenAPI document."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(
            document,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        ),
        encoding="utf-8",
    )


def run_generation(config: ClientConfig) -> None:
    """Generates one data-plane client from the bundled spec and Overlay."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    document = build_distribution_spec(
        API_SPEC_PATH,
        config.overlay_path,
        config.distribution,
    )
    dump_spec(document, config.merged_spec_path)
    validate_parser_input(document)
    modules = parse_modules(document)
    validate_modules(document, modules, config)

    if args.check:
        check_generated_tree(modules, config)
        print(f"Generated {config.label} client is up to date.")
    else:
        generate_client_tree(CODE_ROOT, modules, config)
        print(
            f"Generated {config.label} client from {len(document['paths'])} paths and "
            f"{len(operation_names(modules))} methods."
        )


def main() -> None:
    """Generates the AOS data-plane client from bundled inputs."""
    run_generation(AOS_CONFIG)


if __name__ == "__main__":
    main()
