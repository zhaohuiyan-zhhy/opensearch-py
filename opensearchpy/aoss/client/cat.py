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

from ...client.utils import NamespacedClient, _make_path, query_params


class CatClient(NamespacedClient):

    @query_params(
        "error_trace",
        "expand_wildcards",
        "filter_path",
        "format",
        "h",
        "help",
        "human",
        "local",
        "pretty",
        "s",
        "source",
        "v",
    )
    def aliases(
        self,
        *,
        name: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Shows information about aliases currently configured to indexes, including
        filter and routing information.


        :arg name: A comma-separated list of aliases to retrieve.
            Supports wildcards (`*`).  To retrieve all aliases, omit this parameter
            or use `*` or `_all`.
        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg expand_wildcards: Specifies the type of index that wildcard
            expressions can match. Supports comma-separated values. Valid choices
            are all, closed, hidden, none, open.
        :arg filter_path: A comma-separated list of filters used to
            filter the response. Use wildcards to match any field or part of a
            field's name. To exclude fields, use `-`.
        :arg format: A short version of the `Accept` header, such as
            `json` or `yaml`.
        :arg h: A comma-separated list of column names to display.
        :arg help: Returns help information. Default is false.
        :arg human: Whether to return human-readable values for
            statistics. Default is false.
        :arg local: Whether to return information from the local node
            only instead of from the cluster manager node. Default is false.
        :arg pretty: Whether to pretty-format the returned JSON
            response. Default is false.
        :arg s: A comma-separated list of column names or column aliases
            to sort by.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        :arg v: Enables verbose mode, which displays column headers.
            Default is false.
        """
        return self.transport.perform_request(
            "GET", _make_path("_cat", "aliases", name), params=params, headers=headers
        )

    @query_params(
        "bytes",
        "cluster_manager_timeout",
        "error_trace",
        "expand_wildcards",
        "filter_path",
        "format",
        "h",
        "health",
        "help",
        "human",
        "include_unloaded_segments",
        "local",
        "master_timeout",
        "pretty",
        "pri",
        "s",
        "source",
        "time",
        "v",
    )
    def indices(
        self,
        *,
        index: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Lists information related to indexes, that is, how much disk space they are
        using, how many shards they have, their health status, and so on.


        :arg index: A comma-separated list of data streams, indexes, and
            aliases used to limit the request. Supports wildcards (`*`). To target
            all data streams and indexes, omit this parameter or use `*` or `_all`.
        :arg bytes: The units used to display byte values. Valid choices
            are b, kb, k, mb, m, gb, g, tb, t, pb, p.
        :arg cluster_manager_timeout: The amount of time allowed to
            establish a connection to the cluster manager node.
        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg expand_wildcards: Specifies the type of index that wildcard
            expressions can match. Supports comma-separated values. Valid choices
            are all, closed, hidden, none, open.
        :arg filter_path: A comma-separated list of filters used to
            filter the response. Use wildcards to match any field or part of a
            field's name. To exclude fields, use `-`.
        :arg format: A short version of the `Accept` header, such as
            `json` or `yaml`.
        :arg h: A comma-separated list of column names to display.
        :arg health: Limits indexes based on their health status.
            Supported values are `green`, `yellow`, and `red`. Valid choices are
            green, yellow, red.
        :arg help: Returns help information. Default is false.
        :arg human: Whether to return human-readable values for
            statistics. Default is false.
        :arg include_unloaded_segments: Whether to include information
            from segments not loaded into memory. Default is false.
        :arg local: Returns local information but does not retrieve the
            state from the cluster manager node. Default is false.
        :arg master_timeout (Deprecated: To promote inclusive language,
            use `cluster_manager_timeout` instead.): The amount of time allowed to
            establish a connection to the cluster manager node.
        :arg pretty: Whether to pretty-format the returned JSON
            response. Default is false.
        :arg pri: When `true`, returns information only from the primary
            shards. Default is false.
        :arg s: A comma-separated list of column names or column aliases
            to sort by.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        :arg time: Specifies the time units. Valid choices are nanos,
            micros, ms, s, m, h, d.
        :arg v: Enables verbose mode, which displays column headers.
            Default is false.
        """
        return self.transport.perform_request(
            "GET", _make_path("_cat", "indices", index), params=params, headers=headers
        )

    @query_params(
        "cluster_manager_timeout",
        "error_trace",
        "filter_path",
        "format",
        "h",
        "help",
        "human",
        "local",
        "master_timeout",
        "pretty",
        "s",
        "source",
        "v",
    )
    def templates(
        self,
        *,
        name: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Lists the names, patterns, order numbers, and version numbers of index
        templates.


        :arg name: The name of the template to return. Accepts wildcard
            expressions. If omitted, all templates are returned.
        :arg cluster_manager_timeout: The amount of time allowed to
            establish a connection to the cluster manager node.
        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: A comma-separated list of filters used to
            filter the response. Use wildcards to match any field or part of a
            field's name. To exclude fields, use `-`.
        :arg format: A short version of the `Accept` header, such as
            `json` or `yaml`.
        :arg h: A comma-separated list of column names to display.
        :arg help: Returns help information. Default is false.
        :arg human: Whether to return human-readable values for
            statistics. Default is false.
        :arg local: Returns local information but does not retrieve the
            state from the cluster manager node. Default is false.
        :arg master_timeout (Deprecated: To promote inclusive language,
            use `cluster_manager_timeout` instead.): The amount of time allowed to
            establish a connection to the cluster manager node.
        :arg pretty: Whether to pretty-format the returned JSON
            response. Default is false.
        :arg s: A comma-separated list of column names or column aliases
            to sort by.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        :arg v: Enables verbose mode, which displays column headers.
            Default is false.
        """
        return self.transport.perform_request(
            "GET", _make_path("_cat", "templates", name), params=params, headers=headers
        )
