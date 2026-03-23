FROM python:3.11-slim

WORKDIR /code

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./entrypoint.sh /code/entrypoint.sh
RUN chmod +x /code/entrypoint.sh

COPY ./app /code/app

ENTRYPOINT ["/code/entrypoint.sh"]