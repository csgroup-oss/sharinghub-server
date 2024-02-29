FROM python:3.11-alpine as installer

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install build dependencies
RUN apk add \
        # Shapely
        g++ \
        geos-dev

# Generate python dependencies wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels -r requirements.txt

FROM python:3.11-alpine

ARG VERSION=latest

LABEL version=${VERSION}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH=$PATH:/home/app/.local/bin

RUN addgroup -S app && adduser -S app -G app && \
    chown app /home/app

# Install runtime dependencies
RUN apk add \
        # Shapely
        geos-dev \
        # MIME TYPES
        mailcap

USER app

WORKDIR /home/app/

COPY --chown=app:app --from=installer /usr/src/app/wheels wheels

RUN python -m pip install --user --no-cache-dir wheels/* && \
    rm -rf wheels

COPY --chown=app:app app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers"]
