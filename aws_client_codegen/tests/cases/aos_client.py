# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

from inspect import Parameter, signature
from typing import Any
from unittest import TestCase

from opensearchpy import AOSOpenSearch
from opensearchpy.client import OpenSearch
from test_opensearchpy.test_cases import DummyTransport


class TestAOSOpenSearch(TestCase):
    def setUp(self) -> None:
        """Creates the generated AOS client with a recording transport."""
        self.client: Any = AOSOpenSearch(transport_class=DummyTransport)  # type: ignore

    def assert_url_called(self, method: str, url: str) -> Any:
        """Returns calls recorded for a method and URL."""
        return self.client.transport.calls[(method, url)]

    def test_is_independent_from_oss_client_facade(self) -> None:
        """The complete AOS client does not inherit the OSS facade."""
        assert not isinstance(self.client, OpenSearch)

    def test_generated_aos_operation(self) -> None:
        """An Overlay operation is rendered through the normal method template."""
        self.client.ultrawarm.migrate_to_warm(
            index="logs-2026", cluster_manager_timeout="1m"
        )

        assert self.assert_url_called(
            "POST", "/_ultrawarm/migration/logs-2026/_warm"
        ) == [({"cluster_manager_timeout": b"1m"}, {}, None)]

    def test_generated_update_migration_operation(self) -> None:
        """The Java-aligned update endpoint accepts optional configuration."""
        body = {"migration_type": "WARM_TO_COLD"}

        self.client.ultrawarm.update_migration(index="logs-2026", body=body)

        assert self.assert_url_called("PUT", "/_ultrawarm/migration/logs-2026") == [
            ({}, {}, body)
        ]

    def test_generated_oss_operation(self) -> None:
        """An unchanged base-spec operation is generated into the AOS package."""
        self.client.search(index="logs-2026", body={"query": {"match_all": {}}})

        assert self.assert_url_called("POST", "/logs-2026/_search") == [
            ({}, {}, {"query": {"match_all": {}}})
        ]

    def test_distribution_filter_changes_method_shape(self) -> None:
        """Removing the no-index path makes the remaining index path required."""
        index = signature(self.client.indices.clear_cache).parameters["index"]

        assert index.default is Parameter.empty

    def test_generated_plugin_operation(self) -> None:
        """Plugin namespaces are generated and wired into the plugins facade."""
        self.client.plugins.sql.query(body={"query": "SELECT 1"})

        assert self.assert_url_called("POST", "/_plugins/_sql") == [
            ({}, {}, {"query": "SELECT 1"})
        ]

    def test_ism_is_generated_instead_of_using_oss_handwritten_fallback(self) -> None:
        """The independent AOS package includes the spec-defined ISM namespace."""
        self.client.plugins.ism.get_policies()

        assert self.assert_url_called("GET", "/_plugins/_ism/policies") == [
            ({}, {}, None)
        ]
