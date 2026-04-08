FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./

RUN date -u +'%Y-%m-%d_%H-%M' > version.txt

CMD ["python", "-u", "bot.py"]
