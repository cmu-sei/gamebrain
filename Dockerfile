FROM python:3.10

WORKDIR /app

COPY requirements.txt ./
COPY initial_state.json ./
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY gamebrain gamebrain

CMD [ "uvicorn", "gamebrain.app:APP", "--host", "0.0.0.0", "--port", "8000"]
