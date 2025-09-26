#!/bin/bash
set -e

DOCKER_USER="devaimax"

echo "🚀 [1/3] بناء الصور..."
for dir in services/*; do
  if [[ -d "$dir" && -f "$dir/Dockerfile" ]]; then
    svc=$(basename $dir)   # ياخذ اسم المجلد مثلاً factorial_100k
    echo "🔨 Building $svc from $dir..."
    docker build -t $DOCKER_USER/$svc:latest $dir
  fi
done

echo "🚀 [2/3] رفع الصور إلى Docker Hub..."
for dir in services/*; do
  if [[ -d "$dir" && -f "$dir/Dockerfile" ]]; then
    svc=$(basename $dir)
    echo "📤 Pushing $svc..."
    docker push $DOCKER_USER/$svc:latest
  fi
done

echo "🚀 [3/3] تحديث الخدمات في Swarm..."
for dir in services/*; do
  if [[ -d "$dir" && -f "$dir/Dockerfile" ]]; then
    svc=$(basename $dir)
    echo "♻️ Updating service monitor_$svc..."
    docker service update --force monitor_$svc || true
  fi
done

echo "✅ كله تمام!"
echo "👉 تحقق من Prometheus: http://<manager-ip>:9090/targets"
