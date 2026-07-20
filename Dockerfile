FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11-slim

COPY ./app /app


#RUN mkdir -p /etc/pip && \
#    printf "[global]\ntimeout = 60\nindex-url = https://pypi-dmz.psi.ch/simple\n" > /etc/pip.conf

# Configure internal PyPI mirror for DMZ
COPY pip.conf /etc/pip.conf



RUN pip install pymongo pydantic-settings
RUN pip install --upgrade fastapi pydantic

EXPOSE 8008

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008", "--ssl-keyfile", "/etc/certificates/webserver.key", "--ssl-certfile", "/etc/certificates/webserver.pem"]
