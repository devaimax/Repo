# FROM python:3.11-slim
# WORKDIR /app
# COPY matrix.py .
# RUN pip install prometheus-client numpy
# CMD ["python", "matrix.py"]



# # استخدم Python الرسمي (خفيف)
# FROM python:3.11-slim

# # إعداد بيئة العمل
# WORKDIR /app

# # نسخ ملفات الخدمة
# COPY . .

# # تثبيت المكتبات المطلوبة
# RUN pip install --no-cache-dir prometheus-client numpy

# # كشف المنفذ 8000
# EXPOSE 8000

# # الأمر الافتراضي
# CMD ["python", "matrix.py", "4000"]



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
