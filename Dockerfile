FROM python:3.10-bullseye

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY gamebrain gamebrain

CMD [ "uvicorn", "gamebrain.app:APP", "--host", "0.0.0.0", "--port", "8000"]
