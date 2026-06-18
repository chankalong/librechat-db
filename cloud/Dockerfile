FROM python:3.12-slim-bookworm

WORKDIR /app

COPY cloud/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY json-to-excel.py /app/
COPY cloud/export-daily.sh cloud/export_collections.py cloud/upload-vercel-blob.py cloud/test-mongo.sh /app/
RUN sed -i 's/\r$//' /app/*.sh && chmod +x /app/export-daily.sh /app/test-mongo.sh

ENV EXPORT_ROOT=/data/export

CMD ["/app/export-daily.sh"]
