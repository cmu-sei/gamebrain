FROM python:3.8-bullseye

RUN pip install pipenv

WORKDIR /app

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY gamebrain gamebrain

CMD [ "uvicorn", "gamebrain.app:APP", "--host", "0.0.0.0", "--port", "8000"]
