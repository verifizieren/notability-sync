FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*
RUN chmod +x wait-for-it.sh

EXPOSE 5000

CMD ["./wait-for-it.sh", "db", "5432", "--", "python", "app.py"]