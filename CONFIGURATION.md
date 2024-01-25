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
  - [Server: docs path](#server-docs-path)
  - [Server: HTTP client timeout](#server-http-client-timeout)
  - [Server: enable cache](#server-enable-cache)
  - [Gitlab: URL](#gitlab-url)
  - [Gitlab: OAuth client id](#gitlab-oauth-client-id)
  - [Gitlab: OAuth client secret](#gitlab-oauth-client-secret)
  - [Gitlab: OAuth default token](#gitlab-oauth-default-token)
  - [Gitlab: ignore topics](#gitlab-ignore-topics)
  - [JupyterLab: URL](#jupyterlab-url)
  - [S3: enable](#s3-enable)
  - [S3: bucket](#s3-bucket)
  - [S3: access key](#s3-access-key)
  - [S3: secret key](#s3-secret-key)
  - [S3: region](#s3-region)
  - [S3: endpoint url](#s3-endpoint-url)
  - [S3: presigned expiration](#s3-presigned-expiration)
  - [S3: upload chunk size](#s3-upload-chunk-size)
  - [STAC: root conf](#stac-root-conf)
  - [STAC: categories page default size](#stac-categories-page-default-size)
  - [STAC: categories](#stac-categories)
  - [STAC: projects cache timeout](#stac-projects-cache-timeout)
  - [STAC: projects assets rules](#stac-projects-assets-rules)
  - [STAC: projects assets release source format](#stac-projects-assets-release-source-format)
  - [STAC: projects cache timeout](#stac-projects-cache-timeout-1)
  - [TAGS: sections](#tags-sections)
  - [FRONT-CONFIG: external urls](#front-config-external-urls)
  - [FRONT-CONFIG: visitor alert message](#front-config-visitor-alert-message)

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
  - Example value: `<secret key>`
- YAML:
  - Path: `server.session.secret-key`
  - Example value:
    ```yaml
    server:
      session:
        secret-key: <secret key>
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

### Server: docs path

- Type: path
- Default: `"<PWD>/docs"`
- Environment variable:
  - Name: `DOCS_PATH`
  - Example value: `docs/`
- YAML:
  - Path: `server.docs-path`
  - Example value:
    ```yaml
    server:
      docs-path: docs/
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

### Gitlab: ignore topics

- Type: list of string
- Default: `[]`
- Environment variable:
  - Name: `GITLAB_IGNORE_TOPICS`
  - Example value: `gitlab-ci devops`
- YAML:
  - Path: `gitlab.ignore.topics`
  - Example value:
    ```yaml
    gitlab:
      ignore:
        topics:
          - "gitlab-ci"
          - "devops"
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

### S3: enable

- Type: boolean
- Default: `False`
- Environment variable:
  - Name: `S3_ENABLE`
  - Values: `true`, `false`
- YAML:
  - Path: `s3.enable`
  - Example value:
    ```yaml
    s3:
      enable: true
    ```

### S3: bucket

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `S3_BUCKET`
  - Example value: `gitlab`
- YAML:
  - Path: `s3.bucket`
  - Example value:
  ```yaml
  s3:
    bucket: gitlab
  ```

### S3: access key

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `S3_ACCESS_KEY`
  - Example value: `<access-key>`
- YAML:
  - Path: `s3.access-key`
  - Example value:
  ```yaml
  s3:
    access-key: <access-key>
  ```

### S3: secret key

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `S3_SECRET_KEY`
  - Example value: `<secret-key>`
- YAML:
  - Path: `s3.secret-key`
  - Example value:
  ```yaml
  s3:
    secret-key: <secret-key>
  ```

### S3: region

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `S3_REGION_NAME`
  - Example value: `test`
- YAML:
  - Path: `s3.region`
  - Example value:
  ```yaml
  s3:
    region: test
  ```

### S3: endpoint url

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `S3_ENDPOINT_URL`
  - Example value: `http://127.0.0.1:9000`
- YAML:
  - Path: `s3.endpoint`
  - Example value:
  ```yaml
  s3:
    endpoint: "http://127.0.0.1:9000"
  ```

### S3: presigned expiration

- Type: integer number
- Default: `3600`
- Environment variable:
  - Name: `S3_PRESIGNED_EXPIRATION`
  - Example value: `1200`
- YAML:
  - Path: `s3.presigned-expiration`
  - Example value:
    ```yaml
    s3:
      presigned-expiration: 1200
    ```

### S3: upload chunk size

- Type: integer number
- Default: `6000000`
- Environment variable:
  - Name: `S3_UPLOAD_CHUNK_SIZE`
  - Example value: `300000`
- YAML:
  - Path: `s3.upload-chunk-size`
  - Example value:
    ```yaml
    s3:
      upload-chunk-size: 300000
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

### STAC: categories page default size

- Type: integer number
- Default: `12`
- Environment variable:
  - Name: `STAC_CATEGORIES_PAGE_DEFAULT_SIZE`
  - Example value: `20`
- YAML:
  - Path: `stac.categories.cache-timeout`
  - Example value:
    ```yaml
    stac:
      categories:
        page-size: 20
    ```

### STAC: categories

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `stac.categories.definitions`
  - Example value:
    ```yaml
    stac:
      categories:
        definitions:
          my-category:
            title: My Category
            description: Custom category
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

### STAC: projects cache timeout

- Type: floating number
- Default: `180.0`
- Environment variable:
  - Name: `STAC_SEARCH_CACHE_TIMEOUT`
  - Example value: `15.0`
- YAML:
  - Path: `stac.search.cache-timeout`
  - Example value:
    ```yaml
    stac:
      search:
        cache-timeout: 15.0
    ```

### TAGS: sections

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `tags`
- Example value:
  ```yaml
  tags:
    gitlab:
      minimum_count: 1
    sections:
      - name: "Computer Vision"
        enabled_for:
          - ai-model
          - dataset
          - processor
          - challenge
        keywords:
          - "Image qualification"
          - "Object detection"
          - "Image segmentation"
          - "Mask generation"
  ```

### FRONT-CONFIG: external urls

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `external-urls`
- Example value:
  ```yaml
    external-urls:
      - name: Link
        url : <url>
        icon: <icon>  # not required
        locales:
          fr:
            name: French Localization
      - name: Links with dropdown
        icon: <icon>
        locales:
          fr:
            name: French Localization
        dropdown:
          - name : Link Children
            url: <url>
            icon: <icon>
            locales:
              fr:
                name: <localization>
  ```

### FRONT-CONFIG: visitor alert message

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `alerts`
- Example value:
  ```yaml
    alerts:
      timeout: 3 # days unit
      type: info # color of alert | possibility (info, danger, success, warning,primary, dark, secondary)
      url: /login # no required if want redirect to others service
      title: "Welcome to new SharingHUB "
      message: "To see all projects and unlock all features, please login.."
      locales:
        fr:
          title: "Bienvenue sur le nouveau sharing hub"
          message: "Pour voir tous les projets et débloquer toutes les fonctionnalités, veuillez vous connecter..."
  ```
