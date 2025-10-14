#!/bin/bash
# Script: deploy_monitoring.sh
# الغرض: نشر حزمة Prometheus/Grafana كـ Docker Swarm stack مع إمكانية تبديل الوضع المحسّن.
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

STACK_NAME="monitor"
NETWORK_NAME="monitor-net"
CONFIG_NAME="prometheus_config"
CONFIG_ROOT=${CONFIG_ROOT:-.}
# If config files are not found in the requested root, fall back to the realistic scenario defaults
if [[ ! -f "${CONFIG_ROOT}/docker-compose.yml" ]]; then
  DEFAULT_ROOT="$SCRIPT_DIR/scenarios/realistic_5node/compose"
  if [[ -f "${DEFAULT_ROOT}/docker-compose.yml" ]]; then
    CONFIG_ROOT="$DEFAULT_ROOT"
  fi
fi
PROM_FILE="${CONFIG_ROOT}/prometheus.yml"
COMPOSE_ARGS=("-c" "${CONFIG_ROOT}/docker-compose.yml")
PROM_URL="http://localhost:9090/api/v1/targets"

if [[ "$1" == "--enhanced" ]]; then
  echo "⚙️ Using enhanced overrides (host networking + static targets)"
  PROM_FILE="${CONFIG_ROOT}/prometheus.enhanced.yml"
  COMPOSE_ARGS+=("-c" "${CONFIG_ROOT}/docker-compose.enhanced.yml")
fi

echo "🚀 [1/6] إنشاء الشبكة overlay ($NETWORK_NAME) إذا لم تكن موجودة..."
# تأكد من تجهيز شبكة overlay المستخدمة في المراقبة
docker network inspect $NETWORK_NAME >/dev/null 2>&1 || \
  docker network create --driver overlay --attachable $NETWORK_NAME

echo "🚀 [2/6] حذف أي Stack قديم ($STACK_NAME)..."
# حذف الستاك السابق لتفادي التعارض مع نشر جديد
docker stack rm $STACK_NAME || true
sleep 10

echo "🚀 [3/6] حذف config قديم ($CONFIG_NAME) إذا موجود..."
# إزالة Config سابق لأن Docker لا يسمح بتحديث المحتوى مباشرة
docker config rm $CONFIG_NAME || true

echo "🚀 [4/6] إنشاء config جديد لبروميثيوس ($PROM_FILE)..."
# إنشاء Config جديد باستخدام ملف إعداد Prometheus النشط
docker config create $CONFIG_NAME $PROM_FILE

echo "🚀 [5/6] نشر الـ Stack ($STACK_NAME)..."
docker stack deploy "${COMPOSE_ARGS[@]}" $STACK_NAME

echo "⏳ الانتظار 30 ثانية حتى تبدأ الخدمات..."
sleep 30

echo "🔍 [6/6] التحقق من حالة Targets من Prometheus..."
if ! command -v jq &> /dev/null; then
  echo "⚠️ jq غير مثبت، لن أستطيع تحليل JSON. ثبّت jq باستخدام:"
  echo "   sudo apt-get install jq -y   # على Ubuntu/Debian"
  echo "   sudo yum install jq -y       # على CentOS/RHEL"
  exit 0
fi

STATUS=$(curl -s $PROM_URL | jq -r '.data.activeTargets[] | "\(.labels.job): \(.health)"')

echo "📊 ملخص الحالة:"
echo "$STATUS" | while read line; do
  JOB=$(echo $line | cut -d: -f1)
  HEALTH=$(echo $line | cut -d: -f2 | xargs)
  if [[ "$HEALTH" == "up" ]]; then
    echo "✅ $JOB is UP"
  else
    echo "❌ $JOB is DOWN"
  fi
done

echo ""
echo "👉 افتح Prometheus: http://<manager-ip>:9090/targets"
echo "👉 افتح Grafana:    http://<manager-ip>:3000 (user: admin / pass: your_secure_password)"
