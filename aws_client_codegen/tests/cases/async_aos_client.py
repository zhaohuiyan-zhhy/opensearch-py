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

from opensearchpy import AsyncAOSOpenSearch
from test_opensearchpy.test_async.test_client import DummyTransport

pytestmark = pytest.mark.asyncio


class TestAsyncAOSOpenSearch:
    def setup_method(self, method: Any) -> None:
        """Creates the generated async AOS client."""
        self.client: Any = AsyncAOSOpenSearch(transport_class=DummyTransport)

    async def test_generated_aos_operation(self) -> None:
        """The async client sends an Overlay-defined request."""
        await self.client.ultrawarm.migrate_to_cold(index="logs-2026")

        assert self.client.transport.calls[
            ("POST", "/_ultrawarm/migration/logs-2026/_cold")
        ] == [({}, {}, None)]

    async def test_generated_update_migration_operation(self) -> None:
        """The async AOS client sends update configuration."""
        body = {"migration_type": "WARM_TO_COLD"}

        await self.client.ultrawarm.update_migration(
            index="logs-2026",
            body=body,
        )

        assert self.client.transport.calls[
            ("PUT", "/_ultrawarm/migration/logs-2026")
        ] == [({}, {}, body)]

    async def test_generated_base_spec_operation(self) -> None:
        """The async AOS client contains base-spec methods without inheritance."""
        await self.client.count(index="logs-2026")

        assert self.client.transport.calls[("POST", "/logs-2026/_count")] == [
            ({}, {}, None)
        ]
