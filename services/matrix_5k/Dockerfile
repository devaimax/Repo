# استخدم Python الرسمي (خفيف)
FROM python:3.11-slim

# إعداد بيئة العمل
WORKDIR /app

# نسخ ملفات الخدمة
COPY . .

# تثبيت المكتبات المطلوبة
RUN pip install --no-cache-dir prometheus-client numpy

# كشف المنفذ 8000
EXPOSE 8000

# الأمر الافتراضي
CMD ["python", "matrix.py"]
