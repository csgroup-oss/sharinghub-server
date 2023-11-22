# SharingHub Server

## Table of contents

- [Setup](#setup)
- [Development](#development)
  - [Run with uvicorn](#run-with-uvicorn)
  - [Run with docker container](#run-with-docker-container)
  - [Run full stack with docker compose](#run-full-stack-with-docker-compose)
- [Production](#production)
  - [Create the Docker image](#create-the-docker-image)
  - [HELM](#helm)
- [Configuration](#configuration)

## Setup

You will need first to update the submodules.

```bash
git submodule init
git submodule update
```

## Development

### Run with uvicorn

Setup the environment:

```bash
virtualenv -p python3.11 venv
# or python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt

# Build Web UI static files
cd web-ui
npm install
npm run build:minimal -- --catalogTitle="SharingHUB" --gitlabUrl="https://gitlab.si.c-s.fr" --historyMode="hash" --pathPrefix="/ui"
```

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
docker build -t sharinghub:latest .
```

Use it

```bash
docker run --name sharinghub --rm \
    -p 8000:8000 \
    sharinghub:latest
```

You can check the API docs at [localhost:8000](http://localhost:8000/docs).

### Run full stack with docker compose

If you want to run the server and the web UI, you can use docker compose.

First, build your images:

```bash
make build
```

Then you can run them:

```bash
make run
```

## Production

### Create the Docker image

We'll need to push the image to a docker registry.

```bash
# Login
docker login <your-registry>
# Example: docker login 643vlk6z.gra7.container-registry.ovh.net

# Tag the image for your registry
docker build --build-arg gitlabUrl="<target-gitlab>" -t <registry-tag> .
# Example: docker build --build-arg gitlabUrl="https://gitlab.si.c-s.fr" -t 643vlk6z.gra7.container-registry.ovh.net/space_applications/sharinghub:latest .

# Push
docker push <registry-tag>
# Example: docker push 643vlk6z.gra7.container-registry.ovh.net/space_applications/sharinghub:latest
```

### HELM

Create a robot account in the harbor interface to access GeoJson Proxy Image

```bash
kubectl create namespace sharinghub

kubectl create secret docker-registry regcred --docker-username='robot$space_applications+p2.gitlab2stac' --docker-password='CphryzOE7A4XFnC1943APz0m1N8z9U6n' --docker-server='643vlk6z.gra7.container-registry.ovh.net' --namespace sharinghub
```

Deploy SharingHUB

```bash
# Install
cd deploy/helm
helm install -n sharinghub sharinghub ./sharinghub -f values.yaml --create-namespace
kubectl create secret generic sharinghub-oidc --from-literal clients-ids="gitlab-cs:b2e947651752fb3dc66480f647010f643700ef52a8888dcf6906b74be9c83a22" --from-literal clients-secrets="gitlab-cs:c138e76646cb648bd7881d003590d5bb0296ccdebfecbf57622b5f9156ab898b" --namespace sharinghub

# Update
helm upgrade -n sharinghub sharinghub ./sharinghub -f values.yaml
```

## Configuration

Please check [CONFIGURATION.md](./CONFIGURATION.md).
