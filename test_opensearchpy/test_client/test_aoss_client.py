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

from opensearchpy import AOSOpenSearch, AOSSOpenSearch
from opensearchpy.client import OpenSearch
from test_opensearchpy.test_cases import DummyTransport


class TestAOSSOpenSearch(TestCase):
    def setUp(self) -> None:
        """Creates the generated AOSS client with a recording transport."""
        self.client: Any = AOSSOpenSearch(transport_class=DummyTransport)  # type: ignore

    def assert_url_called(self, method: str, url: str) -> Any:
        """Returns calls recorded for a method and URL."""
        return self.client.transport.calls[(method, url)]

    def test_is_an_independent_serverless_client(self) -> None:
        """AOSS does not inherit the OSS or AOS facade and omits excluded APIs."""
        assert not isinstance(self.client, OpenSearch)
        assert not isinstance(self.client, AOSOpenSearch)
        assert not hasattr(self.client, "ping")
        assert not hasattr(self.client, "info")
        assert not hasattr(self.client, "nodes")
        assert not hasattr(self.client, "ultrawarm")
        assert not hasattr(self.client.cat, "health")
        assert not hasattr(self.client.cluster, "health")

    def test_generated_base_spec_operations(self) -> None:
        """Retained base-spec search and CAT operations use their modeled paths."""
        self.client.search(index="logs-2026", body={"query": {"match_all": {}}})
        self.client.cat.aliases(name="logs")

        assert self.assert_url_called("POST", "/logs-2026/_search") == [
            ({}, {}, {"query": {"match_all": {}}})
        ]
        assert self.assert_url_called("GET", "/_cat/aliases/logs") == [({}, {}, None)]

    def test_snapshot_restore_sends_aoss_body_fields(self) -> None:
        """Cross-collection restore fields pass through the generated body."""
        body = {
            "sourceCollectionId": "abc123",
            "allow_regex": True,
            "rename_pattern": "logs-(.+)",
            "rename_replacement": "restored-$1",
        }

        self.client.snapshot.restore(
            repository="repo",
            snapshot="snap",
            body=body,
        )

        assert self.assert_url_called("POST", "/_snapshot/repo/snap/_restore") == [
            ({}, {}, body)
        ]

    def test_snapshot_get_sends_aoss_preflight_body(self) -> None:
        """The AOSS extension allows a body on snapshot GET."""
        body = {"sourceCollectionId": "abc123"}

        self.client.snapshot.get(repository="repo", snapshot="snap", body=body)

        assert self.assert_url_called("GET", "/_snapshot/repo/snap") == [({}, {}, body)]

    def test_snapshot_repository_sends_crypto_settings(self) -> None:
        """AOSS KMS repository configuration passes through unchanged."""
        body = {
            "type": "s3",
            "settings": {"bucket": "snapshots"},
            "crypto_settings": {
                "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/test"
            },
        }

        self.client.snapshot.create_repository(repository="repo", body=body)

        assert self.assert_url_called("PUT", "/_snapshot/repo") == [({}, {}, body)]

    def test_field_caps_keeps_fields_in_query_string(self) -> None:
        """The removed body property remains available as a query parameter."""
        body = {"index_filter": {"match_all": {}}}

        self.client.field_caps(index="logs-2026", fields=["title"], body=body)

        assert self.assert_url_called("POST", "/logs-2026/_field_caps") == [
            ({"fields": b"title"}, {}, body)
        ]
