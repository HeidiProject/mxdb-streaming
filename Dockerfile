FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11-slim

COPY ./app /app

RUN pip install pymongo pydantic-settings
RUN pip install --upgrade fastapi pydantic

EXPOSE 8008

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008", "--ssl-keyfile", "/certs/certs.key", "--ssl-certfile", "/certs/certs.pem"]