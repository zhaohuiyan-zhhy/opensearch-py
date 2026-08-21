#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

"""Generate the unified OSS, AOS, and AOSS Python client."""

import argparse
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, cast
from unittest.mock import patch

import isort
import requests

from aws_client_codegen.api_spec import build_unified_spec
from aws_client_codegen.generate_aos_api import (
    AOS_CONFIG,
    API_SPEC_PATH,
    CODE_ROOT,
    HTTP_METHODS,
    LocalSpecResponse,
    compare_directories,
    dump_spec,
    operation_names,
    validate_parser_input,
)
from aws_client_codegen.generate_aoss_api import AOSS_CONFIG
from utils import generate_api as oss_generator

UNIFIED_SPEC_PATH = CODE_ROOT / "build" / "aws-api-spec" / "opensearch-unified.yaml"
GENERATED_DIRECTORIES = (
    Path("opensearchpy/_async/client"),
    Path("opensearchpy/_async/plugins"),
    Path("opensearchpy/client"),
    Path("opensearchpy/plugins"),
)
REQUIRED_OPERATIONS = AOS_CONFIG.required_operations + AOSS_CONFIG.required_operations


def parse_modules(document: Mapping[str, Any]) -> Dict[str, Any]:
    """Parses the unified local specification with the standard OSS generator."""
    response = LocalSpecResponse(document)
    with patch.object(requests, "get", return_value=response):
        modules = oss_generator.read_modules()
    return cast(Dict[str, Any], modules)


def spec_operation_names(document: Mapping[str, Any]) -> List[str]:
    """Returns operations expected from the standard generator."""
    operations = set()
    for path_item in document.get("paths", {}).values():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_group = operation.get("x-operation-group")
            if not isinstance(operation_group, str):
                raise ValueError("Unified operation is missing x-operation-group")
            if operation_group.startswith("ism."):
                continue
            if operation_group == "nodes.hot_threads" and "deprecated" in operation:
                continue
            operations.add(operation_group)
    return sorted(operations)


def validate_modules(document: Mapping[str, Any], modules: Mapping[str, Any]) -> None:
    """Checks that the standard generator retained the complete API union."""
    expected = set(spec_operation_names(document))
    actual = set(operation_names(modules))
    if actual != expected:
        raise ValueError(
            "Generated unified operation set does not match the combined spec; "
            f"missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )

    missing = sorted(set(REQUIRED_OPERATIONS) - actual)
    if missing:
        raise ValueError(f"Unified overlay operations were not generated: {missing}")


def generate_client_tree(
    output_root: Path, document: Mapping[str, Any]
) -> Dict[str, Any]:
    """Generates the standard async and sync clients below an output root."""
    original_root = oss_generator.CODE_ROOT
    original_directory = Path.cwd()
    try:
        oss_generator.CODE_ROOT = output_root
        os.chdir(output_root)
        modules = parse_modules(document)
        validate_modules(document, modules)
        oss_generator.dump_modules(modules)
        oss_generator.dump_grpc_client()
        for relative in GENERATED_DIRECTORIES:
            for path in (output_root / relative).rglob("*.py"):
                isort.file(path, quiet=True)
        for relative in GENERATED_DIRECTORIES:
            oss_generator.blacken(output_root / relative)
        return modules
    finally:
        os.chdir(original_directory)
        oss_generator.CODE_ROOT = original_root


def prepare_temporary_tree(output_root: Path) -> None:
    """Copies hand-written client context needed by the in-place OSS generator."""
    shutil.copy2(CODE_ROOT / "setup.cfg", output_root / "setup.cfg")
    for relative in (
        Path("opensearchpy/__init__.py"),
        Path("opensearchpy/_async/__init__.py"),
    ):
        target = output_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CODE_ROOT / relative, target)
    for relative in GENERATED_DIRECTORIES:
        target = output_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(CODE_ROOT / relative, target)
    shutil.copytree(
        CODE_ROOT / "utils" / "templates",
        output_root / "utils" / "templates",
    )


def check_generated_tree(document: Mapping[str, Any]) -> None:
    """Fails when checked-in unified client files differ from fresh generation."""
    with tempfile.TemporaryDirectory(
        prefix="opensearch-py-unified-codegen-"
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        prepare_temporary_tree(temporary_root)
        generate_client_tree(temporary_root, document)

        differences = []
        for relative in GENERATED_DIRECTORIES:
            differences.extend(
                compare_directories(
                    temporary_root / relative,
                    CODE_ROOT / relative,
                )
            )
        if differences:
            details = "\n".join(f"- {difference}" for difference in differences)
            raise SystemExit(
                "Generated unified OSS/AOS/AOSS client is stale. "
                "Run `nox -rs generate`.\n"
                f"{details}"
            )


def run_generation(check: bool = False) -> None:
    """Builds the unified specification and generates or checks the client."""
    document = build_unified_spec(
        API_SPEC_PATH,
        AOS_CONFIG.overlay_path,
        AOSS_CONFIG.overlay_path,
    )
    dump_spec(document, UNIFIED_SPEC_PATH)
    validate_parser_input(document)

    if check:
        check_generated_tree(document)
        print("Generated unified OSS/AOS/AOSS client is up to date.")
        return

    modules = generate_client_tree(CODE_ROOT, document)
    print(
        "Generated unified OSS/AOS/AOSS client from "
        f"{len(document['paths'])} paths and {len(operation_names(modules))} methods."
    )


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    run_generation(check=args.check)


if __name__ == "__main__":
    main()
