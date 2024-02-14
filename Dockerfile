FROM amd64/python:3.11-alpine as docs

COPY requirements-docs.txt .

RUN pip install --no-cache-dir -r requirements-docs.txt

COPY docs/ /docs

WORKDIR /docs

RUN mkdocs build

FROM node:lts-alpine3.18 AS web-ui

WORKDIR /app

COPY web-ui/package*.json ./
RUN npm install

COPY web-ui/ ./
RUN npm run build:minimal -- --catalogTitle="SharingHub" --historyMode="hash" --pathPrefix="/ui"

FROM amd64/python:3.11-alpine as build

# Install runtime dependencies
RUN apk add \
        # Shapely
        g++ \
        geos-dev \
        # MIME TYPES
        mailcap

# Add non root user
RUN addgroup -S app && adduser -S app --ingroup app && chown app /home/app

USER app

ENV PATH=$PATH:/home/app/.local/bin

WORKDIR /home/app/

COPY --chown=app:app requirements.txt   .

USER root
RUN pip install --no-cache-dir -r requirements.txt

FROM build as test
ARG TEST_COMMAND=tox
ARG TEST_ENABLED=false
RUN [ "$TEST_ENABLED" = "false" ] && echo "skipping tests" || eval "$TEST_COMMAND"

FROM build as ship
WORKDIR /home/app/

ENV DOCS_PATH=/home/app/docs
ENV WEB_UI_PATH=/home/app/web-ui

COPY --chown=app:app --from=docs /docs/build/html docs/
COPY --chown=app:app --from=web-ui /app/dist web-ui/
COPY --chown=app:app app/ app/

USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]  # , "--log-level", "critical"]
