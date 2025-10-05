#!/bin/bash

STACK_NAME="monitor"
CONFIG_NAME="monitor_prometheus_config"
PROM_FILE="./prometheus.yml"
COMPOSE_ARGS=("-c" "docker-compose.yml")

if [[ "$1" == "--enhanced" ]]; then
  echo "⚙️ Using enhanced overrides (host networking + static targets)"
  PROM_FILE="./prometheus.enhanced.yml"
  COMPOSE_ARGS+=("-c" "docker-compose.enhanced.yml")
fi

echo "🚀 [1/4] حذف الـ stack القديم ($STACK_NAME) إن وجد..."
docker stack rm $STACK_NAME || true

echo "⏳ بانتظار إيقاف الخدمات..."
sleep 10

echo "🚀 [2/4] حذف الـ config القديم ($CONFIG_NAME) إن وجد..."
docker config rm $CONFIG_NAME || true

echo "🚀 [3/4] إنشاء config جديد من $PROM_FILE ..."
docker config create $CONFIG_NAME $PROM_FILE

echo "🚀 [4/4] نشر الـ stack ($STACK_NAME) باستخدام الملفات المحددة ..."
docker stack deploy "${COMPOSE_ARGS[@]}" $STACK_NAME

echo "✅ الانتهاء! تحقق من الخدمات عبر:"
echo "    docker service ls"
echo "وتحقق من Prometheus على: http://<manager-ip>:9090/targets"
