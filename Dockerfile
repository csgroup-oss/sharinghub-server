FROM node:lts-alpine3.18 AS browser

WORKDIR /app

COPY browser/package*.json ./
RUN npm install

COPY browser/ ./
RUN npm run build:minimal -- --catalogTitle="GitLab2STAC Browser" --historyMode="hash" --pathPrefix="/browse"

FROM amd64/python:3.11-alpine as build

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
ENV BROWSER_PATH=/home/app/browser
COPY --chown=app:app --from=browser /app/dist browser/
COPY --chown=app:app app/            app/
COPY --chown=app:app resources/      resources/

USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]  # , "--log-level", "critical"]
