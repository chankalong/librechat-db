FROM python:3.12-slim-bookworm

WORKDIR /app

COPY cloud/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY json-to-excel.py /app/
COPY cloud/export-daily.sh cloud/export-messages.sh cloud/export_collections.py cloud/upload-s3.py cloud/api.py cloud/storage.py cloud/start-api.sh cloud/test-mongo.sh /app/
RUN sed -i 's/\r$//' /app/*.sh && chmod +x /app/export-daily.sh /app/export-messages.sh /app/upload-s3.py /app/start-api.sh /app/test-mongo.sh

ENV EXPORT_ROOT=/data/export

CMD ["/app/export-daily.sh"]
