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

Install the [pre-commit](https://pre-commit.com/) hooks:

```bash
pre-commit install --install-hooks
```

## Development

### Lint

The linting is managed by pre-commit, but you can run it with:

```bash
pre-commit run --all-files
```

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

## Copyright and License

Copyright 2024 `CS GROUP - France`

**SharingHub Server**  is an open source software, distributed under the Apache License 2.0. See the [`LICENSE`](./LICENSE) file for more information.
