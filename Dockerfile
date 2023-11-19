FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11-slim

COPY ./app /app

COPY requirements .

RUN pip install -r requirements.txt

EXPOSE 8008

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008", "--ssl-keyfile", "/certs/key.pem", "--ssl-certfile", "/certs/cert.pem"]
