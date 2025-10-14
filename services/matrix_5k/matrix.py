# import numpy as np
# import time
# import os
# import csv
# from prometheus_client import Gauge, start_http_server

# execution_time_gauge = Gauge(
#     'matrix_multiplication_time_seconds',
#     'Execution time of matrix multiplication',
#     ['service_name', 'node_name', 'container_id']
# )

# def run_matrix(size, service_name, node_name, container_id):
#     A = np.random.rand(size, size)
#     B = np.random.rand(size, size)

#     start = time.perf_counter()
#     np.dot(A, B)
#     end = time.perf_counter()
#     duration = end - start

#     # تحديث Prometheus
#     execution_time_gauge.labels(
#         service_name=service_name,
#         node_name=node_name,
#         container_id=container_id
#     ).set(duration)

#     # طباعة في اللوج
#     print(f"✅ {service_name} completed matrix({size}x{size}) in {duration:.4f}s")

#     # كتابة في CSV
#     with open("/app/results.csv", "a", newline="") as f:
#         writer = csv.writer(f)
#         writer.writerow([
#             time.strftime("%Y-%m-%d %H:%M:%S"),
#             service_name,
#             node_name,
#             container_id,
#             size,
#             f"{duration:.4f}"
#         ])

#     return duration


# if __name__ == "__main__":
#     start_http_server(8000)

#     service_name = os.getenv('SERVICE_NAME', 'matrix_service')
#     node_name = os.getenv('NODE_NAME', 'unknown_node')
#     container_id = os.getenv('HOSTNAME', 'unknown_container')

#     size = int(os.getenv('MATRIX_SIZE', 4000))

#     if not os.path.exists("/app/results.csv"):
#         with open("/app/results.csv", "w", newline="") as f:
#             writer = csv.writer(f)
#             writer.writerow(["timestamp", "service", "node", "container", "matrix_size", "duration_sec"])

#     print(f"🚀 Starting {service_name} on {node_name} (container={container_id}), size={size}")

#     while True:
#         run_matrix(size, service_name, node_name, container_id)
#         time.sleep(60)





import numpy as np
import time
import os
import csv
from prometheus_client import Gauge, start_http_server
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    pass


# تعريف المقياس لبروميثيوس
execution_time_gauge = Gauge(
    'matrix_multiplication_time_seconds',
    'Execution time of matrix multiplication',
    ['service_name', 'node_name', 'container_id']
)

def run_matrix(size, service_name, node_name, container_id):
    A = np.random.rand(size, size)
    B = np.random.rand(size, size)

    start = time.perf_counter()
    np.dot(A, B)
    end = time.perf_counter()
    duration = end - start

    # تحديث Prometheus
    execution_time_gauge.labels(
        service_name=service_name,
        node_name=node_name,
        container_id=container_id
    ).set(duration)

    # طباعة في اللوج
    print(f"✅ {service_name} completed matrix({size}x{size}) in {duration:.4f}s")

    # كتابة في CSV
    with open("/app/results.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            service_name,
            node_name,
            container_id,
            size,
            f"{duration:.4f}"
        ])

    return duration


if __name__ == "__main__":
    # بدء خادم Prometheus على المنفذ 8000 مع 0.0.0.0 (مهم للـ overlay)
    start_http_server(8000, addr="0.0.0.0")

    size = int(os.getenv('MATRIX_SIZE', 5000))
    default_service_name = f"matrix_{size}"
    service_name = os.getenv('SERVICE_NAME', default_service_name)
    node_name = os.getenv('NODE_NAME', 'unknown_node')
    container_id = os.getenv('HOSTNAME', 'unknown_container')

    # إنشاء ملف CSV مع الهيدر لو مش موجود
    if not os.path.exists("/app/results.csv"):
        with open("/app/results.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "service", "node", "container", "matrix_size", "duration_sec"])

    print(f"🚀 Starting {service_name} on {node_name} (container={container_id}), size={size}")

    while True:
        run_matrix(size, service_name, node_name, container_id)
        time.sleep(60)
