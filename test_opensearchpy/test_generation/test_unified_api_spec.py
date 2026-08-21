# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

"""Test discovery hook for unified AWS code-generation tests."""

from aws_client_codegen.tests.cases.unified_api_spec import (
    test_bundled_unified_spec_generates_complete_union,
    test_unified_spec_applies_updates_and_ignores_removals,
)

__all__ = [
    "test_bundled_unified_spec_generates_complete_union",
    "test_unified_spec_applies_updates_and_ignores_removals",
]
