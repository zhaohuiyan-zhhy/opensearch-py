# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

from copy import deepcopy

import pytest
import yaml

from aws_client_codegen.api_spec import (
    apply_overlay,
    filter_distribution,
    validate_local_references,
)
from aws_client_codegen.api_spec.overlay import DROP, remove_empty_paths
from aws_client_codegen.generate_aos_api import (
    API_SPEC_PATH,
    OVERLAY_PATH,
    module_apis,
    operation_names,
    parse_modules,
    validate_parser_input,
)


def test_aos_generator_uses_bundled_inputs() -> None:
    """Generation does not require callers to locate spec files."""
    assert API_SPEC_PATH.is_file()
    assert OVERLAY_PATH.is_file()
    assert API_SPEC_PATH.parent == OVERLAY_PATH.parent.parent

    overlay = yaml.safe_load(OVERLAY_PATH.read_text(encoding="utf-8"))
    assert overlay["extends"] == "../opensearch-openapi.yaml"


def test_overlay_update_is_deep_merged() -> None:
    """Overlay updates preserve existing sibling keys."""
    document = {"paths": {"/_existing": {"get": {"description": "existing"}}}}
    overlay = {
        "overlay": "1.0.0",
        "actions": [
            {
                "target": "$.paths",
                "update": {
                    "/_new": {
                        "get": {
                            "x-distributions": ["amazon-managed"],
                            "description": "new",
                        }
                    }
                },
            }
        ],
    }

    result = apply_overlay(deepcopy(document), overlay)

    assert result["paths"]["/_existing"]["get"]["description"] == "existing"
    assert result["paths"]["/_new"]["get"]["description"] == "new"


def test_distribution_filter_supports_include_and_exclude_annotations() -> None:
    """Both current and legacy distribution annotations are enforced."""
    document = {
        "paths": {
            "/_oss": {"get": {"description": "all"}},
            "/_aos": {
                "get": {
                    "x-distributions": ["amazon-managed"],
                    "description": "managed",
                }
            },
            "/_not-aoss": {
                "get": {
                    "x-distributions-excluded": ["amazon-serverless"],
                    "description": "not serverless",
                }
            },
        }
    }

    managed = filter_distribution(deepcopy(document), "amazon-managed")
    serverless = filter_distribution(deepcopy(document), "amazon-serverless")

    assert managed is not DROP
    remove_empty_paths(managed)
    assert set(managed["paths"]) == {"/_oss", "/_aos", "/_not-aoss"}
    assert serverless is not DROP
    remove_empty_paths(serverless)
    assert set(serverless["paths"]) == {"/_oss"}


def test_dangling_local_reference_fails_validation() -> None:
    """A merged spec with a dangling local reference is rejected."""
    document = {
        "openapi": "3.1.0",
        "paths": {
            "/_test": {
                "get": {
                    "responses": {"200": {"$ref": "#/components/responses/missing"}}
                }
            }
        },
        "components": {"responses": {}},
    }

    with pytest.raises(KeyError, match="missing"):
        validate_local_references(document)


def test_merged_spec_uses_the_unmodified_oss_method_template() -> None:
    """A local merged spec is parsed and rendered by the OSS generator."""
    document = {
        "openapi": "3.1.0",
        "paths": {
            "/_test/{name}": {
                "get": {
                    "operationId": "sample.get.0",
                    "x-operation-group": "sample.get",
                    "description": "Gets a sample.",
                    "parameters": [
                        {"$ref": "#/components/parameters/sample.get___path.name"}
                    ],
                    "requestBody": {
                        "$ref": "#/components/requestBodies/sample.get",
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
        "components": {
            "parameters": {
                "sample.get___path.name": {
                    "name": "name",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            },
            "requestBodies": {
                "sample.get": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "description": "Selects the source.",
                            }
                        }
                    },
                }
            },
            "schemas": {},
        },
    }

    modules = parse_modules(document)
    api = module_apis(modules["sample"])[0]
    rendered = api.to_python()

    assert operation_names(modules) == ["sample.get"]
    assert api.body == {"required": False, "description": "Selects the source."}
    assert "body: Any=None" in rendered
    assert 'perform_request("GET"' in rendered
    assert "body=body" in rendered


def test_inline_request_body_fails_instead_of_being_silently_ignored() -> None:
    """The unchanged OSS parser limitation is made explicit for AOS inputs."""
    document = {
        "paths": {
            "/_test": {
                "post": {
                    "x-operation-group": "sample.create",
                    "requestBody": {
                        "content": {"application/json": {"schema": {"type": "object"}}}
                    },
                }
            }
        }
    }

    with pytest.raises(ValueError, match="requires a referenced requestBody"):
        validate_parser_input(document)


def test_ism_namespace_bypasses_the_oss_handwritten_client_skip() -> None:
    """AOS generates ISM from its spec because it has no handwritten fallback."""
    document = {
        "openapi": "3.1.0",
        "paths": {
            "/_plugins/_ism/policies": {
                "get": {
                    "operationId": "ism.get_policies.0",
                    "x-operation-group": "ism.get_policies",
                    "description": "Gets policies.",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
        "components": {
            "parameters": {},
            "requestBodies": {},
            "schemas": {},
        },
    }

    modules = parse_modules(document)

    assert operation_names(modules) == ["ism.get_policies"]
    assert modules["ism"].is_plugin is True
