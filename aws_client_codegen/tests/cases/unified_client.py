# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

from typing import Any
from unittest import TestCase

from opensearchpy import OpenSearch
from test_opensearchpy.test_cases import DummyTransport


class TestUnifiedOpenSearch(TestCase):
    def setUp(self) -> None:
        """Creates the standard client with a recording transport."""
        self.client: Any = OpenSearch(transport_class=DummyTransport)

    def test_aos_overlay_operation_is_on_standard_client(self) -> None:
        """AOS additions are generated into the standard client."""
        self.client.ultrawarm.migrate_to_warm(index="logs")

        assert self.client.transport.calls[
            ("POST", "/_ultrawarm/migration/logs/_warm")
        ] == [({}, {}, None)]

    def test_aoss_overlay_update_is_on_standard_client(self) -> None:
        """AOSS request-body updates are generated into the standard client."""
        body = {"sourceCollectionId": "abc123"}

        self.client.snapshot.get(repository="repo", snapshot="snap", body=body)

        assert self.client.transport.calls[("GET", "/_snapshot/repo/snap")] == [
            ({}, {}, body)
        ]

    def test_aos_update_migration_is_on_standard_client(self) -> None:
        """The unified client includes the Java-aligned update endpoint."""
        body = {"migration_type": "WARM_TO_COLD"}

        self.client.ultrawarm.update_migration(index="logs", body=body)

        assert self.client.transport.calls[("PUT", "/_ultrawarm/migration/logs")] == [
            ({}, {}, body)
        ]
