FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8-slim

COPY ./app /app

RUN pip install pymongo

EXPOSE 8008

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008", "--ssl-keyfile", "/certs/key.pem", "--ssl-certfile", "/certs/cert.pem"]
