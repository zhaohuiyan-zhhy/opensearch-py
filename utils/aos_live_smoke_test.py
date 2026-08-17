# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

"""Run isolated smoke tests against an Amazon OpenSearch Service domain."""

import argparse
import asyncio
import getpass
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

from opensearchpy import AOSOpenSearch, AsyncAOSOpenSearch, NotFoundError


@dataclass
class Result:
    """One live API check."""

    round: str
    check: str
    status: str
    duration_ms: int
    detail: str = ""


class Recorder:
    """Collect and print results without storing response bodies."""

    def __init__(self) -> None:
        self.results: List[Result] = []

    def run(
        self,
        round_name: str,
        check: str,
        action: Callable[[], Any],
        validate: Optional[Callable[[Any], bool]] = None,
        detail: Optional[Callable[[Any], str]] = None,
    ) -> Any:
        """Run and record one synchronous check."""
        started = time.monotonic()
        try:
            response = action()
            if validate is not None and not validate(response):
                raise AssertionError("response validation returned false")
            result = Result(
                round_name,
                check,
                "PASS",
                int((time.monotonic() - started) * 1000),
                detail(response) if detail is not None else "",
            )
            self.results.append(result)
            print(f"PASS {round_name}: {check} ({result.duration_ms} ms)")
            return response
        except Exception as error:
            result = Result(
                round_name,
                check,
                "FAIL",
                int((time.monotonic() - started) * 1000),
                _error_detail(error),
            )
            self.results.append(result)
            print(
                f"FAIL {round_name}: {check} ({result.duration_ms} ms): "
                f"{result.detail}"
            )
            return None

    async def run_async(
        self,
        round_name: str,
        check: str,
        action: Callable[[], Awaitable[Any]],
        validate: Optional[Callable[[Any], bool]] = None,
        detail: Optional[Callable[[Any], str]] = None,
    ) -> Any:
        """Run and record one asynchronous check."""
        started = time.monotonic()
        try:
            response = await action()
            if validate is not None and not validate(response):
                raise AssertionError("response validation returned false")
            result = Result(
                round_name,
                check,
                "PASS",
                int((time.monotonic() - started) * 1000),
                detail(response) if detail is not None else "",
            )
            self.results.append(result)
            print(f"PASS {round_name}: {check} ({result.duration_ms} ms)")
            return response
        except Exception as error:
            result = Result(
                round_name,
                check,
                "FAIL",
                int((time.monotonic() - started) * 1000),
                _error_detail(error),
            )
            self.results.append(result)
            print(
                f"FAIL {round_name}: {check} ({result.duration_ms} ms): "
                f"{result.detail}"
            )
            return None

    def skip(self, category: str, check: str, reason: str) -> None:
        """Record an intentionally skipped API category."""
        self.results.append(Result(category, check, "SKIP", 0, reason))


def _error_detail(error: Exception) -> str:
    detail = str(error).replace("\n", " ")
    return f"{type(error).__name__}: {detail}"[:500]


def _is_acknowledged(response: Any) -> bool:
    return isinstance(response, dict) and response.get("acknowledged") is True


def _is_dict(response: Any) -> bool:
    return isinstance(response, dict)


def _is_nonempty_list(response: Any) -> bool:
    return isinstance(response, list) and bool(response)


def _ignore_not_found(action: Callable[[], Any]) -> Any:
    try:
        return action()
    except NotFoundError:
        return {"already_absent": True}


def _is_absent(action: Callable[[], Any]) -> bool:
    try:
        response = action()
        return not bool(response)
    except NotFoundError:
        return True


def _uses_optimized_engine(response: Any, index: str) -> bool:
    if not isinstance(response, dict):
        return False
    settings = response.get(index, {}).get("settings", {}).get("index", {})
    value = settings.get("index.append_only.enabled")
    if value is None:
        value = settings.get("append_only.enabled")
    if value is None and isinstance(settings.get("append_only"), dict):
        value = settings["append_only"].get("enabled")
    return str(value).lower() == "true"


def _probe_optimized_engine(
    client: AOSOpenSearch, recorder: Recorder, round_name: str, index: str
) -> bool:
    started = time.monotonic()
    try:
        client.count(index=index)
        detail = "standard engine APIs available"
        optimized = False
    except NotFoundError as error:
        if "Optimized Engine" not in str(error):
            raise
        detail = "domain proxy reports Optimized Engine"
        optimized = True
    duration_ms = int((time.monotonic() - started) * 1000)
    recorder.results.append(
        Result(round_name, "environment.engine_mode_probe", "PASS", duration_ms, detail)
    )
    print(
        f"PASS {round_name}: environment.engine_mode_probe "
        f"({duration_ms} ms): {detail}"
    )
    return optimized


def _client_options(endpoint: str, username: str, password: str) -> Dict[str, Any]:
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("endpoint must be an HTTPS URL or hostname")
    if parsed.path not in ("", "/"):
        raise ValueError("endpoint must not include a path")
    return {
        "hosts": [{"host": parsed.hostname, "port": parsed.port or 443}],
        "http_auth": (username, password),
        "use_ssl": True,
        "verify_certs": True,
        "ssl_assert_hostname": True,
        "ssl_show_warn": True,
        "timeout": 30,
    }


def _run_read_only_checks(client: AOSOpenSearch, recorder: Recorder) -> None:
    round_name = "round-1-read-and-index-metadata"
    recorder.run(round_name, "root.ping", client.ping, lambda value: value is True)
    recorder.run(
        round_name,
        "root.info",
        client.info,
        lambda value: isinstance(value, dict) and "version" in value,
        lambda value: f"version={value['version'].get('number', 'unknown')}",
    )
    recorder.run(
        round_name,
        "cluster.health",
        client.cluster.health,
        lambda value: isinstance(value, dict)
        and value.get("status") in {"green", "yellow"},
        lambda value: f"status={value.get('status')}",
    )
    recorder.run(
        round_name, "cluster.get_settings", client.cluster.get_settings, _is_dict
    )
    recorder.run(round_name, "cluster.stats", client.cluster.stats, _is_dict)
    recorder.run(
        round_name, "cluster.pending_tasks", client.cluster.pending_tasks, _is_dict
    )
    recorder.run(round_name, "nodes.info", client.nodes.info, _is_dict)
    recorder.run(round_name, "nodes.stats", client.nodes.stats, _is_dict)
    recorder.run(round_name, "nodes.usage", client.nodes.usage, _is_dict)
    recorder.run(
        round_name,
        "cat.health",
        lambda: client.cat.health(params={"format": "json"}),
        _is_nonempty_list,
    )
    recorder.run(
        round_name,
        "cat.nodes",
        lambda: client.cat.nodes(params={"format": "json"}),
        _is_nonempty_list,
    )
    recorder.run(
        round_name,
        "cat.plugins",
        lambda: client.cat.plugins(params={"format": "json"}),
        lambda value: isinstance(value, list),
    )
    recorder.run(round_name, "tasks.list", client.tasks.list, _is_dict)
    recorder.run(
        round_name, "security.get_sslinfo", client.security.get_sslinfo, _is_dict
    )


def _run_index_metadata_checks(
    client: AOSOpenSearch, recorder: Recorder, names: Dict[str, str]
) -> bool:
    round_name = "round-1-read-and-index-metadata"
    index = names["index"]
    index_body = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "5s",
            "index.append_only.enabled": False,
        },
        "mappings": {
            "properties": {
                "message": {"type": "text"},
                "category": {"type": "keyword"},
                "count": {"type": "integer"},
                "timestamp": {"type": "date"},
            }
        },
    }
    recorder.run(
        round_name,
        "indices.create",
        lambda: client.indices.create(index=index, body=index_body),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "indices.exists",
        lambda: client.indices.exists(index=index),
        lambda value: value is True,
    )
    recorder.run(
        round_name,
        "indices.get",
        lambda: client.indices.get(index=index),
        lambda value: isinstance(value, dict) and index in value,
    )
    recorder.run(
        round_name,
        "indices.get_mapping",
        lambda: client.indices.get_mapping(index=index),
        lambda value: isinstance(value, dict) and index in value,
    )
    settings = recorder.run(
        round_name,
        "indices.get_settings",
        lambda: client.indices.get_settings(index=index),
        lambda value: isinstance(value, dict) and index in value,
    )
    recorder.run(
        round_name,
        "indices.put_mapping",
        lambda: client.indices.put_mapping(
            index=index, body={"properties": {"added": {"type": "boolean"}}}
        ),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "indices.get_field_mapping",
        lambda: client.indices.get_field_mapping(index=index, fields="added"),
        _is_dict,
    )
    recorder.run(
        round_name,
        "indices.put_settings",
        lambda: client.indices.put_settings(
            index=index, body={"index": {"refresh_interval": "10s"}}
        ),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "indices.analyze",
        lambda: client.indices.analyze(
            index=index, body={"analyzer": "standard", "text": "AOS smoke test"}
        ),
        lambda value: isinstance(value, dict) and bool(value.get("tokens")),
    )
    optimized_engine = _probe_optimized_engine(
        client, recorder, round_name, index
    ) or _uses_optimized_engine(settings, index)
    if optimized_engine:
        recorder.skip(
            round_name,
            "indices.validate_query",
            "domain uses Optimized Engine, which blocks _validate/query",
        )
    else:
        recorder.run(
            round_name,
            "indices.validate_query",
            lambda: client.indices.validate_query(
                index=index, body={"query": {"match": {"message": "smoke"}}}
            ),
            lambda value: isinstance(value, dict) and value.get("valid") is True,
        )
    recorder.run(
        round_name,
        "indices.resolve_index",
        lambda: client.indices.resolve_index(name=index),
        lambda value: isinstance(value, dict) and bool(value.get("indices")),
    )
    recorder.run(
        round_name,
        "indices.stats",
        lambda: client.indices.stats(index=index),
        _is_dict,
    )
    return optimized_engine


def _run_template_and_data_stream_checks(
    client: AOSOpenSearch, recorder: Recorder, names: Dict[str, str]
) -> None:
    round_name = "round-1-read-and-index-metadata"
    legacy_template = names["legacy_template"]
    index_template = names["index_template"]
    data_stream_template = names["data_stream_template"]
    data_stream = names["data_stream"]

    recorder.run(
        round_name,
        "indices.put_template",
        lambda: client.indices.put_template(
            name=legacy_template,
            body={
                "index_patterns": [f"{legacy_template}-*"],
                "settings": {"number_of_shards": 1},
            },
        ),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "indices.exists_template",
        lambda: client.indices.exists_template(name=legacy_template),
        lambda value: value is True,
    )
    recorder.run(
        round_name,
        "indices.get_template",
        lambda: client.indices.get_template(name=legacy_template),
        lambda value: isinstance(value, dict) and legacy_template in value,
    )
    recorder.run(
        round_name,
        "indices.put_index_template",
        lambda: client.indices.put_index_template(
            name=index_template,
            body={
                "index_patterns": [f"{index_template}-*"],
                "template": {"settings": {"number_of_shards": 1}},
            },
        ),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "indices.exists_index_template",
        lambda: client.indices.exists_index_template(name=index_template),
        lambda value: value is True,
    )
    recorder.run(
        round_name,
        "indices.get_index_template",
        lambda: client.indices.get_index_template(name=index_template),
        _is_dict,
    )
    recorder.run(
        round_name,
        "indices.simulate_index_template",
        lambda: client.indices.simulate_index_template(name=index_template),
        _is_dict,
    )
    recorder.run(
        round_name,
        "indices.put_index_template[data_stream]",
        lambda: client.indices.put_index_template(
            name=data_stream_template,
            body={
                "index_patterns": [f"{data_stream}-*"],
                "data_stream": {},
                "template": {
                    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                            "message": {"type": "text"},
                        }
                    },
                },
            },
        ),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "indices.create_data_stream",
        lambda: client.indices.create_data_stream(name=f"{data_stream}-logs"),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "root.index[data_stream]",
        lambda: client.index(
            index=f"{data_stream}-logs",
            body={
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "test",
            },
            params={"op_type": "create", "refresh": "true"},
        ),
        lambda value: isinstance(value, dict) and value.get("result") == "created",
    )
    recorder.run(
        round_name,
        "indices.get_data_stream",
        lambda: client.indices.get_data_stream(name=f"{data_stream}-logs"),
        lambda value: isinstance(value, dict) and bool(value.get("data_streams")),
    )
    recorder.run(
        round_name,
        "indices.data_streams_stats",
        lambda: client.indices.data_streams_stats(name=f"{data_stream}-logs"),
        _is_dict,
    )


def _run_document_and_query_checks(
    client: AOSOpenSearch,
    recorder: Recorder,
    names: Dict[str, str],
    optimized_engine: bool,
) -> None:
    round_name = "round-2-documents-search-and-plugins"
    index = names["index"]
    read_id = "2" if optimized_engine else "1"
    bulk_action = "create" if optimized_engine else "index"
    index_kwargs = {} if optimized_engine else {"id": "1"}
    recorder.run(
        round_name,
        "root.index",
        lambda: client.index(
            index=index,
            body={
                "message": "first smoke document",
                "category": "alpha",
                "count": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            params={"refresh": "true"},
            **index_kwargs,
        ),
        lambda value: isinstance(value, dict)
        and value.get("result") in {"created", "updated"},
    )
    recorder.run(
        round_name,
        "root.create",
        lambda: client.create(
            index=index,
            id="2",
            body={
                "message": "second smoke document",
                "category": "beta",
                "count": 2,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            params={"refresh": "true"},
        ),
        lambda value: isinstance(value, dict) and value.get("result") == "created",
    )
    recorder.run(
        round_name,
        "root.bulk",
        lambda: client.bulk(
            index=index,
            body=[
                {bulk_action: {"_id": "3"}},
                {
                    "message": "third bulk document",
                    "category": "alpha",
                    "count": 3,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                {bulk_action: {"_id": "4"}},
                {
                    "message": "fourth bulk document",
                    "category": "beta",
                    "count": 4,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            ],
            params={"refresh": "true"},
        ),
        lambda value: isinstance(value, dict) and value.get("errors") is False,
    )
    recorder.run(
        round_name,
        "root.exists",
        lambda: client.exists(index=index, id=read_id),
        lambda value: value is True,
    )
    recorder.run(
        round_name,
        "root.exists_source",
        lambda: client.exists_source(index=index, id=read_id),
        lambda value: value is True,
    )
    recorder.run(
        round_name,
        "root.get",
        lambda: client.get(index=index, id=read_id),
        lambda value: isinstance(value, dict) and value.get("found") is True,
    )
    recorder.run(
        round_name,
        "root.get_source",
        lambda: client.get_source(index=index, id=read_id),
        lambda value: isinstance(value, dict)
        and value.get("count") == (2 if optimized_engine else 1),
    )
    if optimized_engine:
        recorder.skip(
            round_name,
            "root.update",
            "domain uses Optimized Engine, which is append-only",
        )
    else:
        recorder.run(
            round_name,
            "root.update",
            lambda: client.update(
                index=index,
                id="1",
                body={"doc": {"count": 10, "added": True}},
                params={"refresh": "true"},
            ),
            lambda value: isinstance(value, dict) and value.get("result") == "updated",
        )
    recorder.run(
        round_name,
        "root.mget",
        lambda: client.mget(index=index, body={"ids": [read_id, "3", "missing"]}),
        lambda value: isinstance(value, dict) and len(value.get("docs", [])) == 3,
    )
    if optimized_engine:
        for check in ("root.count", "root.search", "root.msearch", "root.explain"):
            recorder.skip(
                round_name,
                check,
                "domain proxy blocks this API with Optimized Engine",
            )
    else:
        recorder.run(
            round_name,
            "root.count",
            lambda: client.count(index=index),
            lambda value: isinstance(value, dict) and value.get("count", 0) >= 4,
        )
        recorder.run(
            round_name,
            "root.search",
            lambda: client.search(
                index=index,
                body={
                    "query": {"match": {"message": "smoke"}},
                    "aggs": {"by_category": {"terms": {"field": "category"}}},
                },
            ),
            lambda value: isinstance(value, dict) and "hits" in value,
        )
        recorder.run(
            round_name,
            "root.msearch",
            lambda: client.msearch(
                index=index,
                body=[
                    {},
                    {"query": {"term": {"category": "alpha"}}},
                    {},
                    {"query": {"term": {"category": "beta"}}},
                ],
            ),
            lambda value: isinstance(value, dict)
            and len(value.get("responses", [])) == 2,
        )
        recorder.run(
            round_name,
            "root.explain",
            lambda: client.explain(
                index=index, id="1", body={"query": {"match_all": {}}}
            ),
            lambda value: isinstance(value, dict) and value.get("matched") is True,
        )
    if optimized_engine:
        recorder.skip(
            round_name,
            "root.termvectors",
            "Optimized Engine returns HTTP 500 for term vector requests",
        )
    else:
        recorder.run(
            round_name,
            "root.termvectors",
            lambda: client.termvectors(
                index=index, id=read_id, body={"fields": ["message"]}
            ),
            lambda value: isinstance(value, dict) and value.get("found") is True,
        )
    recorder.run(
        round_name,
        "root.field_caps",
        lambda: client.field_caps(index=index, params={"fields": "category,count"}),
        lambda value: isinstance(value, dict) and "fields" in value,
    )
    recorder.run(
        round_name,
        "root.search_shards",
        lambda: client.search_shards(index=index),
        lambda value: isinstance(value, dict) and bool(value.get("shards")),
    )
    recorder.run(
        round_name,
        "indices.refresh",
        lambda: client.indices.refresh(index=index),
        _is_dict,
    )
    recorder.run(
        round_name,
        "indices.flush",
        lambda: client.indices.flush(index=index),
        _is_dict,
    )
    recorder.run(
        round_name,
        "cat.indices",
        lambda: client.cat.indices(index=index, params={"format": "json"}),
        _is_nonempty_list,
    )
    if optimized_engine:
        recorder.skip(
            round_name,
            "cat.count",
            "domain proxy blocks _cat/count with Optimized Engine",
        )
    else:
        recorder.run(
            round_name,
            "cat.count",
            lambda: client.cat.count(index=index, params={"format": "json"}),
            _is_nonempty_list,
        )
    recorder.run(
        round_name,
        "cat.shards",
        lambda: client.cat.shards(index=index, params={"format": "json"}),
        _is_nonempty_list,
    )


def _run_alias_pipeline_and_plugin_checks(
    client: AOSOpenSearch,
    recorder: Recorder,
    names: Dict[str, str],
    optimized_engine: bool,
) -> None:
    round_name = "round-2-documents-search-and-plugins"
    index = names["index"]
    alias = names["alias"]
    ingest_pipeline = names["ingest_pipeline"]
    search_pipeline = names["search_pipeline"]
    ism_policy = names["ism_policy"]
    index_kwargs = {} if optimized_engine else {"id": "pipeline-doc"}

    recorder.run(
        round_name,
        "indices.put_alias",
        lambda: client.indices.put_alias(index=index, name=alias),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "indices.exists_alias",
        lambda: client.indices.exists_alias(index=index, name=alias),
        lambda value: value is True,
    )
    recorder.run(
        round_name,
        "indices.get_alias",
        lambda: client.indices.get_alias(index=index, name=alias),
        _is_dict,
    )
    recorder.run(
        round_name,
        "cat.aliases",
        lambda: client.cat.aliases(name=alias, params={"format": "json"}),
        _is_nonempty_list,
    )
    recorder.run(
        round_name,
        "ingest.put_pipeline",
        lambda: client.ingest.put_pipeline(
            id=ingest_pipeline,
            body={
                "description": "AOS generated client smoke test",
                "processors": [{"set": {"field": "ingested", "value": True}}],
            },
        ),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "ingest.get_pipeline",
        lambda: client.ingest.get_pipeline(id=ingest_pipeline),
        lambda value: isinstance(value, dict) and ingest_pipeline in value,
    )
    recorder.run(
        round_name,
        "ingest.simulate",
        lambda: client.ingest.simulate(
            id=ingest_pipeline,
            body={"docs": [{"_source": {"message": "pipeline smoke"}}]},
        ),
        lambda value: isinstance(value, dict) and bool(value.get("docs")),
    )
    recorder.run(
        round_name,
        "root.index[pipeline]",
        lambda: client.index(
            index=index,
            body={
                "message": "pipeline document",
                "category": "pipeline",
                "count": 5,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            params={"pipeline": ingest_pipeline, "refresh": "true"},
            **index_kwargs,
        ),
        lambda value: isinstance(value, dict) and value.get("result") == "created",
    )
    recorder.run(
        round_name,
        "search_pipeline.put",
        lambda: client.search_pipeline.put(
            id=search_pipeline,
            body={
                "description": "AOS generated client smoke test",
                "request_processors": [],
                "response_processors": [],
            },
        ),
        _is_acknowledged,
    )
    recorder.run(
        round_name,
        "search_pipeline.get",
        lambda: client.search_pipeline.get(id=search_pipeline),
        lambda value: isinstance(value, dict) and search_pipeline in value,
    )
    if optimized_engine:
        recorder.skip(
            round_name,
            "root.search[search_pipeline]",
            "domain proxy blocks _search with Optimized Engine",
        )
    else:
        recorder.run(
            round_name,
            "root.search[search_pipeline]",
            lambda: client.search(
                index=index,
                body={"query": {"match_all": {}}},
                params={"search_pipeline": search_pipeline},
            ),
            lambda value: isinstance(value, dict) and "hits" in value,
        )
    recorder.run(
        round_name,
        "plugins.sql.query",
        lambda: client.plugins.sql.query(
            body={"query": f"SELECT COUNT(*) AS total FROM `{index}`"}
        ),
        lambda value: isinstance(value, dict) and "datarows" in value,
    )
    recorder.run(
        round_name,
        "plugins.ism.put_policy",
        lambda: client.plugins.ism.put_policy(
            policy_id=ism_policy,
            body={
                "policy": {
                    "description": "AOS generated client smoke test",
                    "default_state": "active",
                    "states": [
                        {
                            "name": "active",
                            "actions": [],
                            "transitions": [],
                        }
                    ],
                }
            },
        ),
        lambda value: isinstance(value, dict) and value.get("_id") == ism_policy,
    )
    recorder.run(
        round_name,
        "plugins.ism.get_policy",
        lambda: client.plugins.ism.get_policy(policy_id=ism_policy),
        lambda value: isinstance(value, dict) and value.get("_id") == ism_policy,
    )
    recorder.run(
        round_name, "insights.top_queries", client.insights.top_queries, _is_dict
    )


async def _run_async_checks(
    options: Dict[str, Any],
    recorder: Recorder,
    names: Dict[str, str],
    optimized_engine: bool,
) -> None:
    round_name = "round-3-async-client"
    async_index = names["async_index"]
    client = AsyncAOSOpenSearch(**options)
    try:
        await recorder.run_async(
            round_name, "async.root.ping", client.ping, lambda value: value is True
        )
        await recorder.run_async(
            round_name,
            "async.root.info",
            client.info,
            lambda value: isinstance(value, dict) and "version" in value,
        )
        await recorder.run_async(
            round_name,
            "async.cluster.health",
            client.cluster.health,
            lambda value: isinstance(value, dict)
            and value.get("status") in {"green", "yellow"},
        )
        await recorder.run_async(
            round_name,
            "async.indices.create",
            lambda: client.indices.create(
                index=async_index,
                body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "index.append_only.enabled": False,
                    },
                    "mappings": {
                        "properties": {
                            "message": {"type": "text"},
                            "value": {"type": "integer"},
                        }
                    },
                },
            ),
            _is_acknowledged,
        )
        index_kwargs = {} if optimized_engine else {"id": "1"}
        index_response = await recorder.run_async(
            round_name,
            "async.root.index",
            lambda: client.index(
                index=async_index,
                body={"message": "async smoke", "value": 1},
                params={"refresh": "true"},
                **index_kwargs,
            ),
            lambda value: isinstance(value, dict) and value.get("result") == "created",
        )
        read_id = (
            index_response.get("_id", "missing")
            if isinstance(index_response, dict)
            else "missing"
        )
        await recorder.run_async(
            round_name,
            "async.root.get",
            lambda: client.get(index=async_index, id=read_id),
            lambda value: isinstance(value, dict) and value.get("found") is True,
        )
        await recorder.run_async(
            round_name,
            "async.root.exists",
            lambda: client.exists(index=async_index, id=read_id),
            lambda value: value is True,
        )
        await recorder.run_async(
            round_name,
            "async.root.mget",
            lambda: client.mget(index=async_index, body={"ids": [read_id, "missing"]}),
            lambda value: isinstance(value, dict) and len(value.get("docs", [])) == 2,
        )
        if optimized_engine:
            for check in (
                "async.root.search",
                "async.root.update",
                "async.root.count",
                "async.root.delete",
            ):
                recorder.skip(
                    round_name,
                    check,
                    "domain blocks this operation with Optimized Engine",
                )
        else:
            await recorder.run_async(
                round_name,
                "async.root.search",
                lambda: client.search(
                    index=async_index,
                    body={"query": {"match": {"message": "async"}}},
                ),
                lambda value: isinstance(value, dict)
                and value.get("hits", {}).get("total", {}).get("value") == 1,
            )
            await recorder.run_async(
                round_name,
                "async.root.update",
                lambda: client.update(
                    index=async_index,
                    id=read_id,
                    body={"doc": {"value": 2}},
                    params={"refresh": "true"},
                ),
                lambda value: isinstance(value, dict)
                and value.get("result") == "updated",
            )
            await recorder.run_async(
                round_name,
                "async.root.count",
                lambda: client.count(index=async_index),
                lambda value: isinstance(value, dict) and value.get("count") == 1,
            )
            await recorder.run_async(
                round_name,
                "async.root.delete",
                lambda: client.delete(
                    index=async_index, id=read_id, params={"refresh": "true"}
                ),
                lambda value: isinstance(value, dict)
                and value.get("result") == "deleted",
            )
    finally:
        await recorder.run_async(
            "cleanup",
            "async.indices.delete",
            lambda: client.indices.delete(
                index=async_index, params={"ignore_unavailable": "true"}
            ),
            _is_acknowledged,
        )
        await client.close()


def _run_cleanup(
    client: AOSOpenSearch, recorder: Recorder, names: Dict[str, str]
) -> None:
    cleanup_actions = [
        (
            "plugins.ism.delete_policy",
            lambda: client.plugins.ism.delete_policy(policy_id=names["ism_policy"]),
        ),
        (
            "search_pipeline.delete",
            lambda: client.search_pipeline.delete(id=names["search_pipeline"]),
        ),
        (
            "ingest.delete_pipeline",
            lambda: client.ingest.delete_pipeline(id=names["ingest_pipeline"]),
        ),
        (
            "indices.delete_data_stream",
            lambda: client.indices.delete_data_stream(
                name=f"{names['data_stream']}-logs"
            ),
        ),
        (
            "indices.delete_index_template[data_stream]",
            lambda: client.indices.delete_index_template(
                name=names["data_stream_template"]
            ),
        ),
        (
            "indices.delete_index_template",
            lambda: client.indices.delete_index_template(name=names["index_template"]),
        ),
        (
            "indices.delete_template",
            lambda: client.indices.delete_template(name=names["legacy_template"]),
        ),
        (
            "indices.delete",
            lambda: client.indices.delete(
                index=names["index"], params={"ignore_unavailable": "true"}
            ),
        ),
    ]
    for check, action in cleanup_actions:
        recorder.run(
            "cleanup",
            check,
            partial(_ignore_not_found, action),
        )


def _record_skips(recorder: Recorder) -> None:
    skipped = {
        "snapshot.*": "requires a preconfigured snapshot repository and IAM role",
        "ultrawarm.migrate_*": "requires UltraWarm capacity and long-running migration",
        "remote_store.restore": "requires a remote-backed index and repository",
        "dangling_indices.*": "requires intentionally creating dangling on-disk data",
        "cluster.reroute": "can move shards and affect the entire domain",
        "cluster.put_settings": "changes persistent or transient domain-wide settings",
        "cluster weighted routing/decommission": "changes availability-zone routing for the domain",
        "nodes.reload_secure_settings": "requires the keystore password and node-wide action",
        "ingestion.pause/resume": "requires an existing ingestion sourceCollectionId",
        "ultrawarm cold-index allow_regex": "requires cold storage resources and a suitable migrated index",
        "ML/neural/replication/notifications plugins": "require models, remote clusters, channels, or other external resources",
    }
    for check, reason in skipped.items():
        recorder.skip("not-run-requires-infrastructure-or-high-risk", check, reason)


def _verify_cleanup(client: AOSOpenSearch, names: Dict[str, str]) -> Dict[str, bool]:
    checks = {
        "index_absent": not client.indices.exists(index=names["index"]),
        "async_index_absent": not client.indices.exists(index=names["async_index"]),
        "data_stream_absent": not bool(
            client.indices.exists(index=f"{names['data_stream']}-logs")
        ),
        "legacy_template_absent": not client.indices.exists_template(
            name=names["legacy_template"]
        ),
        "index_template_absent": not client.indices.exists_index_template(
            name=names["index_template"]
        ),
        "data_stream_template_absent": not client.indices.exists_index_template(
            name=names["data_stream_template"]
        ),
        "ingest_pipeline_absent": _is_absent(
            lambda: client.ingest.get_pipeline(id=names["ingest_pipeline"])
        ),
        "search_pipeline_absent": _is_absent(
            lambda: client.search_pipeline.get(id=names["search_pipeline"])
        ),
        "ism_policy_absent": _is_absent(
            lambda: client.plugins.ism.get_policy(policy_id=names["ism_policy"])
        ),
    }
    return checks


def _report(
    recorder: Recorder,
    output: Path,
    endpoint: str,
    started_at: str,
    prefix: str,
    cleanup_verification: Dict[str, bool],
) -> None:
    counts = {
        status: sum(result.status == status for result in recorder.results)
        for status in ("PASS", "FAIL", "SKIP")
    }
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    report = {
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "target": {
            "host": parsed.hostname,
        },
        "resource_prefix": prefix,
        "summary": counts,
        "cleanup_verification": cleanup_verification,
        "results": [asdict(result) for result in recorder.results],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"SUMMARY pass={counts['PASS']} fail={counts['FAIL']} "
        f"skip={counts['SKIP']} report={output}"
    )


def main() -> int:
    """Run all live checks and return nonzero on test or cleanup failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True, help="AOS HTTPS endpoint")
    parser.add_argument("--username", required=True, help="Internal master username")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/aos-live-smoke-report.json"),
        help="JSON result path (default: /tmp/aos-live-smoke-report.json)",
    )
    args = parser.parse_args()

    password = getpass.getpass("AOS password: ")
    if not password:
        parser.error("password must not be empty")

    started_at = datetime.now(timezone.utc).isoformat()
    prefix = f"aos-client-smoke-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}"
    names = {
        "index": f"{prefix}-index",
        "async_index": f"{prefix}-async",
        "alias": f"{prefix}-alias",
        "legacy_template": f"{prefix}-legacy-template",
        "index_template": f"{prefix}-index-template",
        "data_stream_template": f"{prefix}-ds-template",
        "data_stream": f"{prefix}-ds",
        "ingest_pipeline": f"{prefix}-ingest",
        "search_pipeline": f"{prefix}-search-pipeline",
        "ism_policy": f"{prefix}-ism",
    }
    recorder = Recorder()
    options = _client_options(args.endpoint, args.username, password)
    client = AOSOpenSearch(**options)
    cleanup_verification: Dict[str, bool] = {}

    try:
        _run_read_only_checks(client, recorder)
        optimized_engine = _run_index_metadata_checks(client, recorder, names)
        _run_template_and_data_stream_checks(client, recorder, names)
        _run_document_and_query_checks(client, recorder, names, optimized_engine)
        _run_alias_pipeline_and_plugin_checks(client, recorder, names, optimized_engine)
        asyncio.run(_run_async_checks(options, recorder, names, optimized_engine))
    finally:
        _run_cleanup(client, recorder, names)
        try:
            cleanup_verification = _verify_cleanup(client, names)
        except Exception as error:
            cleanup_verification = {"verification_completed": False}
            recorder.results.append(
                Result(
                    "cleanup",
                    "verify_all_resources_absent",
                    "FAIL",
                    0,
                    _error_detail(error),
                )
            )
        client.close()
        _record_skips(recorder)
        _report(
            recorder,
            args.output,
            args.endpoint,
            started_at,
            prefix,
            cleanup_verification,
        )

    failed = any(result.status == "FAIL" for result in recorder.results)
    cleanup_failed = not cleanup_verification or not all(cleanup_verification.values())
    return 1 if failed or cleanup_failed else 0


if __name__ == "__main__":
    sys.exit(main())
