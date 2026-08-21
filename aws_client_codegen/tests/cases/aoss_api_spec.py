# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

from typing import Any, Dict

import yaml

from aws_client_codegen.api_spec import build_distribution_spec
from aws_client_codegen.generate_aos_api import (
    API_SPEC_PATH,
    parse_modules,
    validate_modules,
)
from aws_client_codegen.generate_aoss_api import AOSS_CONFIG


def build_aoss_spec() -> Dict[str, Any]:
    """Builds the checked-in AOSS spec inputs."""
    return build_distribution_spec(
        API_SPEC_PATH,
        AOSS_CONFIG.overlay_path,
        AOSS_CONFIG.distribution,
    )


def test_aoss_generator_uses_bundled_inputs() -> None:
    """Generation requires no caller-supplied spec or Overlay paths."""
    assert API_SPEC_PATH.is_file()
    assert AOSS_CONFIG.overlay_path.is_file()
    assert API_SPEC_PATH.parent == AOSS_CONFIG.overlay_path.parent.parent

    overlay = yaml.safe_load(AOSS_CONFIG.overlay_path.read_text(encoding="utf-8"))
    assert overlay["extends"] == "../opensearch-openapi.yaml"


def test_aoss_surface_is_narrowed_by_distribution_and_overlay() -> None:
    """Unsupported root, CAT, cluster-management, node, and UltraWarm APIs vanish."""
    document = build_aoss_spec()
    paths = document["paths"]

    assert "/" not in paths
    assert "/_cat/health" not in paths
    assert "/_cluster/health" not in paths
    assert not any(path.startswith("/_nodes") for path in paths)
    assert not any(path.startswith("/_ultrawarm") for path in paths)

    assert "/_cat/aliases" in paths
    assert "/_cat/indices" in paths
    assert "/_cat/templates" in paths
    assert "/{index}/_search" in paths


def test_aoss_snapshot_extensions_are_merged() -> None:
    """AOSS-specific snapshot request fields survive distribution filtering."""
    document = build_aoss_spec()
    request_bodies = document["components"]["requestBodies"]

    restore = request_bodies["snapshot.restore"]["content"]["application/json"][
        "schema"
    ]["properties"]
    assert restore["sourceCollectionId"]["pattern"] == "^[a-z0-9]{3,40}$"
    assert restore["allow_regex"]["default"] is False

    snapshot_get = document["paths"]["/_snapshot/{repository}/{snapshot}"]["get"]
    assert snapshot_get["requestBody"] == {
        "$ref": "#/components/requestBodies/aoss.snapshot.get"
    }
    preflight = request_bodies["aoss.snapshot.get"]["content"]["application/json"][
        "schema"
    ]["properties"]
    assert "sourceCollectionId" in preflight

    repository = request_bodies["snapshot.create_repository"]["content"][
        "application/json"
    ]["schema"]["properties"]["crypto_settings"]
    assert repository["required"] == ["kms_key_arn"]


def test_aoss_schema_compatibility_updates_are_merged() -> None:
    """AOSS response requirements and field-caps request shape match the Overlay."""
    document = build_aoss_spec()
    components = document["components"]

    resolve_item = components["schemas"]["indices.resolve_index___ResolveIndexItem"]
    assert resolve_item["required"] == ["name"]
    resolve_response = components["responses"]["indices.resolve_index___200"][
        "content"
    ]["application/json"]["schema"]
    assert resolve_response["required"] == ["aliases", "indices"]

    field_caps = components["requestBodies"]["field_caps"]["content"][
        "application/json"
    ]["schema"]["properties"]
    assert "fields" not in field_caps
    assert "field_caps___query.fields" in components["parameters"]


def test_every_filtered_aoss_operation_is_generated() -> None:
    """The parser generates exactly the operation groups in the filtered spec."""
    document = build_aoss_spec()
    modules = parse_modules(document)

    validate_modules(document, modules, AOSS_CONFIG)
