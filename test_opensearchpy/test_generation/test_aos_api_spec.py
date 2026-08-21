# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

"""Test discovery hook for the centralized AOS code-generation tests."""

from aws_client_codegen.tests.cases.aos_api_spec import (
    test_aos_generator_uses_bundled_inputs,
    test_dangling_local_reference_fails_validation,
    test_distribution_filter_supports_include_and_exclude_annotations,
    test_inline_request_body_fails_instead_of_being_silently_ignored,
    test_ism_namespace_bypasses_the_oss_handwritten_client_skip,
    test_merged_spec_uses_the_unmodified_oss_method_template,
    test_overlay_update_is_deep_merged,
)

__all__ = [
    "test_aos_generator_uses_bundled_inputs",
    "test_dangling_local_reference_fails_validation",
    "test_distribution_filter_supports_include_and_exclude_annotations",
    "test_inline_request_body_fails_instead_of_being_silently_ignored",
    "test_ism_namespace_bypasses_the_oss_handwritten_client_skip",
    "test_merged_spec_uses_the_unmodified_oss_method_template",
    "test_overlay_update_is_deep_merged",
]
