FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./

ENV DB_PATH=/data/irc_bot.db
RUN mkdir -p /data

CMD ["python", "-u", "bot.py"]
