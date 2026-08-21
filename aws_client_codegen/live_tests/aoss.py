#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

"""Run reversible coverage checks against an AOSS collection."""

import argparse
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from botocore.session import Session

from opensearchpy import (
    AOSSOpenSearch,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)


@dataclass
class Result:
    """One live API check."""

    check: str
    status: str
    duration_ms: int
    detail: str = ""


class Recorder:
    """Runs checks while retaining a compact machine-readable result."""

    def __init__(self) -> None:
        self.results: List[Result] = []

    def run(
        self,
        check: str,
        action: Callable[[], Any],
        validate: Callable[[Any], bool],
    ) -> Any:
        """Runs one check without preventing cleanup or later checks on failure."""
        started = time.monotonic()
        try:
            response = action()
            if not validate(response):
                raise AssertionError("response validation returned false")
            result = Result(
                check,
                "PASS",
                int((time.monotonic() - started) * 1000),
            )
            self.results.append(result)
            print(f"PASS {check} ({result.duration_ms} ms)")
            return response
        except Exception as error:
            result = Result(
                check,
                "FAIL",
                int((time.monotonic() - started) * 1000),
                f"{type(error).__name__}: {str(error).replace(chr(10), ' ')}"[:500],
            )
            self.results.append(result)
            print(f"FAIL {check} ({result.duration_ms} ms): {result.detail}")
            return None

    def skip(self, check: str, reason: str) -> None:
        """Records an API category that needs external resources."""
        self.results.append(Result(check, "SKIP", 0, reason))


def _acknowledged(response: Any) -> bool:
    return isinstance(response, dict) and response.get("acknowledged") is True


def _dict(response: Any) -> bool:
    return isinstance(response, dict)


def _wait_for(
    action: Callable[[], Any],
    validate: Callable[[Any], bool],
    timeout: int = 30,
) -> Any:
    deadline = time.monotonic() + timeout
    response = None
    while time.monotonic() < deadline:
        response = action()
        if validate(response):
            return response
        time.sleep(1)
    return response


def _client(endpoint: str, region: str, profile: str) -> AOSSOpenSearch:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("endpoint must be an HTTPS URL")
    if parsed.path not in ("", "/") or parsed.port is not None:
        raise ValueError("endpoint must not include a path or explicit port")

    credentials = Session(profile=profile).get_credentials()
    if credentials is None:
        raise ValueError(f"AWS profile has no credentials: {profile}")
    auth = RequestsAWSV4SignerAuth(credentials, region, "aoss")
    return AOSSOpenSearch(
        hosts=[{"host": parsed.hostname, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20,
        timeout=30,
    )


def _metadata_checks(
    client: AOSSOpenSearch,
    recorder: Recorder,
    component: str,
    template: str,
    index: str,
) -> Dict[str, bool]:
    created = {"component": False, "template": False, "index": False}
    response = recorder.run(
        "cluster.put_component_template",
        lambda: client.cluster.put_component_template(
            name=component,
            body={
                "template": {
                    "mappings": {"properties": {"template_marker": {"type": "keyword"}}}
                }
            },
        ),
        _acknowledged,
    )
    created["component"] = response is not None
    recorder.run(
        "cluster.exists_component_template",
        lambda: client.cluster.exists_component_template(name=component),
        lambda value: value is True,
    )
    recorder.run(
        "cluster.get_component_template",
        lambda: client.cluster.get_component_template(name=component),
        lambda value: isinstance(value, dict)
        and len(value.get("component_templates", [])) == 1,
    )

    response = recorder.run(
        "indices.put_index_template",
        lambda: client.indices.put_index_template(
            name=template,
            body={
                "index_patterns": [f"{index.rsplit('-', 1)[0]}-*"],
                "composed_of": [component],
            },
        ),
        _acknowledged,
    )
    created["template"] = response is not None
    recorder.run(
        "indices.exists_index_template",
        lambda: client.indices.exists_index_template(name=template),
        lambda value: value is True,
    )
    recorder.run(
        "indices.get_index_template",
        lambda: client.indices.get_index_template(name=template),
        lambda value: isinstance(value, dict)
        and len(value.get("index_templates", [])) == 1,
    )
    recorder.run(
        "cat.templates",
        lambda: client.cat.templates(name=template, params={"format": "json"}),
        lambda value: isinstance(value, list) and len(value) == 1,
    )

    response = recorder.run(
        "indices.create",
        lambda: client.indices.create(index=index),
        _acknowledged,
    )
    created["index"] = response is not None
    recorder.run(
        "indices.exists",
        lambda: client.indices.exists(index=index),
        lambda value: value is True,
    )
    recorder.run(
        "indices.get",
        lambda: client.indices.get(index=index),
        lambda value: isinstance(value, dict) and index in value,
    )
    recorder.run(
        "indices.put_mapping",
        lambda: client.indices.put_mapping(
            index=index,
            body={
                "properties": {
                    "message": {"type": "text"},
                    "category": {"type": "keyword"},
                    "count": {"type": "integer"},
                }
            },
        ),
        _acknowledged,
    )
    recorder.run(
        "indices.get_mapping",
        lambda: client.indices.get_mapping(index=index),
        lambda value: isinstance(value, dict) and index in value,
    )
    recorder.run(
        "indices.get_settings",
        lambda: client.indices.get_settings(index=index),
        lambda value: isinstance(value, dict) and index in value,
    )
    recorder.run(
        "indices.resolve_index",
        lambda: client.indices.resolve_index(name=index),
        lambda value: isinstance(value, dict) and len(value.get("indices", [])) == 1,
    )
    recorder.run(
        "indices.analyze",
        lambda: client.indices.analyze(
            index=index,
            body={"analyzer": "standard", "text": "AOSS coverage test"},
        ),
        lambda value: isinstance(value, dict) and bool(value.get("tokens")),
    )
    recorder.run(
        "indices.validate_query",
        lambda: client.indices.validate_query(
            index=index,
            body={"query": {"match_all": {}}},
        ),
        lambda value: isinstance(value, dict) and value.get("valid") is True,
    )
    recorder.run(
        "cat.indices",
        lambda: client.cat.indices(index=index, params={"format": "json"}),
        lambda value: isinstance(value, list) and len(value) == 1,
    )
    return created


def _document_checks(
    client: AOSSOpenSearch,
    recorder: Recorder,
    index: str,
) -> None:
    documents = {
        "doc-1": {"message": "first document", "category": "alpha", "count": 1},
        "doc-2": {"message": "second document", "category": "beta", "count": 2},
    }
    recorder.run(
        "root.index",
        lambda: client.index(index=index, id="doc-1", body=documents["doc-1"]),
        lambda value: isinstance(value, dict)
        and value.get("result") in {"created", "updated"},
    )
    recorder.run(
        "root.create",
        lambda: client.create(index=index, id="doc-2", body=documents["doc-2"]),
        lambda value: isinstance(value, dict) and value.get("result") == "created",
    )
    recorder.run(
        "root.bulk",
        lambda: client.bulk(
            index=index,
            body=[
                {"index": {"_id": "doc-3"}},
                {"message": "third document", "category": "gamma", "count": 3},
                {"index": {"_id": "doc-4"}},
                {"message": "fourth document", "category": "delta", "count": 4},
            ],
        ),
        lambda value: isinstance(value, dict)
        and value.get("errors") is False
        and len(value.get("items", [])) == 2,
    )

    recorder.run(
        "root.count[eventual]",
        lambda: _wait_for(
            lambda: client.count(index=index),
            lambda value: isinstance(value, dict) and value.get("count", 0) >= 4,
        ),
        lambda value: isinstance(value, dict) and value.get("count", 0) >= 4,
    )
    recorder.run(
        "root.exists",
        lambda: client.exists(index=index, id="doc-1"),
        lambda value: value is True,
    )
    recorder.run(
        "root.exists_source",
        lambda: client.exists_source(index=index, id="doc-1"),
        lambda value: value is True,
    )
    recorder.run(
        "root.get",
        lambda: client.get(index=index, id="doc-1"),
        lambda value: isinstance(value, dict) and value.get("found") is True,
    )
    recorder.run(
        "root.get_source",
        lambda: client.get_source(index=index, id="doc-1"),
        lambda value: isinstance(value, dict)
        and value.get("message") == "first document",
    )
    recorder.run(
        "root.explain",
        lambda: client.explain(
            index=index,
            id="doc-1",
            body={"query": {"match_all": {}}},
        ),
        lambda value: isinstance(value, dict) and value.get("matched") is True,
    )
    recorder.run(
        "root.update",
        lambda: client.update(
            index=index,
            id="doc-1",
            body={"doc": {"count": 10}},
        ),
        lambda value: isinstance(value, dict) and value.get("result") == "updated",
    )
    recorder.run(
        "root.mget",
        lambda: client.mget(
            index=index,
            body={"ids": ["doc-1", "doc-2", "doc-3"]},
        ),
        lambda value: isinstance(value, dict) and len(value.get("docs", [])) == 3,
    )
    recorder.run(
        "root.search",
        lambda: client.search(index=index, body={"query": {"match_all": {}}}),
        lambda value: isinstance(value, dict)
        and len(value.get("hits", {}).get("hits", [])) >= 4,
    )
    recorder.run(
        "root.msearch",
        lambda: client.msearch(
            index=index,
            body=[{}, {"query": {"match_all": {}}}],
        ),
        lambda value: isinstance(value, dict) and len(value.get("responses", [])) == 1,
    )
    recorder.run(
        "root.field_caps",
        lambda: client.field_caps(
            index=index,
            params={"fields": "message,category,count"},
        ),
        lambda value: isinstance(value, dict) and "fields" in value,
    )
    recorder.run(
        "root.delete",
        lambda: client.delete(index=index, id="doc-2"),
        lambda value: isinstance(value, dict) and value.get("result") == "deleted",
    )


def _alias_and_pit_checks(
    client: AOSSOpenSearch,
    recorder: Recorder,
    index: str,
    alias: str,
) -> Optional[str]:
    recorder.run(
        "indices.put_alias",
        lambda: client.indices.put_alias(index=index, name=alias),
        _acknowledged,
    )
    recorder.run(
        "indices.exists_alias",
        lambda: client.indices.exists_alias(index=index, name=alias),
        lambda value: value is True,
    )
    recorder.run(
        "indices.get_alias",
        lambda: client.indices.get_alias(index=index, name=alias),
        lambda value: isinstance(value, dict) and index in value,
    )
    recorder.run(
        "cat.aliases",
        lambda: client.cat.aliases(name=alias, params={"format": "json"}),
        lambda value: isinstance(value, list) and len(value) == 1,
    )
    recorder.run(
        "indices.delete_alias",
        lambda: client.indices.delete_alias(index=index, name=alias),
        _acknowledged,
    )

    response = recorder.run(
        "root.create_pit",
        lambda: client.create_pit(index=index, params={"keep_alive": "1m"}),
        lambda value: isinstance(value, dict) and bool(value.get("pit_id")),
    )
    if not isinstance(response, dict):
        return None
    pit_id = response["pit_id"]
    recorder.run(
        "root.get_all_pits",
        client.get_all_pits,
        lambda value: isinstance(value, dict)
        and any(pit.get("pit_id") == pit_id for pit in value.get("pits", [])),
    )
    deleted = recorder.run(
        "root.delete_pit",
        lambda: client.delete_pit(body={"pit_id": [pit_id]}),
        lambda value: isinstance(value, dict)
        and any(
            pit.get("pit_id") == pit_id and pit.get("successful") is True
            for pit in value.get("pits", [])
        ),
    )
    return None if deleted is not None else pit_id


def _cleanup(
    client: AOSSOpenSearch,
    recorder: Recorder,
    created: Dict[str, bool],
    component: str,
    template: str,
    index: str,
    alias: str,
    pit_id: Optional[str],
) -> None:
    if pit_id is not None:
        recorder.run(
            "cleanup.delete_pit",
            lambda: client.delete_pit(body={"pit_id": [pit_id]}),
            _dict,
        )
    if created["index"]:
        if client.indices.exists_alias(index=index, name=alias):
            recorder.run(
                "cleanup.delete_alias",
                lambda: client.indices.delete_alias(index=index, name=alias),
                _acknowledged,
            )
        recorder.run(
            "cleanup.indices.delete",
            lambda: client.indices.delete(index=index),
            _acknowledged,
        )
        recorder.run(
            "cleanup.indices.absent",
            lambda: client.indices.exists(index=index),
            lambda value: value is False,
        )
    if created["template"]:
        recorder.run(
            "cleanup.indices.delete_index_template",
            lambda: client.indices.delete_index_template(name=template),
            _acknowledged,
        )
    if created["component"]:
        recorder.run(
            "cleanup.cluster.delete_component_template",
            lambda: client.cluster.delete_component_template(name=component),
            _acknowledged,
        )


def main() -> int:
    """Runs the live suite and returns nonzero when any check fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE", "default"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/aoss-live-smoke-report.json"),
    )
    args = parser.parse_args()

    prefix = f"aoss-py-live-{uuid.uuid4().hex[:12]}"
    component = f"{prefix}-component"
    template = f"{prefix}-template"
    index = f"{prefix}-index"
    alias = f"{prefix}-alias"
    recorder = Recorder()
    client = _client(args.endpoint, args.region, args.profile)
    created = {"component": False, "template": False, "index": False}
    pit_id: Optional[str] = None
    try:
        created = _metadata_checks(client, recorder, component, template, index)
        if created["index"]:
            _document_checks(client, recorder, index)
            pit_id = _alias_and_pit_checks(client, recorder, index, alias)
    finally:
        _cleanup(
            client,
            recorder,
            created,
            component,
            template,
            index,
            alias,
            pit_id,
        )
        client.close()

    recorder.skip(
        "snapshot.*",
        "requires a snapshot repository, KMS key, and cross-collection setup",
    )
    recorder.skip(
        "ingest/search_pipeline/plugin.*",
        "requires operation-specific processors, models, or external resources",
    )
    recorder.skip(
        "indices.put_settings",
        "requires a confirmed AOSS-supported mutable setting",
    )
    counts = {
        status: sum(result.status == status for result in recorder.results)
        for status in ("PASS", "FAIL", "SKIP")
    }
    report = {
        "target": urlparse(args.endpoint).hostname,
        "region": args.region,
        "profile": args.profile,
        "resource_prefix": prefix,
        "summary": counts,
        "results": [asdict(result) for result in recorder.results],
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"SUMMARY pass={counts['PASS']} fail={counts['FAIL']} "
        f"skip={counts['SKIP']} report={args.output}"
    )
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
