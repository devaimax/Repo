# import math
# import time
# import os
# import csv
# from prometheus_client import Gauge, start_http_server

# # تعريف المقياس
# execution_time_gauge = Gauge(
#     'factorial_execution_time_seconds',
#     'Execution time of factorial calculation',
#     ['service_name', 'node_name', 'container_id']
# )

# def run_fact(n: int, service_name, node_name, container_id):
#     start = time.perf_counter()
#     math.factorial(n)
#     end = time.perf_counter()
#     duration = end - start

#     # تحديث Prometheus
#     execution_time_gauge.labels(
#         service_name=service_name,
#         node_name=node_name,
#         container_id=container_id
#     ).set(duration)

#     # طباعة في اللوج
#     print(f"✅ {service_name} completed factorial({n}) in {duration:.4f}s")

#     # كتابة في CSV
#     with open("/app/results.csv", "a", newline="") as f:
#         writer = csv.writer(f)
#         writer.writerow([
#             time.strftime("%Y-%m-%d %H:%M:%S"),
#             service_name,
#             node_name,
#             container_id,
#             n,
#             f"{duration:.4f}"
#         ])

#     return duration


# if __name__ == "__main__":
#     # بدء السيرفر على المنفذ 8000
#     start_http_server(8000)

#     # تعريف metadata
#     service_name = os.getenv('SERVICE_NAME', 'fact_service')
#     node_name = os.getenv('NODE_NAME', 'unknown_node')
#     container_id = os.getenv('HOSTNAME', 'unknown_container')

#     n = int(os.getenv('N', 100000))  # القيمة الافتراضية 100k

#     # إنشاء ملف CSV مع الهيدر لو مش موجود
#     if not os.path.exists("/app/results.csv"):
#         with open("/app/results.csv", "w", newline="") as f:
#             writer = csv.writer(f)
#             writer.writerow(["timestamp", "service", "node", "container", "n", "duration_sec"])

#     print(f"🚀 Starting {service_name} on {node_name} (container={container_id}), n={n}")

#     while True:
#         run_fact(n, service_name, node_name, container_id)
#         time.sleep(60)



import math
import time
import os
import csv
from prometheus_client import Gauge, start_http_server

# تعريف المقياس لبروميثيوس
execution_time_gauge = Gauge(
    'factorial_execution_time_seconds',
    'Execution time of factorial calculation',
    ['service_name', 'node_name', 'container_id']
)

def run_fact(n, service_name, node_name, container_id):
    start = time.perf_counter()
    math.factorial(n)
    end = time.perf_counter()
    duration = end - start

    # تحديث Prometheus
    execution_time_gauge.labels(
        service_name=service_name,
        node_name=node_name,
        container_id=container_id
    ).set(duration)

    # طباعة في اللوج
    print(f"✅ {service_name} completed factorial({n}) in {duration:.4f}s")

    # كتابة في CSV
    with open("/app/results.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            service_name,
            node_name,
            container_id,
            n,
            f"{duration:.4f}"
        ])

    return duration


if __name__ == "__main__":
    # بدء خادم Prometheus على المنفذ 8000 مع 0.0.0.0
    start_http_server(8000, addr="0.0.0.0")

    service_name = os.getenv('SERVICE_NAME', 'fact_service')
    node_name = os.getenv('NODE_NAME', 'unknown_node')
    container_id = os.getenv('HOSTNAME', 'unknown_container')

    n = int(os.getenv('N', 100000))  # القيمة الافتراضية 100k

    # إنشاء ملف CSV مع الهيدر لو مش موجود
    if not os.path.exists("/app/results.csv"):
        with open("/app/results.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "service", "node", "container", "n", "duration_sec"])

    print(f"🚀 Starting {service_name} on {node_name} (container={container_id}), n={n}")

    while True:
        run_fact(n, service_name, node_name, container_id)
        time.sleep(60)
