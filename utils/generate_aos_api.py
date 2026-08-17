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
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple, cast
from unittest.mock import patch

import isort
import requests
import unasync
import yaml

from utils import generate_api as oss_generator
from utils.aos_api_spec import build_distribution_spec

CODE_ROOT = Path(__file__).absolute().parent.parent
DISTRIBUTION = "amazon-managed"
AOS_SPEC_ROOT = CODE_ROOT / "utils" / "aos_api_spec"
API_SPEC_PATH = AOS_SPEC_ROOT / "opensearch-openapi.yaml"
OVERLAY_PATH = AOS_SPEC_ROOT / "overlays" / "amazon-managed.overlay.yaml"
MERGED_SPEC_PATH = CODE_ROOT / "build" / "aos-api-spec" / "opensearch-aos.yaml"
ASYNC_OUTPUT = Path("opensearchpy/_async/aos")
SYNC_OUTPUT = Path("opensearchpy/aos")
GENERATED_HEADER_PATH = CODE_ROOT / "utils" / "generated_file_headers.txt"
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


class LocalSpecResponse:
    """Minimal requests response used to feed a local spec to the OSS parser."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        self.text = yaml.safe_dump(
            document,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )


def generated_header() -> str:
    """Returns the license and AOS-specific generated-file warning."""
    warning = GENERATED_HEADER_PATH.read_text(encoding="utf-8").strip()
    warning = warning.replace(
        "`nox -rs generate`",
        "`nox -rs generate_aos`",
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


def validate_modules(document: Mapping[str, Any], modules: Mapping[str, Any]) -> None:
    """Checks that every filtered AOS operation group was generated."""
    expected_operations = set(spec_operation_names(document))
    operations = set(operation_names(modules))
    if operations != expected_operations:
        missing = sorted(expected_operations - operations)
        unexpected = sorted(operations - expected_operations)
        raise ValueError(
            "Generated AOS operation set does not match the filtered spec; "
            f"missing={missing}, unexpected={unexpected}"
        )

    required = {
        "ultrawarm.cancel_migration",
        "ultrawarm.get_migration_status",
        "ultrawarm.list_migration_status",
        "ultrawarm.migrate_to_cold",
        "ultrawarm.migrate_to_hot",
        "ultrawarm.migrate_to_warm",
    }
    missing = sorted(required - operations)
    if missing:
        raise ValueError(f"AOS Overlay operations were not generated: {missing}")
    if "ism" not in modules:
        raise ValueError("AOS spec operations were not generated: ism namespace")


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


def render_template(name: str, **context: Any) -> str:
    """Renders an AOS package template using the OSS Jinja environment."""
    template = oss_generator.jinja_env.get_template(f"aos/{name}")
    return cast(str, template.render(header=generated_header(), **context)) + "\n"


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


def render_async_tree(output_root: Path, modules: Mapping[str, Any]) -> Path:
    """Generates the complete asynchronous AOS client package."""
    async_root = output_root / ASYNC_OUTPUT
    sync_root = output_root / SYNC_OUTPUT
    shutil.rmtree(async_root, ignore_errors=True)
    shutil.rmtree(sync_root, ignore_errors=True)

    root_module, core_modules, plugin_modules = split_modules(modules)
    root_methods = render_methods(root_module)

    for namespace, module in core_modules:
        methods = render_methods(module)
        write_file(
            output_root,
            ASYNC_OUTPUT / "client" / f"{namespace}.py",
            render_template(
                "module",
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
            ASYNC_OUTPUT / "plugins" / f"{namespace}.py",
            render_template(
                "module",
                class_name=class_name(namespace),
                methods=methods,
                needs_warnings="warnings." in methods,
                utility_imports=utility_imports(methods, namespaced=True),
            ),
        )

    write_file(
        output_root,
        ASYNC_OUTPUT / "client" / "plugins.py",
        render_template(
            "plugins_client",
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
        ASYNC_OUTPUT / "client" / "__init__.py",
        render_template(
            "root_client",
            class_name="AsyncAOSOpenSearch",
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
        ASYNC_OUTPUT / "plugins" / "__init__.py",
        render_template(
            "package_init",
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
        ASYNC_OUTPUT / "__init__.py",
        render_template(
            "package_init",
            imports=[{"module": "client", "name": "AsyncAOSOpenSearch"}],
        ),
    )
    return async_root


def unasync_tree(output_root: Path, async_root: Path) -> Path:
    """Derives the synchronous AOS client package from the async package."""
    sync_root = output_root / SYNC_OUTPUT
    rule = unasync.Rule(
        fromdir=f"/{ASYNC_OUTPUT.as_posix()}/",
        todir=f"/{SYNC_OUTPUT.as_posix()}/",
        additional_replacements={
            "AsyncAOSOpenSearch": "AOSOpenSearch",
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


def generate_client_tree(output_root: Path, modules: Mapping[str, Any]) -> None:
    """Generates the complete async and sync AOS client trees."""
    async_root = render_async_tree(output_root, modules)
    unasync_tree(output_root, async_root)


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


def check_generated_tree(modules: Mapping[str, Any]) -> None:
    """Fails when checked-in AOS clients differ from fresh generation."""
    with tempfile.TemporaryDirectory(prefix="opensearch-py-aos-codegen-") as temp:
        temporary_root = Path(temp)
        generate_client_tree(temporary_root, modules)
        differences = []
        for relative in (ASYNC_OUTPUT, SYNC_OUTPUT):
            differences.extend(
                compare_directories(
                    temporary_root / relative,
                    CODE_ROOT / relative,
                )
            )
        if differences:
            details = "\n".join(f"- {difference}" for difference in differences)
            raise SystemExit(f"Generated AOS client is stale:\n{details}")


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


def main() -> None:
    """Generates the AOS data-plane client from the bundled spec and Overlay."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    document = build_distribution_spec(API_SPEC_PATH, OVERLAY_PATH, DISTRIBUTION)
    dump_spec(document, MERGED_SPEC_PATH)
    validate_parser_input(document)
    modules = parse_modules(document)
    validate_modules(document, modules)

    if args.check:
        check_generated_tree(modules)
        print("Generated AOS client is up to date.")
    else:
        generate_client_tree(CODE_ROOT, modules)
        print(
            f"Generated AOS client from {len(document['paths'])} paths and "
            f"{len(operation_names(modules))} methods."
        )


if __name__ == "__main__":
    main()
