# SharingHub Server

## Table of contents

- [Roadmap](#roadmap)
- [Setup](#setup)
- [Development](#development)
  - [Run with uvicorn](#run-with-uvicorn)
  - [Run with docker container](#run-with-docker-container)
  - [Run full stack with docker compose](#run-full-stack-with-docker-compose)
- [Production](#production)
  - [Create the Docker image](#create-the-docker-image)
  - [HELM](#helm)
- [Configuration](#configuration)

## Roadmap

The goal here is to establish a plan on the developments of SharingHub, with the different requirements for each release.

- **Release v0.1.0 (v0.1.X): MVP**

  The goal of this release is to implement the minimum set of features to have a functioning and cohesive platform. This version could be used for demonstrations and deployed as such, independently from the development one. Fixes can be added, but no new features implemented. Milestone [here](https://gitlab.si.c-s.fr/groups/space_applications/mlops-services/-/boards?milestone_title=v0.1.0).

- **Release v1.0.0 (v1.X.Y): Industrialized, first stable**

  After the v0.1.0, we will work on the industrialization of the SharingHub. It is important to refactor and improve the software architecture to create a robust base for future developments. We will also add here the QA tools and create the CI/CD pipelines. Small new features and bug fixes can be added after, as long as they do not overstep on the boundaries of the next release. Milestone [here](https://gitlab.si.c-s.fr/groups/space_applications/mlops-services/-/boards?milestone_title=v1.0.0).

- **Release v2.0.0 (v2.X.Y): Model-centered**

  The last set of features planned, with AI models capabilities. The goal is to be able to deploy and manage an inference service for models hosted on GitLab. A CLI tool can be developed as part of a "kit" for developers, to init models/datasets/others repositories, and help for the packaging of the models for deployment (Eg. command to generate a .joblib file for a scikit-learn model).

For compatibility with [SharingHub UI](https://gitlab.si.c-s.fr/space_applications/mlops-services/sharinghub-ui), a versioning scheme will be put in place. SharingHub UI will use this server, so it must be the one to constraint a version between the two. For a `x.y.z` version required by the front, it can connect to a `x.v.w` version of the back, with `v>=y`, and if `v == y`, then `w>=z`.

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
npm run build:minimal -- --catalogTitle="SharingHUB" --historyMode="hash" --pathPrefix="/ui"
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
docker build -t <registry-tag> .
# Example: docker build -t 643vlk6z.gra7.container-registry.ovh.net/space_applications/sharinghub:latest .

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

Deploy CS SharingHUB

```bash
# Install
cd deploy/helm

kubectl create secret generic sharinghub-oidc --from-literal client-id="b2e947651752fb3dc66480f647010f643700ef52a8888dcf6906b74be9c83a22" --from-literal client-secret="c138e76646cb648bd7881d003590d5bb0296ccdebfecbf57622b5f9156ab898b" --namespace sharinghub

helm install -n sharinghub sharinghub ./sharinghub -f values.yaml --create-namespace

# Update
helm upgrade -n sharinghub sharinghub ./sharinghub -f values.yaml
```

Deploy CNES SharingHub

```bash
# Install
cd deploy/helm

kubectl create secret generic sharinghub-oidc --from-literal client-id="b2e947651752fb3dc66480f647010f643700ef52a8888dcf6906b74be9c83a22" --from-literal client-secret="c138e76646cb648bd7881d003590d5bb0296ccdebfecbf57622b5f9156ab898b" --namespace sharinghub

helm install -n sharinghub sharinghub-cnes ./sharinghub -f values.cnes.yaml --create-namespace

# Update
helm upgrade -n sharinghub sharinghub-cnes ./sharinghub -f values.cnes.yaml
```

## Configuration

Please check [CONFIGURATION.md](./CONFIGURATION.md).
