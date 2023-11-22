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
  - [Server: request timeout](#server-request-timeout)
  - [Server: web ui path](#server-web-ui-path)
  - [Server: enable cache](#server-enable-cache)
  - [Remotes](#remotes)
  - [OAuth: clients ids](#oauth-clients-ids)
  - [OAuth: clients secrets](#oauth-clients-secrets)
  - [Catalog: cache timeout](#catalog-cache-timeout)
  - [Catalog: topics](#catalog-topics)
  - [Project: cache timeout](#project-cache-timeout)
  - [Project: assets rules](#project-assets-rules)
  - [Project: assets release source format](#project-assets-release-source-format)

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

### Server: request timeout

- Type: floating number
- Default: `300.0`
- Environment variable:
  - Name: `REQUEST_TIMEOUT`
  - Example value: `600.0`
- YAML:
  - Path: `server.request.timeout`
  - Example value:
    ```yaml
    server:
      request:
        timeout: 600.0
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

### Remotes

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `remotes`
  - Example value:
  ```yaml
  remotes:
    gitlab-example:
      url: https://gitlab.example.com
      title: GitLab
      description: Original GitLab site.
      oauth:
        server_metadata_url: https://gitlab.example.com/.well-known/openid-configuration
  ```

### OAuth: clients ids

- Type: mapping of strings
- Help: keys must be remote key in [Remotes](#remotes) config.
- Environment variable:
  - Name: `OAUTH_CLIENTS_IDS`
  - Example value: `gitlab-cs:<client-id-1>;gitlab-cloud-cs:<client-id-2>`
- YAML:
  - Path: `remotes.<remote>.oauth.client_id`
  - Example value:
  ```yaml
  remotes:
    gitlab-example:
      oauth:
        client_id: <client-id>
  ```

### OAuth: clients secrets

- Type: mapping of strings
- Environment variable:
  - Name: `OAUTH_CLIENTS_SECRETS`
  - Example value: `gitlab-example:<client-secret-1>;gitlab-example-2:<client-secret-2>`
- YAML:
  - Path: `remotes.<remote>.oauth.client_secret`
  - Example value:
  ```yaml
  remotes:
    gitlab-example:
      oauth:
        client_secret: <client-secret>
  ```

### Catalog: cache timeout

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

### Catalog: topics

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

### Project: cache timeout

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

### Project: assets rules

- Type: list of string
- Default: `["*.tif", "*.tiff", "*.geojson"]`
- Environment variable:
  - Name: `ASSETS_RULES`
  - Example value: `*.tif *.tiff`
- YAML:
  - Path: `projects.assets.rules`
  - Example value:
    ```yaml
    projects:
      assets:
        rules:
          - "*.tif"
          - "*.tiff"
    ```

### Project: assets release source format

- Type: string
- Default: `"zip"`
- Environment variable:
  - Name: `RELEASE_SOURCE_FORMAT`
  - Example value: `tar.gz`
- YAML:
  - Path: `projects.assets.release-source-format`
  - Example value:
    ```yaml
    projects:
      assets:
        release-source-format: tar.gz
    ```
