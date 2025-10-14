#!/bin/bash
set -e

echo "🚀 [1/3] بناء الصور..."

# Build images
docker build -t devaimax/factorial_100k:latest ./services/factorial_100k
docker build -t devaimax/factorial_200k:latest ./services/factorial_200k
docker build -t devaimax/factorial_300k:latest ./services/factorial_300k
docker build -t devaimax/factorial_400k:latest ./services/factorial_400k
docker build -t devaimax/factorial_500k:latest ./services/factorial_500k
docker build -t devaimax/matrix_4k:latest ./services/matrix_4k
docker build -t devaimax/matrix_5k:latest ./services/matrix_5k
docker build -t devaimax/matrix_6k:latest ./services/matrix_6k
docker build -t devaimax/matrix_7k:latest ./services/matrix_7k
docker build -t devaimax/matrix_8k:latest ./services/matrix_8k

echo "🚀 [2/3] رفع الصور إلى Docker Hub..."

docker push devaimax/factorial_100k:latest
docker push devaimax/factorial_200k:latest
docker push devaimax/factorial_300k:latest
docker push devaimax/factorial_400k:latest
docker push devaimax/factorial_500k:latest
docker push devaimax/matrix_4k:latest
docker push devaimax/matrix_5k:latest
docker push devaimax/matrix_6k:latest
docker push devaimax/matrix_7k:latest
docker push devaimax/matrix_8k:latest

echo "🚀 [3/3] تحديث الخدمات في Swarm..."

# Update running services with correct names
docker service update --force --image devaimax/factorial_100k:latest monitor_fact_100k || echo "❌ monitor_fact_100k not found"
docker service update --force --image devaimax/factorial_200k:latest monitor_fact_200k || echo "❌ monitor_fact_200k not found"
docker service update --force --image devaimax/factorial_300k:latest monitor_fact_300k || echo "❌ monitor_fact_300k not found"
docker service update --force --image devaimax/factorial_400k:latest monitor_fact_400k || echo "❌ monitor_fact_400k not found"
docker service update --force --image devaimax/factorial_500k:latest monitor_fact_500k || echo "❌ monitor_fact_500k not found"
docker service update --force --image devaimax/matrix_4k:latest monitor_matrix_4k || echo "❌ monitor_matrix_4k not found"
docker service update --force --image devaimax/matrix_5k:latest monitor_matrix_5k || echo "❌ monitor_matrix_5k not found"
docker service update --force --image devaimax/matrix_6k:latest monitor_matrix_6k || echo "❌ monitor_matrix_6k not found"
docker service update --force --image devaimax/matrix_7k:latest monitor_matrix_7k || echo "❌ monitor_matrix_7k not found"
docker service update --force --image devaimax/matrix_8k:latest monitor_matrix_8k || echo "❌ monitor_matrix_8k not found"

echo "✅ كله تمام!"
echo "👉 تحقق من Prometheus: http://<manager-ip>:9090/targets"
