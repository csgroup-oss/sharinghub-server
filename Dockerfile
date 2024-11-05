FROM python:3.11-slim-bookworm as installer

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install Git for VCS versioning
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Generate python dependencies wheels
COPY . .
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels .[prod]

FROM python:3.11-slim-bookworm

ARG VERSION=latest

LABEL version=${VERSION}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && \
    apt-get install -y --no-install-recommends mailcap && \
    pip install --no-cache-dir --upgrade pip setuptools && \
    rm -rf /var/lib/apt/lists/*

COPY resources/gunicorn.conf.py /etc/gunicorn.conf.py
COPY --from=installer /usr/src/app/wheels /wheels

RUN pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

RUN groupadd -g 1000 app && \
    useradd -mr -d /home/app -s /bin/bash -u 1000 -g 1000 app

USER app

WORKDIR /home/app

EXPOSE 8000

CMD ["gunicorn", "--config", "/etc/gunicorn.conf.py"]
