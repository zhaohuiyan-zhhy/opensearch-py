# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

"""AOS OpenAPI Overlay support used by the client generator."""

from .overlay import (
    apply_overlay,
    build_distribution_spec,
    filter_distribution,
    validate_local_references,
)

__all__ = [
    "apply_overlay",
    "build_distribution_spec",
    "filter_distribution",
    "validate_local_references",
]
