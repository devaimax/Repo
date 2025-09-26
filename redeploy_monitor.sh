#!/bin/bash

STACK_NAME="monitor"
CONFIG_NAME="monitor_prometheus_config"
PROM_FILE="./prometheus.yml"
COMPOSE_FILE="./docker-compose.yml"

echo "🚀 [1/4] حذف الـ stack القديم ($STACK_NAME) إن وجد..."
docker stack rm $STACK_NAME || true

echo "⏳ بانتظار إيقاف الخدمات..."
sleep 10

echo "🚀 [2/4] حذف الـ config القديم ($CONFIG_NAME) إن وجد..."
docker config rm $CONFIG_NAME || true

echo "🚀 [3/4] إنشاء config جديد من $PROM_FILE ..."
docker config create $CONFIG_NAME $PROM_FILE

echo "🚀 [4/4] نشر الـ stack ($STACK_NAME) باستخدام $COMPOSE_FILE ..."
docker stack deploy -c $COMPOSE_FILE $STACK_NAME

echo "✅ الانتهاء! تحقق من الخدمات عبر:"
echo "    docker service ls"
echo "وتحقق من Prometheus على: http://<manager-ip>:9090/targets"
