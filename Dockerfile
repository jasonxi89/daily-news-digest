FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY crontab /app/crontab
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh && crontab /app/crontab

ENTRYPOINT ["./entrypoint.sh"]
