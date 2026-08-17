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
# or in the OpenSearch API specification, and run `nox -rs generate_aos`. See DEVELOPER_GUIDE.md
# and https://github.com/opensearch-project/opensearch-api-specification for details.
# -----------------------------------------------------------------------------------------+

from .asynchronous_search import AsynchronousSearchClient
from .flow_framework import FlowFrameworkClient
from .geospatial import GeospatialClient
from .ism import IsmClient
from .knn import KnnClient
from .ltr import LtrClient
from .ml import MlClient
from .neural import NeuralClient
from .notifications import NotificationsClient
from .observability import ObservabilityClient
from .ppl import PplClient
from .query import QueryClient
from .replication import ReplicationClient
from .rollups import RollupsClient
from .search_relevance import SearchRelevanceClient
from .security_analytics import SecurityAnalyticsClient
from .sm import SmClient
from .sql import SqlClient
from .transforms import TransformsClient
from .ubi import UbiClient

__all__ = [
    "AsynchronousSearchClient",
    "FlowFrameworkClient",
    "GeospatialClient",
    "IsmClient",
    "KnnClient",
    "LtrClient",
    "MlClient",
    "NeuralClient",
    "NotificationsClient",
    "ObservabilityClient",
    "PplClient",
    "QueryClient",
    "ReplicationClient",
    "RollupsClient",
    "SearchRelevanceClient",
    "SecurityAnalyticsClient",
    "SmClient",
    "SqlClient",
    "TransformsClient",
    "UbiClient",
]
