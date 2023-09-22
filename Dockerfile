FROM python:3.10

WORKDIR /app

COPY settings.yaml ./
COPY requirements.txt ./
COPY initial_state.json ./
RUN pip install --no-cache-dir --upgrade pip --root-user-action=ignore
RUN pip install --no-cache-dir -r requirements.txt --root-user-action=ignore

COPY gamebrain gamebrain

CMD [ "uvicorn", "gamebrain.app:APP", "--host", "0.0.0.0", "--port", "8000"]

LABEL org.opencontainers.image.source=https://github.com/cmu-sei/gamebrain

