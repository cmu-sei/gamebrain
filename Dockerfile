FROM python:3.8-bullseye

RUN apt update && apt install -y redis-server && rm -rf /var/lib/apt/lists/*
RUN pip install pipenv

WORKDIR /app

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY gamebrain .


CMD [ "uvicorn", "gamebrain.app:APP", "--ssl-keyfile=/app/certs/tls.key", "--ssl-certfile=/app/certs/tls.crt" ]
