import json
import pathlib

import js_json

import re

import pandas as pd

import csv

def main():
    files = pathlib.Path("dashboards").glob("mm-*")

    csv_data = []

    all_metrics = set()

    metric_function = js_json.wrap({})

    metric_function.mattermost_api_plugin_time_bucket = "pluginApiDuration"
    metric_function.mattermost_api_plugin_time_sum = "pluginApiDuration"
    metric_function.mattermost_api_plugin_time_count = "pluginApiDuration"

    metric_function.mattermost_websocket_broadcasts_total = "totalWebsocketBroadcastEvent"

    metric_function.mattermost_websocket_broadcasts_buffer_total = "websocketBroadcastBufferSize"

    metric_function.mattermost_websocket_event_total = "totalWebsocketEventCounter"

    metric_function.mattermost_login_logins_total = "totalLoginsCounter"

    metric_function.mattermost_db_store_time_count = "totalStoreMethodDuration"
    metric_function.mattermost_db_store_time_sum = "totalStoreMethodDuration"
    metric_function.mattermost_db_store_time_bucket = "totalStoreMethodDuration"

    metric_function.mattermost_http_websockets_total = "webSocketBroadcastUsersRegistered"

    metric_function.mattermost_db_replica_lag_time = "replicaLagTime"

    metric_function.mattermost_db_master_connections_total = "totalMasterDbConnections"

    metric_function.mattermost_db_read_replica_connections_total = "totalReadReplicaDbConnections"

    metric_function.mattermost_cluster_cluster_health_score = "clusterHealthScore"

    metric_function.mattermost_login_logins_fail_total = "totalLoginsFailCounter"

    metric_function.mattermost_post_emails_sent_total = "totalPostSentEmailCounter"

    metric_function.mattermost_post_pushes_sent_total = "totalPostSentPushCounter"

    metric_function.mattermost_post_file_attachments_total = "totalPostFileAttachmentCounter"

    metric_function.mattermost_search_posts_searches_total = "totalPostsSearchCounter"

    metric_function.mattermost_search_posts_searches_duration_seconds_sum = "totalPostsSearchDuration"

    metric_function.mattermost_http_requests_total = "totalHttpRequestCounter"

    metric_function.mattermost_cluster_cluster_requests_total = "totalClusterRequestCounter"

    metric_function.mattermost_cluster_event_type_totals = "totalClusterEventTypesCounter"

    metric_function.mattermost_cache_etag_miss_total = "totalCacheEtagMissCounter"
    metric_function.mattermost_cache_etag_hit_total = "totalCacheEtagHitCounter"

    metric_function.mattermost_cache_mem_miss_total = "totalCacheMemMissCounter"

    metric_function.mattermost_cache_mem_hit_total="totalCacheMemHitCounter"

    metric_function.mattermost_process_resident_memory_bytes="residentMemoryBytes"

    metric_function.mattermost_process_virtual_memory_bytes="processVirtualMemoryBytes"

    metric_function.mattermost_process_open_fds="openFileDescriptors"

    metric_function.mattermost_process_cpu_seconds_total="totalProcessCPUSeconds"

    metric_function.mattermost_post_total="totalPostCounter"

    metric_function.mattermost_http_errors_total="totalHttpErrorCounter"

    metric_function.mattermost_http_websockets_total="webSocketBroadcastUsersRegistered"

    metric_function.mattermost_db_master_connections_total="totalMasterDbConnections"

    metric_function.mattermost_http_errors_total="totalHttpErrorCounter"

    metric_function.mattermost_http_request_duration_seconds_sum="httpRequestDuration"

    metric_function.mattermost_db_master_connections_total="totalMasterDbConnections"

    metric_function.mattermost_cluster_cluster_request_duration_seconds="totalClusterRequestDuration"

    metric_function.mattermost_db_read_replica_connections_total="totalReadReplicaDbConnections"

    for file in files:
        print("==================================================================================\nfile:", file)

        dashboard = js_json.wrap(json.load(open(file)))

        # print("dashboard:",dashboard)

        for panel in dashboard.panels:
            print("-------------------------\npannel:", panel.title)

            if panel.targets:
                for target in panel.targets:

                    print("target:", target)

                    regex = re.compile("(mattermost_[a-zA-Z0-9_]+)|[{\)]")

                    matches = set(regex.findall(target.expr))

                    print("matches:",matches)

                    for match in matches:
                        if match:

                            csv_data.append({
                                "dashboard": dashboard.title,
                                "panel": panel.title,
                                "metric_name": ("*" if match in all_metrics else "") + match,
                                "expr": target.expr,
                            })

                            all_metrics.add(match)

    df = pd.DataFrame(data=csv_data)
    print("df:", df)

    df.to_csv("mattermost_metrics.csv", quoting=csv.QUOTE_NONNUMERIC, sep="\t")

if __name__ == "__main__":
    main()