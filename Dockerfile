FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY fastapi_server_env.py ./
ENV PORT=8000
EXPOSE 8000
CMD ["uvicorn", "fastapi_server_env:app", "--host", "0.0.0.0", "--port", "8000"]
