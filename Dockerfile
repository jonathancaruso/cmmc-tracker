FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directories for persistent data
RUN mkdir -p /data/uploads

# Symlink so app finds them
ENV DB_PATH=/data/cmmc.db
ENV UPLOAD_PATH=/data/uploads

EXPOSE 3300

CMD ["python", "app.py"]
