FROM python:3.12-slim
WORKDIR /app
COPY services/prediction-service/main.py .
COPY services/prediction-service/classifier.py .
COPY ml/model.json ./model.json
ENV MODEL_PATH=/app/model.json
EXPOSE 8002
CMD ["python3", "main.py"]
