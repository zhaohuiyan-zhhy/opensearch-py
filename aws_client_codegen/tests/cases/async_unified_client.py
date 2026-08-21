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

from opensearchpy import AsyncOpenSearch
from test_opensearchpy.test_async.test_client import DummyTransport

pytestmark = pytest.mark.asyncio


class TestAsyncUnifiedOpenSearch:
    def setup_method(self, method: Any) -> None:
        """Creates the standard asynchronous client."""
        self.client: Any = AsyncOpenSearch(transport_class=DummyTransport)

    async def test_aos_and_aoss_overlay_changes_are_on_standard_client(self) -> None:
        """Both overlays contribute to the asynchronous API union."""
        body = {"sourceCollectionId": "abc123"}

        await self.client.ultrawarm.migrate_to_cold(index="logs")
        await self.client.ultrawarm.update_migration(
            index="logs",
            body={"migration_type": "WARM_TO_COLD"},
        )
        await self.client.snapshot.get(
            repository="repo",
            snapshot="snap",
            body=body,
        )

        assert self.client.transport.calls[
            ("POST", "/_ultrawarm/migration/logs/_cold")
        ] == [({}, {}, None)]
        assert self.client.transport.calls[("PUT", "/_ultrawarm/migration/logs")] == [
            ({}, {}, {"migration_type": "WARM_TO_COLD"})
        ]
        assert self.client.transport.calls[("GET", "/_snapshot/repo/snap")] == [
            ({}, {}, body)
        ]
