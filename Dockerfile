# استخدم صورة Python أساسية
FROM python:3.11-slim

# تعيين مجلد العمل
WORKDIR /app

# نسخ ملفات المشروع
COPY server/ ./server/

# تثبيت الاعتماديات (إذا كان لديك ملف requirements.txt، استخدم الأمر التالي)
# RUN pip install --no-cache-dir -r server/requirements.txt
# وإلا، يمكنك تثبيت المكتبات الأساسية يدوياً
RUN pip install --no-cache-dir mcp-server

# تعيين متغيرات البيئة المطلوبة (إذا لزم الأمر)
# ENV COMPOSEBRIDGE_ROOT=/path/to/project

# أمر التشغيل لـ Glama (يجب أن يكون عبر stdio)
CMD ["python", "server/mcp_server.py"]