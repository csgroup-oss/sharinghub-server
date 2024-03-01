# SharingHub Server

## Table of contents

- [Environment setup](#environment-setup)
- [Development](#development)
  - [Run with uvicorn](#run-with-uvicorn)
  - [Run with docker container](#run-with-docker-container)
- [Configuration](#configuration)

## Environment setup

Python 3.11 required.

Setup the environment:

```bash
python3 -mvenv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Development

### Run with uvicorn

We use `python-dotenv`, if a `.env` file is present it will be loaded.
You can copy the `.env.template` as `.env`, and complete it to have a quick env setup done.

Other configuration values may be overridden, the `.env` file is not git-tracked in this repo so don't hesitate to twist the configuration when you want to test things.

Then run the development server:

```bash
uvicorn app.main:app --reload
```

### Run with docker container

Build image

```bash
docker build . -t sharinghub-server:latest --build-arg VERSION=$(git rev-parse --short HEAD)
```

Use it

```bash
docker run --rm --env-file .env -p 8000:8000 --name sharinghub-server sharinghub-server:latest
```

You can check the API docs at [localhost:8000/docs](http://localhost:8000/docs).

## Configuration

Please check [CONFIGURATION.md](./CONFIGURATION.md).
