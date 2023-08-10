# GitLab2STAC

## Development

### Run with uvicorn

Setup the environment:

```bash
virtualenv -p python3.11 venv
# or python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt
```

Then run the development server:

```bash
uvicorn app.main:app --reload
```

### Run with docker container

Build image

```bash
docker build -t gitlab2stac:latest .
```

Use it

```bash
docker run --name gitlab2stac --rm \
    -p 8000:8000 \
    gitlab2stac:latest
```

You can check the API docs at [localhost:8000](http://localhost:8000/docs).

## Production

### Create the Docker image

We'll need to push the image to a docker registry.

```bash
# Login
docker login <your-registry>
# Example: docker login 643vlk6z.gra7.container-registry.ovh.net

# Tag the image for your registry
docker build -t <registry-tag> .
# Example: docker build -t 643vlk6z.gra7.container-registry.ovh.net/space_applications/gitlab2stac:latest .

# Push
docker push <registry-tag>
# Example: docker push 643vlk6z.gra7.container-registry.ovh.net/space_applications/gitlab2stac:latest
```

### HELM

Create a robot account in the harbor interface to access GeoJson Proxy Image

```bash
kubectl create namespace gitlab2stac

kubectl create secret docker-registry regcred --docker-username='robot$space_applications+p2.gitlab2stac' --docker-password='CphryzOE7A4XFnC1943APz0m1N8z9U6n' --docker-server='643vlk6z.gra7.container-registry.ovh.net' --namespace gitlab2stac
```

Deploy Gitlab2stac proxy

```bash
helm upgrade --install gitlab2stac ./deploy/helm/gitlab2stac --namespace gitlab2stac --values deploy/helm/values.yaml
```
