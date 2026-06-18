FROM python:3.12-slim-bookworm

ARG MONGO_TOOLS_VERSION=100.10.0

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && curl -fsSL "https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian12-x86_64-${MONGO_TOOLS_VERSION}.tgz" \
    | tar -xz -C /usr/local/bin --strip-components=2 \
      "mongodb-database-tools-debian12-x86_64-${MONGO_TOOLS_VERSION}/bin/mongoexport" \
  && apt-get purge -y curl \
  && apt-get autoremove -y \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY cloud/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY json-to-excel.py /app/
COPY cloud/export-daily.sh cloud/export-messages.sh cloud/upload-s3.py cloud/api.py cloud/storage.py cloud/start-api.sh /app/
RUN sed -i 's/\r$//' /app/*.sh && chmod +x /app/export-daily.sh /app/export-messages.sh /app/upload-s3.py /app/start-api.sh

ENV EXPORT_ROOT=/data/export

CMD ["/app/export-daily.sh"]
