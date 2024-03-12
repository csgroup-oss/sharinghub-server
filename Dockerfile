FROM python:3.11-slim-bookworm as installer

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Generate python dependencies wheels
COPY . .
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels .[prod]

FROM python:3.11-slim-bookworm

ARG VERSION=latest

LABEL version=${VERSION}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH=$PATH:/home/app/.local/bin

RUN useradd -mrU -d /home/app -s /bin/bash app

RUN apt-get update && \
    apt-get install -y --no-install-recommends mailcap && \
    rm -rf /var/lib/apt/lists/*

USER app

WORKDIR /home/app

COPY --chown=app:app --from=installer /usr/src/app/wheels wheels

RUN pip install --user --no-cache-dir wheels/* && \
    rm -rf wheels

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
