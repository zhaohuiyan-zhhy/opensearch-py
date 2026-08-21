#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

from pathlib import Path

from aws_client_codegen.generate_aos_api import (
    AOS_SPEC_ROOT,
    CODE_ROOT,
    ClientConfig,
    run_generation,
)

AOSS_CONFIG = ClientConfig(
    label="AOSS",
    distribution="amazon-serverless",
    overlay_path=AOS_SPEC_ROOT / "overlays" / "amazon-serverless.overlay.yaml",
    merged_spec_path=CODE_ROOT / "build" / "aoss-api-spec" / "opensearch-aoss.yaml",
    async_output=Path("opensearchpy/_async/aoss"),
    sync_output=Path("opensearchpy/aoss"),
    async_class_name="AsyncAOSSOpenSearch",
    sync_class_name="AOSSOpenSearch",
    nox_session="generate_aoss",
    required_operations=(
        "snapshot.create_repository",
        "snapshot.get",
        "snapshot.restore",
    ),
    forbidden_operations=(
        "info",
        "ping",
        "cat.health",
        "cluster.health",
        "nodes.info",
        "ultrawarm.migrate_to_warm",
    ),
    required_namespaces=("ism",),
)


def main() -> None:
    """Generates the AOSS data-plane client from bundled inputs."""
    run_generation(AOSS_CONFIG)


if __name__ == "__main__":
    main()
