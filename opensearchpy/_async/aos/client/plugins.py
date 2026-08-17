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

from typing import Any

from ...client.utils import NamespacedClient
from ..plugins.asynchronous_search import AsynchronousSearchClient
from ..plugins.flow_framework import FlowFrameworkClient
from ..plugins.geospatial import GeospatialClient
from ..plugins.ism import IsmClient
from ..plugins.knn import KnnClient
from ..plugins.ltr import LtrClient
from ..plugins.ml import MlClient
from ..plugins.neural import NeuralClient
from ..plugins.notifications import NotificationsClient
from ..plugins.observability import ObservabilityClient
from ..plugins.ppl import PplClient
from ..plugins.query import QueryClient
from ..plugins.replication import ReplicationClient
from ..plugins.rollups import RollupsClient
from ..plugins.search_relevance import SearchRelevanceClient
from ..plugins.security_analytics import SecurityAnalyticsClient
from ..plugins.sm import SmClient
from ..plugins.sql import SqlClient
from ..plugins.transforms import TransformsClient
from ..plugins.ubi import UbiClient


class PluginsClient(NamespacedClient):
    asynchronous_search: AsynchronousSearchClient
    flow_framework: FlowFrameworkClient
    geospatial: GeospatialClient
    ism: IsmClient
    knn: KnnClient
    ltr: LtrClient
    ml: MlClient
    neural: NeuralClient
    notifications: NotificationsClient
    observability: ObservabilityClient
    ppl: PplClient
    query: QueryClient
    replication: ReplicationClient
    rollups: RollupsClient
    search_relevance: SearchRelevanceClient
    security_analytics: SecurityAnalyticsClient
    sm: SmClient
    sql: SqlClient
    transforms: TransformsClient
    ubi: UbiClient

    def __init__(self, client: Any) -> None:
        super().__init__(client)
        self.asynchronous_search = AsynchronousSearchClient(client)
        self.flow_framework = FlowFrameworkClient(client)
        self.geospatial = GeospatialClient(client)
        self.ism = IsmClient(client)
        self.knn = KnnClient(client)
        self.ltr = LtrClient(client)
        self.ml = MlClient(client)
        self.neural = NeuralClient(client)
        self.notifications = NotificationsClient(client)
        self.observability = ObservabilityClient(client)
        self.ppl = PplClient(client)
        self.query = QueryClient(client)
        self.replication = ReplicationClient(client)
        self.rollups = RollupsClient(client)
        self.search_relevance = SearchRelevanceClient(client)
        self.security_analytics = SecurityAnalyticsClient(client)
        self.sm = SmClient(client)
        self.sql = SqlClient(client)
        self.transforms = TransformsClient(client)
        self.ubi = UbiClient(client)
