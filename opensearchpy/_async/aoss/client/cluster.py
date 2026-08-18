# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

# ------------------------------------------------------------------------------------------
# THIS CODE IS AUTOMATICALLY GENERATED AND MANUAL EDITS WILL BE LOST
#
# To contribute, kindly make modifications in the opensearch-py client generator
# or in the OpenSearch API specification, and run `nox -rs generate_aoss`. See DEVELOPER_GUIDE.md
# and https://github.com/opensearch-project/opensearch-api-specification for details.
# -----------------------------------------------------------------------------------------+

from typing import Any

from ...client.utils import SKIP_IN_PATH, NamespacedClient, _make_path, query_params


class ClusterClient(NamespacedClient):

    @query_params(
        "cluster_manager_timeout",
        "error_trace",
        "filter_path",
        "human",
        "master_timeout",
        "pretty",
        "source",
        "timeout",
    )
    async def delete_component_template(
        self,
        *,
        name: Any,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Deletes a component template.


        :arg name: The name of the component template to delete.
            Supports wildcard (*) expressions.
        :arg cluster_manager_timeout: The amount of time to wait for a
            response from the cluster manager node. For more information about
            supported time units, see [Common
            parameters](https://opensearch.org/docs/latest/api-reference/common-
            parameters/#time-units).
        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: A comma-separated list of filters used to
            filter the response. Use wildcards to match any field or part of a
            field's name. To exclude fields, use `-`.
        :arg human: Whether to return human-readable values for
            statistics. Default is false.
        :arg master_timeout (Deprecated: To promote inclusive language,
            use `cluster_manager_timeout` instead.): A duration. Units can be
            `nanos`, `micros`, `ms` (milliseconds), `s` (seconds), `m` (minutes),
            `h` (hours) and `d` (days). Also accepts `0` without a unit and `-1` to
            indicate an unspecified value.
        :arg pretty: Whether to pretty-format the returned JSON
            response. Default is false.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        :arg timeout: A duration. Units can be `nanos`, `micros`, `ms`
            (milliseconds), `s` (seconds), `m` (minutes), `h` (hours) and `d`
            (days). Also accepts `0` without a unit and `-1` to indicate an
            unspecified value.
        """
        if name in SKIP_IN_PATH:
            raise ValueError("Empty value passed for a required argument 'name'.")

        return await self.transport.perform_request(
            "DELETE",
            _make_path("_component_template", name),
            params=params,
            headers=headers,
        )

    @query_params(
        "cluster_manager_timeout",
        "error_trace",
        "filter_path",
        "flat_settings",
        "human",
        "local",
        "master_timeout",
        "pretty",
        "source",
    )
    async def get_component_template(
        self,
        *,
        name: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Returns one or more component templates.


        :arg name: The name of the component template to retrieve.
            Wildcard (`*`) expressions are supported.
        :arg cluster_manager_timeout: The amount of time to wait for a
            response from the cluster manager node. For more information about
            supported time units, see [Common
            parameters](https://opensearch.org/docs/latest/api-reference/common-
            parameters/#time-units).
        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: A comma-separated list of filters used to
            filter the response. Use wildcards to match any field or part of a
            field's name. To exclude fields, use `-`.
        :arg flat_settings: Whether to return settings in the flat form,
            which can improve readability, especially for heavily nested settings.
            For example, the flat form of `"cluster": { "max_shards_per_node": 500
            }` is `"cluster.max_shards_per_node": "500"`. Default is false.
        :arg human: Whether to return human-readable values for
            statistics. Default is false.
        :arg local: When `true`, the request retrieves information from
            the local node only. When `false`, information is retrieved from the
            cluster manager node. Default is false.
        :arg master_timeout (Deprecated: To promote inclusive language,
            use `cluster_manager_timeout` instead.): A duration. Units can be
            `nanos`, `micros`, `ms` (milliseconds), `s` (seconds), `m` (minutes),
            `h` (hours) and `d` (days). Also accepts `0` without a unit and `-1` to
            indicate an unspecified value.
        :arg pretty: Whether to pretty-format the returned JSON
            response. Default is false.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        """
        return await self.transport.perform_request(
            "GET",
            _make_path("_component_template", name),
            params=params,
            headers=headers,
        )

    @query_params(
        "cluster_manager_timeout",
        "create",
        "error_trace",
        "filter_path",
        "human",
        "master_timeout",
        "pretty",
        "source",
        "timeout",
    )
    async def put_component_template(
        self,
        *,
        name: Any,
        body: Any,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Creates or updates a component template.


        :arg name: The name of the component template to create.
            OpenSearch includes the following built-in component templates: `logs-
            mappings`, `logs-settings`, `metrics-mappings`, `metrics-settings`,
            `synthetics-mapping`, and `synthetics-settings`. OpenSearch uses these
            templates to configure backing indexes for its data streams. If you want
            to overwrite one of these templates, set the replacement template
            `version` to a higher value than the current version. If you want to
            disable all built-in component and index templates, set
            `stack.templates.enabled` to `false` using the [Cluster Update Settings
            API](https://opensearch.org/docs/latest/api-reference/cluster-
            api/cluster-settings/).
        :arg body: The template definition.
        :arg cluster_manager_timeout: The amount of time to wait for a
            response from the cluster manager node. For more information about
            supported time units, see [Common
            parameters](https://opensearch.org/docs/latest/api-reference/common-
            parameters/#time-units).
        :arg create: When `true`, this request cannot replace or update
            existing component templates. Default is false.
        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: A comma-separated list of filters used to
            filter the response. Use wildcards to match any field or part of a
            field's name. To exclude fields, use `-`.
        :arg human: Whether to return human-readable values for
            statistics. Default is false.
        :arg master_timeout (Deprecated: To promote inclusive language,
            use `cluster_manager_timeout` instead.): A duration. Units can be
            `nanos`, `micros`, `ms` (milliseconds), `s` (seconds), `m` (minutes),
            `h` (hours) and `d` (days). Also accepts `0` without a unit and `-1` to
            indicate an unspecified value.
        :arg pretty: Whether to pretty-format the returned JSON
            response. Default is false.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        :arg timeout: A duration. Units can be `nanos`, `micros`, `ms`
            (milliseconds), `s` (seconds), `m` (minutes), `h` (hours) and `d`
            (days). Also accepts `0` without a unit and `-1` to indicate an
            unspecified value.
        """
        for param in (name, body):
            if param in SKIP_IN_PATH:
                raise ValueError("Empty value passed for a required argument.")

        return await self.transport.perform_request(
            "PUT",
            _make_path("_component_template", name),
            params=params,
            headers=headers,
            body=body,
        )

    @query_params(
        "cluster_manager_timeout",
        "error_trace",
        "filter_path",
        "human",
        "local",
        "master_timeout",
        "pretty",
        "source",
    )
    async def exists_component_template(
        self,
        *,
        name: Any,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Returns information about whether a particular component template exist.


        :arg name: The name of the component template. Wildcard (*)
            expressions are supported.
        :arg cluster_manager_timeout: The amount of time to wait for a
            response from the cluster manager node. For more information about
            supported time units, see [Common
            parameters](https://opensearch.org/docs/latest/api-reference/common-
            parameters/#time-units).
        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: A comma-separated list of filters used to
            filter the response. Use wildcards to match any field or part of a
            field's name. To exclude fields, use `-`.
        :arg human: Whether to return human-readable values for
            statistics. Default is false.
        :arg local: When `true`, the request retrieves information from
            the local node only. When `false`, information is retrieved from the
            cluster manager node. Default is false.
        :arg master_timeout (Deprecated: To promote inclusive language,
            use `cluster_manager_timeout` instead.): A duration. Units can be
            `nanos`, `micros`, `ms` (milliseconds), `s` (seconds), `m` (minutes),
            `h` (hours) and `d` (days). Also accepts `0` without a unit and `-1` to
            indicate an unspecified value.
        :arg pretty: Whether to pretty-format the returned JSON
            response. Default is false.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        """
        if name in SKIP_IN_PATH:
            raise ValueError("Empty value passed for a required argument 'name'.")

        return await self.transport.perform_request(
            "HEAD",
            _make_path("_component_template", name),
            params=params,
            headers=headers,
        )
