# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

"""Test discovery hook for the centralized AOSS code-generation tests."""

from aws_client_codegen.tests.cases.aoss_api_spec import (
    test_aoss_generator_uses_bundled_inputs,
    test_aoss_schema_compatibility_updates_are_merged,
    test_aoss_snapshot_extensions_are_merged,
    test_aoss_surface_is_narrowed_by_distribution_and_overlay,
    test_every_filtered_aoss_operation_is_generated,
)

__all__ = [
    "test_aoss_generator_uses_bundled_inputs",
    "test_aoss_schema_compatibility_updates_are_merged",
    "test_aoss_snapshot_extensions_are_merged",
    "test_aoss_surface_is_narrowed_by_distribution_and_overlay",
    "test_every_filtered_aoss_operation_is_generated",
]
