#!/bin/bash
# Script: redeploy_monitor.sh
# الغرض: إعادة نشر Stack المراقبة بسرعة باستخدام ملفات التكوين الحالية.

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

STACK_NAME="monitor"
CONFIG_NAME="monitor_prometheus_config"
CONFIG_ROOT=${CONFIG_ROOT:-.}
if [[ ! -f "${CONFIG_ROOT}/docker-compose.yml" ]]; then
  DEFAULT_ROOT="$SCRIPT_DIR/scenarios/realistic_5node/compose"
  if [[ -f "${DEFAULT_ROOT}/docker-compose.yml" ]]; then
    CONFIG_ROOT="$DEFAULT_ROOT"
  fi
fi
PROM_FILE="${CONFIG_ROOT}/prometheus.yml"
COMPOSE_ARGS=("-c" "${CONFIG_ROOT}/docker-compose.yml")

if [[ "$1" == "--enhanced" ]]; then
  echo "⚙️ Using enhanced overrides (host networking + static targets)"
  PROM_FILE="${CONFIG_ROOT}/prometheus.enhanced.yml"
  COMPOSE_ARGS+=("-c" "${CONFIG_ROOT}/docker-compose.enhanced.yml")
fi

echo "🚀 [1/4] حذف الـ stack القديم ($STACK_NAME) إن وجد..."
# إزالة الستاك الحالي قبل إعادة نشره
docker stack rm $STACK_NAME || true

echo "⏳ بانتظار إيقاف الخدمات..."
sleep 10

echo "🚀 [2/4] حذف الـ config القديم ($CONFIG_NAME) إن وجد..."
# حذف الـ config القديم لأن Docker يمنع تعديل المحتوى
docker config rm $CONFIG_NAME || true

echo "🚀 [3/4] إنشاء config جديد من $PROM_FILE ..."
# إعادة إنشاء Config من ملف Prometheus المحدد
docker config create $CONFIG_NAME $PROM_FILE

echo "🚀 [4/4] نشر الـ stack ($STACK_NAME) باستخدام الملفات المحددة ..."
# نشر الستاك باستخدام ملفات الـ compose النشطة
docker stack deploy "${COMPOSE_ARGS[@]}" $STACK_NAME

echo "✅ الانتهاء! تحقق من الخدمات عبر:"
echo "    docker service ls"
echo "وتحقق من Prometheus على: http://<manager-ip>:9090/targets"
