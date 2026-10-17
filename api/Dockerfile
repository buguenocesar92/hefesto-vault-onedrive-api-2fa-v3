FROM python:3.13-slim
WORKDIR /app
COPY server.py /app/server.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
EXPOSE 8081
CMD ["python", "/app/server.py"]
