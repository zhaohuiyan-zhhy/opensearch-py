# ------------------------------------------------------------------------------------------
# THIS CODE IS AUTOMATICALLY GENERATED AND MANUAL EDITS WILL BE LOST
#
# To contribute, kindly make modifications in the opensearch-py client generator
# or in the OpenSearch API specification, and run `nox -rs generate`. See DEVELOPER_GUIDE.md
# and https://github.com/opensearch-project/opensearch-api-specification for details.
# -----------------------------------------------------------------------------------------+


from typing import Any

from .utils import SKIP_IN_PATH, NamespacedClient, _make_path, query_params


class UltrawarmClient(NamespacedClient):
    @query_params()
    async def cancel_migration(
        self,
        *,
        index: Any,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Cancels an in-progress UltraWarm migration.


        :arg index: The name of the index to migrate.
        """
        if index in SKIP_IN_PATH:
            raise ValueError("Empty value passed for a required argument 'index'.")

        return await self.transport.perform_request(
            "POST",
            _make_path("_ultrawarm", "migration", "_cancel", index),
            params=params,
            headers=headers,
        )

    @query_params()
    async def get_migration_status(
        self,
        *,
        index: Any,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Returns migration status for an index.


        :arg index: The name of the index to migrate.
        """
        if index in SKIP_IN_PATH:
            raise ValueError("Empty value passed for a required argument 'index'.")

        return await self.transport.perform_request(
            "GET",
            _make_path("_ultrawarm", "migration", index, "_status"),
            params=params,
            headers=headers,
        )

    @query_params()
    async def list_migration_status(
        self,
        *,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Lists active UltraWarm migrations.

        """
        return await self.transport.perform_request(
            "GET", "/_ultrawarm/migration/_status", params=params, headers=headers
        )

    @query_params("cluster_manager_timeout")
    async def migrate_to_cold(
        self,
        *,
        index: Any,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Starts an asynchronous migration from UltraWarm to cold storage.


        :arg index: The name of the index to migrate.
        :arg cluster_manager_timeout: Time to wait for a response from
            the cluster manager node.
        """
        if index in SKIP_IN_PATH:
            raise ValueError("Empty value passed for a required argument 'index'.")

        return await self.transport.perform_request(
            "POST",
            _make_path("_ultrawarm", "migration", index, "_cold"),
            params=params,
            headers=headers,
        )

    @query_params("cluster_manager_timeout")
    async def migrate_to_hot(
        self,
        *,
        index: Any,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Starts an asynchronous migration from UltraWarm to hot storage.


        :arg index: The name of the index to migrate.
        :arg cluster_manager_timeout: Time to wait for a response from
            the cluster manager node.
        """
        if index in SKIP_IN_PATH:
            raise ValueError("Empty value passed for a required argument 'index'.")

        return await self.transport.perform_request(
            "POST",
            _make_path("_ultrawarm", "migration", index, "_hot"),
            params=params,
            headers=headers,
        )

    @query_params("cluster_manager_timeout")
    async def migrate_to_warm(
        self,
        *,
        index: Any,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Starts an asynchronous migration from hot storage to UltraWarm.


        :arg index: The name of the index to migrate.
        :arg cluster_manager_timeout: Time to wait for a response from
            the cluster manager node.
        """
        if index in SKIP_IN_PATH:
            raise ValueError("Empty value passed for a required argument 'index'.")

        return await self.transport.perform_request(
            "POST",
            _make_path("_ultrawarm", "migration", index, "_warm"),
            params=params,
            headers=headers,
        )

    @query_params()
    async def update_migration(
        self,
        *,
        index: Any,
        body: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Updates the configuration of an in-progress UltraWarm migration.


        :arg index: The name of the index to migrate.
        """
        if index in SKIP_IN_PATH:
            raise ValueError("Empty value passed for a required argument 'index'.")

        return await self.transport.perform_request(
            "PUT",
            _make_path("_ultrawarm", "migration", index),
            params=params,
            headers=headers,
            body=body,
        )
