FROM python:3.11-slim

WORKDIR /app

# 1. نسخ ملف المتطلبات أولاً لتثبيت المكتبات
COPY server/requirements.txt ./server/

# 2. تثبيت المكتبات (هذا السطر مهم جداً)
RUN pip install --no-cache-dir -r server/requirements.txt

# 3. نسخ باقي كود السيرفر
COPY server/ ./server/

# 4. الأمر النهائي لتشغيل السيرفر
CMD ["python", "server/mcp_server.py"]