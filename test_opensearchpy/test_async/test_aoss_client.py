# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

from typing import Any

import pytest

from opensearchpy import AsyncAOSSOpenSearch

from .test_client import DummyTransport

pytestmark = pytest.mark.asyncio


class TestAsyncAOSSOpenSearch:
    def setup_method(self, method: Any) -> None:
        """Creates the generated asynchronous AOSS client."""
        self.client: Any = AsyncAOSSOpenSearch(transport_class=DummyTransport)

    async def test_generated_base_spec_operation(self) -> None:
        """The async package contains retained base-spec operations."""
        await self.client.count(index="logs-2026")

        assert self.client.transport.calls[("POST", "/logs-2026/_count")] == [
            ({}, {}, None)
        ]

    async def test_generated_aoss_snapshot_operation(self) -> None:
        """The async package accepts and sends the AOSS preflight body."""
        body = {"sourceCollectionId": "abc123"}

        await self.client.snapshot.get(
            repository="repo",
            snapshot="snap",
            body=body,
        )

        assert self.client.transport.calls[("GET", "/_snapshot/repo/snap")] == [
            ({}, {}, body)
        ]
