# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

from pathlib import Path
from typing import Any, Dict

import yaml

from aws_client_codegen.api_spec import build_unified_spec
from aws_client_codegen.generate_aos_api import AOS_CONFIG, API_SPEC_PATH
from aws_client_codegen.generate_aoss_api import AOSS_CONFIG
from aws_client_codegen.generate_api import parse_modules, validate_modules


def write_yaml(path: Path, document: Dict[str, Any]) -> None:
    """Writes a test YAML document."""
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def test_unified_spec_applies_updates_and_ignores_removals(tmp_path: Path) -> None:
    """The additive merge has the same ordered semantics as the Java generator."""
    base = tmp_path / "spec.yaml"
    aos_overlay = tmp_path / "aos.overlay.yaml"
    aoss_overlay = tmp_path / "aoss.overlay.yaml"
    write_yaml(
        base,
        {
            "openapi": "3.1.0",
            "paths": {
                "/common": {
                    "get": {
                        "x-operation-group": "common",
                        "description": "common",
                    }
                }
            },
            "components": {"schemas": {"Shared": {"properties": {}}}},
        },
    )
    write_yaml(
        aos_overlay,
        {
            "overlay": "1.0.0",
            "actions": [
                {
                    "target": "$.paths",
                    "update": {
                        "/aos": {
                            "post": {
                                "x-operation-group": "aos",
                                "x-distributions": ["amazon-managed"],
                            }
                        }
                    },
                }
            ],
        },
    )
    write_yaml(
        aoss_overlay,
        {
            "overlay": "1.0.0",
            "actions": [
                {"target": "$.paths['/common']", "remove": True},
                {
                    "target": "$.components.schemas['Shared'].properties",
                    "update": {
                        "serverless": {
                            "type": "string",
                            "x-distributions": ["amazon-serverless"],
                        }
                    },
                },
            ],
        },
    )

    document = build_unified_spec(base, aos_overlay, aoss_overlay)

    assert "/common" in document["paths"]
    assert "/aos" in document["paths"]
    assert "serverless" in document["components"]["schemas"]["Shared"]["properties"]


def test_bundled_unified_spec_generates_complete_union() -> None:
    """The real inputs expose base, AOS, and AOSS operations in one client."""
    document = build_unified_spec(
        API_SPEC_PATH,
        AOS_CONFIG.overlay_path,
        AOSS_CONFIG.overlay_path,
    )
    modules = parse_modules(document)

    validate_modules(document, modules)
    assert "ultrawarm" in modules
    assert "/_cat/health" in document["paths"]
    assert (
        document["paths"]["/_snapshot/{repository}/{snapshot}"]["get"]["requestBody"][
            "$ref"
        ]
        == "#/components/requestBodies/aoss.snapshot.get"
    )
