# Configuration

You can can configure the SharingHUB server through multiple sources:

- YAML file
- Environment variables

> Note: Environment variables always overwrite YAML values if they are set.

The YAML file path can be changed to point to another one with the environment variable `CONFIG_PATH`.

Content:

- [Variables](#variables)
  - [Config file path](#config-file-path)
  - [Server: debug](#server-debug)
  - [Server: log level](#server-log-level)
  - [Server: API prefix](#server-api-prefix)
  - [Server: allowed origins](#server-allowed-origins)
  - [Server: session secret key](#server-session-secret-key)
  - [Server: session max age](#server-session-max-age)
  - [Server: web ui path](#server-web-ui-path)
  - [Server: HTTP client timeout](#server-http-client-timeout)
  - [Server: enable cache](#server-enable-cache)
  - [Gitlab: URL](#gitlab-url)
  - [Gitlab: OAuth client id](#gitlab-oauth-client-id)
  - [Gitlab: OAuth client secret](#gitlab-oauth-client-secret)
  - [Gitlab: OAuth default token](#gitlab-oauth-default-token)
  - [JupyterLab: URL](#jupyterlab-url)
  - [STAC: root conf](#stac-root-conf)
  - [STAC: catalogs cache timeout](#stac-catalogs-cache-timeout)
  - [STAC: catalogs topics](#stac-catalogs-topics)
  - [STAC: projects cache timeout](#stac-projects-cache-timeout)
  - [STAC: projects assets rules](#stac-projects-assets-rules)
  - [STAC: projects assets release source format](#stac-projects-assets-release-source-format)

## Variables

> Note: relative paths are resolved against current working dir

### Config file path

- Type: path
- Default: `"<APP_DIR>/config.yaml"`
- Environment variable:
  - Name: `CONFIG_PATH`
  - Example value: `/path/to/file.yaml`

### Server: debug

- Type: boolean
- Default: `False`
- Environment variable:
  - Name: `DEBUG`
  - Values: `true`, `false`
- YAML:
  - Path: `server.debug`
  - Example value:
    ```yaml
    server:
      debug: true
    ```

### Server: log level

- Type: string
- Default: `"INFO"`, `"DEBUG"` if debug is true.
- Environment variable:
  - Name: `LOG_LEVEL`
  - Values: `CRITICAL`, `WARNING`, `INFO`, `DEBUG`
- YAML:
  - Path: `server.log-level`
  - Example value:
    ```yaml
    server:
      log-level: WARNING
    ```

### Server: API prefix

- Type: string
- Default: `""`
- Environment variable:
  - Name: `API_PREFIX`
  - Example value: `/my/prefix`
- YAML:
  - Path: `server.prefix`
  - Example value:
    ```yaml
    server:
      prefix: /my/prefix
    ```

### Server: allowed origins

- Type: list of string
- Default: `["http://localhost:8000", "https://radiantearth.github.io"]`
- Environment variable:
  - Name: `ALLOWED_ORIGINS`
  - Example value: `http://localhost:7000 http://localhost:8000 http://localhost:9000`
- YAML:
  - Path: `server.allowed-origins`
  - Example value:
    ```yaml
    server:
      allowed-origins:
        - http://localhost:7000
        - http://localhost:8000
        - http://localhost:9000
    ```

### Server: session secret key

- Type: string
- Default: random uuid
- Environment variable:
  - Name: `SESSION_SECRET_KEY`
  - Example value: `f785090f-0716-4ccb-89f0-afbd3c4a56d3`
- YAML:
  - Path: `server.session.secret-key`
  - Example value:
    ```yaml
    server:
      session:
        secret-key: f785090f-0716-4ccb-89f0-afbd3c4a56d3
    ```

### Server: session max age

- Type: floating number
- Default: `3600.0`
- Environment variable:
  - Name: `SESSION_MAX_AGE`
  - Example value: `7200.0`
- YAML:
  - Path: `server.session.max-age`
  - Example value:
    ```yaml
    server:
      session:
        max-age: 7200.0
    ```

### Server: web ui path

- Type: path
- Default: `"<PWD>/web-ui/dist"`
- Environment variable:
  - Name: `WEB_UI_PATH`
  - Example value: `web-ui/dist`
- YAML:
  - Path: `server.web-ui-path`
  - Example value:
    ```yaml
    server:
      web-ui-path: web-ui/dist
    ```

### Server: HTTP client timeout

- Type: floating number
- Default: `300.0`
- Environment variable:
  - Name: `HTTP_CLIENT_TIMEOUT`
  - Example value: `600.0`
- YAML:
  - Path: `server.http_client.timeout`
  - Example value:
    ```yaml
    server:
      http_client:
        timeout: 600.0
    ```

### Server: enable cache

- Type: boolean
- Default: `not DEBUG`
- Environment variable:
  - Name: `ENABLE_CACHE`
  - Values: `true`, `false`
- YAML:
  - Path: `server.cache`
  - Example value:
    ```yaml
    server:
      cache: true
    ```

### Gitlab: URL

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `GITLAB_URL`
  - Example value: `https://gitlab.example.com`
- YAML:
  - Path: `gitlab.url`
  - Example value:
  ```yaml
  gitlab:
    url: https://gitlab.example.com
  ```

### Gitlab: OAuth client id

- Type: string
- Default: read from env var
- Environment variable:
  - Name: `GITLAB_OAUTH_CLIENT_ID`
  - Example value: `<client-id>`
- YAML:
  - Path: `gitlab.oauth.client-id`
  - Example value:
  ```yaml
  gitlab:
    oauth:
      client-id: <client-id>
  ```

### Gitlab: OAuth client secret

- Type: string
- Default: read from env var
- Environment variable:
  - Name: `GITLAB_OAUTH_CLIENT_SECRET`
  - Example value: `<client-secret>`
- YAML:
  - Path: `gitlab.oauth.client-secret`
  - Example value:
  ```yaml
  gitlab:
    oauth:
      client-secret: <client-secret>
  ```

### Gitlab: OAuth default token

- Type: string
- Default: read from env var
- Environment variable:
  - Name: `GITLAB_OAUTH_DEFAULT_TOKEN`
  - Example value: `<default-token>`
- YAML:
  - Path: `gitlab.oauth.default-token`
  - Example value:
  ```yaml
  gitlab:
    oauth:
      default-token: <default-token>
  ```

### JupyterLab: URL

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `JUPYTERLAB_URL`
  - Example value: `https://nb.example.com`
- YAML:
  - Path: `jupyterlab.url`
  - Example value:
  ```yaml
  gitlab:
    url: https://nb.example.com
  ```

### STAC: root conf

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `stac.root`
  - Example value:
    ```yaml
    stac:
      root:
        id: my-gitlab-catalog
        title: My GitLab Catalog
        description: My description
        logo: URL
    ```

### STAC: catalogs cache timeout

- Type: floating number
- Default: `600.0`
- Environment variable:
  - Name: `STAC_CATALOGS_CACHE_TIMEOUT`
  - Example value: `30.0`
- YAML:
  - Path: `stac.catalogs.cache-timeout`
  - Example value:
    ```yaml
    stac:
      catalogs:
        cache-timeout: 30.0
    ```

### STAC: catalogs topics

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `stac.catalogs.topics`
  - Example value:
    ```yaml
    stac:
      catalogs:
        topics:
          my-topic:
            title: My Topic
            description: Custom topic
            default_type: item
    ```

### STAC: projects cache timeout

- Type: floating number
- Default: `300.0`
- Environment variable:
  - Name: `STAC_PROJECTS_CACHE_TIMEOUT`
  - Example value: `15.0`
- YAML:
  - Path: `stac.projects.cache-timeout`
  - Example value:
    ```yaml
    stac:
      projects:
        cache-timeout: 15.0
    ```

### STAC: projects assets rules

- Type: list of string
- Default: `["*.tif", "*.tiff", "*.geojson"]`
- Environment variable:
  - Name: `STAC_PROJECTS_ASSETS_RULES`
  - Example value: `*.tif *.tiff`
- YAML:
  - Path: `stac.projects.assets.rules`
  - Example value:
    ```yaml
    stac:
      projects:
        assets:
          rules:
            - "*.tif"
            - "*.tiff"
    ```

### STAC: projects assets release source format

- Type: string
- Default: `"zip"`
- Environment variable:
  - Name: `STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT`
  - Example value: `tar.gz`
- YAML:
  - Path: `stac.projects.assets.release-source-format`
  - Example value:
    ```yaml
    stac:
      projects:
        assets:
          release-source-format: tar.gz
    ```
