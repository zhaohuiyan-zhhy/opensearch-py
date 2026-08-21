# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

import copy
from pathlib import Path
from typing import Any, Dict, List

import yaml

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
DROP = object()


def parse_target(target: str) -> List[str]:
    """Parses the exact JSONPath targets used by the checked-in overlays."""
    if not target.startswith("$"):
        raise ValueError(f"Overlay target must start with '$': {target}")

    keys = []
    position = 1
    while position < len(target):
        if target[position] == ".":
            end = position + 1
            while end < len(target) and target[end] not in ".[":
                end += 1
            if end == position + 1:
                raise ValueError(f"Empty target segment: {target}")
            keys.append(target[position + 1 : end])
            position = end
            continue

        if target[position : position + 2] == "['":
            end = target.find("']", position + 2)
            if end == -1:
                raise ValueError(f"Unterminated target segment: {target}")
            keys.append(target[position + 2 : end])
            position = end + 2
            continue

        raise ValueError(
            f"Unsupported JSONPath syntax at position {position}: {target}"
        )

    return keys


def get_node(document: Dict[str, Any], keys: List[str]) -> Any:
    """Returns an exact target node and fails when the base spec has drifted."""
    node: Any = document
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"Overlay target does not exist: {'.'.join(keys)}")
        node = node[key]
    return node


def deep_merge(target: Dict[str, Any], update: Dict[str, Any]) -> None:
    """Applies the Overlay update mapping semantics needed by these overlays."""
    for key, value in update.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            deep_merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def apply_overlay(document: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Applies exact-target update/remove actions from an Overlay 1.0 document."""
    if overlay.get("overlay") != "1.0.0":
        raise ValueError("Expected an OpenAPI Overlay 1.0.0 document")

    actions = overlay.get("actions")
    if not isinstance(actions, list):
        raise ValueError("Overlay must contain an actions list")

    for index, action in enumerate(actions, start=1):
        target = action.get("target")
        if not isinstance(target, str):
            raise ValueError(f"Action {index} has no target")
        keys = parse_target(target)

        if "update" in action:
            node = get_node(document, keys)
            update = action["update"]
            if not isinstance(node, dict) or not isinstance(update, dict):
                raise ValueError(f"Action {index} update requires mapping values")
            deep_merge(node, update)
        elif action.get("remove") is True:
            if not keys:
                raise ValueError("The document root cannot be removed")
            parent = get_node(document, keys[:-1])
            if not isinstance(parent, dict) or keys[-1] not in parent:
                raise KeyError(f"Overlay remove target does not exist: {target}")
            del parent[keys[-1]]
        else:
            raise ValueError(f"Action {index} must contain update or remove")

    return document


def apply_additive_overlay(
    document: Dict[str, Any], overlay: Dict[str, Any]
) -> Dict[str, Any]:
    """Applies update actions while retaining targets named by remove actions."""
    actions = overlay.get("actions")
    if not isinstance(actions, list):
        raise ValueError("Overlay must contain an actions list")

    additive_overlay = copy.deepcopy(overlay)
    additive_actions = []
    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            raise ValueError(f"Action {index} must be a mapping")
        if isinstance(action.get("update"), dict):
            additive_actions.append(copy.deepcopy(action))
        elif action.get("remove") is not True:
            raise ValueError(f"Action {index} must contain update or remove")
    additive_overlay["actions"] = additive_actions
    return apply_overlay(document, additive_overlay)


def filter_distribution(value: Any, distribution: str) -> Any:
    """Recursively removes nodes excluded from the selected distribution."""
    if isinstance(value, dict):
        included = value.get("x-distributions")
        excluded = value.get("x-distributions-excluded")
        if isinstance(included, list) and distribution not in included:
            return DROP
        if isinstance(excluded, list) and distribution in excluded:
            return DROP

        filtered_mapping = {}
        for key, child in value.items():
            filtered_child = filter_distribution(child, distribution)
            if filtered_child is not DROP:
                filtered_mapping[key] = filtered_child
        return filtered_mapping

    if isinstance(value, list):
        filtered_list = []
        for child in value:
            filtered_child = filter_distribution(child, distribution)
            if filtered_child is not DROP:
                filtered_list.append(filtered_child)
        return filtered_list

    return value


def remove_empty_paths(document: Dict[str, Any]) -> None:
    """Removes path items with no operation left after distribution filtering."""
    paths = document.get("paths", {})
    document["paths"] = {
        path: path_item
        for path, path_item in paths.items()
        if any(method in HTTP_METHODS for method in path_item)
    }


def resolve_pointer(document: Dict[str, Any], reference: str) -> None:
    """Resolves one local JSON pointer or raises for a dangling reference."""
    node: Any = document
    for raw_key in reference[2:].split("/"):
        key = raw_key.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or key not in node:
            raise KeyError(reference)
        node = node[key]


def validate_local_references(document: Dict[str, Any]) -> int:
    """Validates every local $ref and returns the number of unique references."""
    references = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/"):
                references.add(reference)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)
    for reference in sorted(references):
        resolve_pointer(document, reference)
    return len(references)


def load_yaml(path: Path) -> Dict[str, Any]:
    """Loads and validates a mapping-valued YAML document."""
    with path.open(encoding="utf-8") as yaml_file:
        data = yaml.safe_load(yaml_file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return data


def build_distribution_spec(
    base_spec_path: Path, overlay_path: Path, distribution: str
) -> Dict[str, Any]:
    """Builds and validates one AOS distribution-specific OpenAPI document."""
    document = load_yaml(base_spec_path)
    overlay = load_yaml(overlay_path)
    if "openapi" not in document or not isinstance(document.get("paths"), dict):
        raise ValueError(f"Not an OpenAPI document: {base_spec_path}")

    apply_overlay(document, overlay)
    filtered_document = filter_distribution(document, distribution)
    if filtered_document is DROP or not isinstance(filtered_document, dict):
        raise ValueError(f"The root document excludes {distribution}")

    remove_empty_paths(filtered_document)
    validate_local_references(filtered_document)
    return filtered_document


def build_unified_spec(
    base_spec_path: Path, aos_overlay_path: Path, aoss_overlay_path: Path
) -> Dict[str, Any]:
    """Builds the additive OSS, AOS, and AOSS OpenAPI union."""
    document = load_yaml(base_spec_path)
    if "openapi" not in document or not isinstance(document.get("paths"), dict):
        raise ValueError(f"Not an OpenAPI document: {base_spec_path}")

    apply_additive_overlay(document, load_yaml(aos_overlay_path))
    apply_additive_overlay(document, load_yaml(aoss_overlay_path))
    validate_local_references(document)
    return document
