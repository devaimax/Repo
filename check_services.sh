#!/bin/bash

# الشبكة اللي فيها الخدمات
NETWORK="monitor-net"

# قائمة الخدمات + المنفذ
SERVICES=(
  "monitor_prometheus:9090"
  "monitor_grafana:3000"
  "monitor_cadvisor:8080"
  "monitor_node-exporter:9100"
  "monitor_fact_100k:8000"
  "monitor_fact_200k:8000"
  "monitor_fact_300k:8000"
  "monitor_fact_400k:8000"
  "monitor_fact_500k:8000"
  "monitor_matrix_4k:8000"
  "monitor_matrix_5k:8000"
  "monitor_matrix_6k:8000"
  "monitor_matrix_7k:8000"
  "monitor_matrix_8k:8000"
)

echo "🔍 Checking services in network: $NETWORK"
echo "=========================================="

for service in "${SERVICES[@]}"; do
  name=$(echo $service | cut -d: -f1)
  port=$(echo $service | cut -d: -f2)

  echo -n "➡️  $name ($port): "

  docker run --rm --network $NETWORK curlimages/curl:latest -s -o /dev/null -w "%{http_code}" http://$name:$port/metrics > tmp_status 2>/dev/null
  STATUS=$(cat tmp_status)

  if [ "$STATUS" == "200" ]; then
    echo "✅ UP"
  else
    echo "❌ DOWN (status=$STATUS)"
  fi

  rm -f tmp_status
done
