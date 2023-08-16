# GitLab2STAC

## Setup

You will need first to update the submodules.

```bash
git submodule init
git submodule update
```

## Configuration

You can can configure Gitlab2STAC service through multiple sources:

- YAML file
- Environment variables

> Note: Environment variables always overwrite YAML values if they are set.

The YAML file path can be changed to point to another one with the environment variable `CONFIG_PATH`.

### Variables

> Note: relative paths are resolved against current working dir

#### Config file path

- Type: path
- Default: `"<APP_DIR>/config.yaml"`
- Environment variable:
  - Name: `CONFIG_PATH`
  - Example value: `/path/to/file.yaml`

#### Debug

- Type: boolean
- Default: `False`
- Environment variable:
  - Name: `DEBUG`
  - Values: `true`, `false`
- YAML:
  - Path: `debug`
  - Example values:
    ```yaml
    debug: true
    # OR
    debug: false
    ```

#### Log level

- Type: string
- Default: `"INFO"`, `"DEBUG"` if debug is true.
- Environment variable:
  - Name: `LOG_LEVEL`
  - Values: `CRITICAL`, `WARNING`, `INFO`, `DEBUG`
- YAML:
  - Path: `log-level`
  - Example value:
    ```yaml
    log-level: WARNING
    ```

#### API prefix

- Type: string
- Default: `""`
- Environment variable:
  - Name: `API_PREFIX`
  - Example value: `/my/prefix`
- YAML:
  - Path: `api-prefix`
  - Example value:
    ```yaml
    api-prefix: /my/prefix
    ```

#### Allowed origins

- Type: list of string
- Default: `["http://localhost:8000", "https://radiantearth.github.io"]`
- Environment variable:
  - Name: `ALLOWED_ORIGINS`
  - Example value: `http://localhost:7000 http://localhost:8000 http://localhost:9000`
- YAML:
  - Path: `allowed-origins`
  - Example value:
    ```yaml
    allowed-origins:
      - http://localhost:7000
      - http://localhost:8000
      - http://localhost:9000
    ```

#### Browser path

- Type: path
- Default: `"<PWD>/browser/dist"`
- Environment variable:
  - Name: `BROWSER_PATH`
  - Example value: `browser/dist`
- YAML:
  - Path: `browser-path`
  - Example value:
    ```yaml
    browser-path: browser/dist
    ```

#### Enable cache

- Type: boolean
- Default: `not DEBUG`
- Environment variable:
  - Name: `ENABLE_CACHE`
  - Values: `true`, `false`
- YAML:
  - Path: `cache`
  - Example values:
    ```yaml
    cache: true
    # OR
    cache: false
    ```

#### Remotes

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `remotes`
  - Example value:
  ```yaml
  remotes:
    gitlab.com:
      title: GitLab
      description: Original GitLab site.
  ```

#### Catalog: cache timeout

- Type: floating number
- Default: `600.0`
- Environment variable:
  - Name: `CATALOG_CACHE_TIMEOUT`
  - Example value: `30.0`
- YAML:
  - Path: `catalogs.cache-timeout`
  - Example value:
    ```yaml
    catalogs:
        cache-timeout: 30.0
    ```

#### Catalog: per page items

- Type: integer number
- Default: `12`
- Environment variable:
  - Name: `CATALOG_PER_PAGE`
  - Example value: `10`
- YAML:
  - Path: `catalogs.per-page`
  - Example value:
    ```yaml
    catalogs:
        per-page: 10
    ```

#### Catalog: topics

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `catalogs.topics`
  - Example value:
    ```yaml
    catalogs:
      topics:
        my-topic:
          title: My Topic
          description: Custom topic
          default_type: item
    ```

#### Project: cache timeout

- Type: floating number
- Default: `300.0`
- Environment variable:
  - Name: `PROJECT_CACHE_TIMEOUT`
  - Example value: `15.0`
- YAML:
  - Path: `projects.cache-timeout`
  - Example value:
    ```yaml
    projects:
        cache-timeout: 15.0
    ```

#### Assets rules

- Type: list of string
- Default: `["*.tif", "*.tiff", "*.geojson"]`
- Environment variable:
  - Name: `ASSETS_RULES`
  - Example value: `*.tif *.tiff`
- YAML:
  - Path: `assets-rules`
  - Example value:
    ```yaml
    assets-rules:
      - "*.tif"
      - "*.tiff"
    ```

#### Release source format

- Type: string
- Default: `"zip"`
- Environment variable:
  - Name: `RELEASE_SOURCE_FORMAT`
  - Example value: `tar.gz`
- YAML:
  - Path: `release-source-format`
  - Example value:
    ```yaml
    release-source-format: tar.gz
    ```

## Development

### Run with uvicorn

Setup the environment:

```bash
virtualenv -p python3.11 venv
# or python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt

# Build browser static files
cd browser
npm install
RUN npm run build:minimal -- --catalogTitle="GitLab2STAC Browser" --gitlabUrl="https://gitlab.si.c-s.fr" --historyMode="hash" --pathPrefix="/browse"
```

We use `python-dotenv`, if a `.env` file is present it will be loaded. We can use it to enable debug mode, with:

```bash
DEBUG=true
```

Other configuration values may be overridden, the `.env` file is not git-tracked in this repo so don't hesitate to twist the configuration when you want to test things.

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
docker build --build-arg gitlabUrl="<target-gitlab>" -t <registry-tag> .
# Example: docker build --build-arg gitlabUrl="https://gitlab.si.c-s.fr" -t 643vlk6z.gra7.container-registry.ovh.net/space_applications/gitlab2stac:latest .

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
