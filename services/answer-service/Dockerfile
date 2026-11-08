FROM python:3.12-slim
WORKDIR /app
COPY services/answer-service/main.py .
COPY services/answer-service/rag.py .
COPY services/answer-service/llm.py .
COPY docs/kb/ ./kb/
COPY flags.json .
ENV FLAGS_PATH=/app/flags.json
EXPOSE 8003
CMD ["python3", "main.py"]
