# Configuration

You can configure the SharingHub server through multiple sources:

- YAML file
- Environment variables

> Note: Environment variables always overwrite YAML values if they are set.

The YAML file path can be changed to point to another one with the environment variable `CONFIG_PATH`.

Content:

- [Variables](#variables)
  - [Config file path](#config-file-path)
  - [Server](#server)
    - [Debug](#debug)
    - [Log level](#log-level)
    - [API prefix](#api-prefix)
    - [Allowed origins](#allowed-origins)
    - [Session secret key](#session-secret-key)
    - [Session cookie](#session-cookie)
    - [Session domain](#session-domain)
    - [Session max age](#session-max-age)
    - [Static files path](#static-files-path)
    - [Static UI dirname](#static-ui-dirname)
    - [HTTP client timeout](#http-client-timeout)
    - [Enable cache](#enable-cache)
    - [Check API cache timeout](#check-api-cache-timeout)
  - [Gitlab](#gitlab)
    - [URL](#url)
    - [Allow public](#allow-public)
    - [OAuth client id](#oauth-client-id)
    - [OAuth client secret](#oauth-client-secret)
    - [OAuth default token](#oauth-default-token)
    - [Ignore topics](#ignore-topics)
  - [S3](#s3)
    - [Enable](#enable)
    - [Bucket](#bucket)
    - [Access key](#access-key)
    - [Secret key](#secret-key)
    - [Region](#region)
    - [Endpoint url](#endpoint-url)
    - [Presigned expiration](#presigned-expiration)
    - [Upload chunk size](#upload-chunk-size)
    - [Check access cache timeout](#check-access-cache-timeout)
  - [JupyterLab: URL](#jupyterlab-url)
  - [Wizard: URL](#wizard-url)
  - [MLflow](#mlflow)
    - [MLflow Type](#mlflow-type)
    - [MLflow URL](#mlflow-url)
  - [SPACES: Deployment conf](#spaces-deployment-conf)
  - [Documentation: URL](#documentation-url)
  - [STAC](#stac)
    - [Root conf](#root-conf)
    - [Categories](#categories)
      - [Categories features](#categories-features)
    - [Projects cache timeout](#projects-cache-timeout)
    - [Projects assets rules](#projects-assets-rules)
    - [Projects assets release source format](#projects-assets-release-source-format)
    - [Search page default size](#search-page-default-size)
  - [Front config](#front-config)
    - [External urls](#external-urls)
    - [Visitor alert message](#visitor-alert-message)
    - [Tags sections](#tags-sections)

## Variables

> Note: relative paths are resolved against current working dir

### Config file path

- Type: path
- Default: `"<APP_DIR>/config.yaml"`
- Environment variable:
  - Name: `CONFIG_PATH`
  - Example value: `/path/to/file.yaml`

### Server

#### Debug

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

#### Log level

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

#### API prefix

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

#### Allowed origins

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

#### Session secret key

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

#### Session cookie

- Type: string
- Default: `"sharinghub-session"`
- Environment variable:
  - Name: `SESSION_COOKIE`
  - Example value: `"session"`
- YAML:
  - Path: `server.session.cookie`
  - Example value:

    ```yaml
    server:
      session:
        cookie: "session"
    ```

#### Session domain

- Type: string
- Default: `None`
- Environment variable:
  - Name: `SESSION_DOMAIN`
  - Example value: `"test.local"`
- YAML:
  - Path: `server.session.domain`
  - Example value:

    ```yaml
    server:
      session:
        domain: "test.local"
    ```

#### Session max age

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

#### Static files path

- Type: path
- Environment variable:
  - Name: `STATIC_FILES_PATH`
  - Example value: `/statics`
- YAML:
  - Path: `server.statics`
  - Example value:

    ```yaml
    server:
      statics: /statics
    ```

#### Static UI dirname

- Type: string
- Default: `ui`
- Environment variable:
  - Name: `STATIC_UI_DIRNAME`
  - Example value: `web-ui`
- YAML:
  - Path: `server.statics-ui`
  - Example value:

    ```yaml
    server:
      statics-ui: web-ui
    ```

#### HTTP client timeout

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

#### Enable cache

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

#### Check API cache timeout

- Type: floating number
- Default: `300.0`
- Environment variable:
  - Name: `CHECKER_CACHE_TIMEOUT`
  - Example value: `15.0`
- YAML:
  - Path: `checker.cache-timeout`
  - Example value:

    ```yaml
    checker:
      cache-timeout: 15.0
    ```

### Gitlab

#### URL

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

#### Allow public

- Type: boolean
- Default: `False`
- Environment variable:
  - Name: `GITLAB_ALLOW_PUBLIC`
  - Values: `true`, `false`
- YAML:
  - Path: `gitlab.allow-public`
  - Example value:

    ```yaml
    gitlab:
      allow-public: true
    ```

#### OAuth client id

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

#### OAuth client secret

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

#### OAuth default token

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

#### Ignore topics

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

### S3

#### Enable

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

#### Bucket

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

#### Access key

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

#### Secret key

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

#### Region

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

#### Endpoint url

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

#### Presigned expiration

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

#### Upload chunk size

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

#### Check access cache timeout

- Type: floating number
- Default: `300.0`
- Environment variable:
  - Name: `S3_CHECK_ACCESS_CACHE_TIMEOUT`
  - Example value: `15.0`
- YAML:
  - Path: `s3.check-access.cache-timeout`
  - Example value:

    ```yaml
    s3:
      check-access:
        cache-timeout: 15.0
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
    jupyterlab:
      url: https://nb.example.com
    ```

### Wizard: URL

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `WIZARD_URL`
  - Example value: `https://example.com/wizard`
- YAML:
  - Path: `wizard.url`
  - Example value:

    ```yaml
    wizard:
      url: https://example.com/wizard
    ```

### MLflow

#### MLflow Type

- Type: string (possible values: "mlflow", "mlflow-sharinghub", "gitlab")
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `MLFLOW_TYPE`
  - Example value: `mlflow-sharinghub`
- YAML:
  - Path: `mlflow.type`
  - Example value:

    ```yaml
    mlflow:
      type: gitlab
    ```

#### MLflow URL

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `MLFLOW_URL`
  - Example value: `https://sharinghub.example.com/mlflow`
- YAML:
  - Path: `mlflow.url`
  - Example value:

    ```yaml
    mlflow:
      url: https://sharinghub.example.com/mlflow
    ```

### SPACES: Deployment conf

- Type: mapping
- Default: read from [config file](./app/config.yaml)
  - YAML:
    - Path: `spaces`
- Example value:

  ```yaml
    spaces:
       streamlit:
         url: "https://example.example.com/deploy/"
         assets:
            - streamlit_app.py
            - file.example
  ```

### Documentation: URL

- Type: string
- Default: read from [config file](./app/config.yaml)
- Environment variable:
  - Name: `DOCS_URL`
  - Example value: `https://sharingub.instance/docs`
- YAML:
  - Path: `docs.url`
  - Example value:

    ```yaml
    docs:
      url:https://sharinghub.example.com/docs
    ```

### STAC

#### Root conf

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

#### Categories

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `stac.categories`
  - Example value:

    ```yaml
    stac:
      categories:
        - my-category:
            title: My Category
            description: Custom category
            default_type: item
    ```

##### Categories features

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `stac.categories.[entry].features`
  - Example value:

    ```yaml
    stac:
      categories:
        - my-category:
            features:
              deployment-spaces: enable #to enable spaces deployment link for item of this category
              jupyter: disable  #to enable jupyter link for item of this category
              map-viewer: enable #to enable map-viewer for item of this category
              store-s3: enable #to enable dvc for item of this category
              mlflow: enable #to enable mlflow for item of this category
    ```

#### Projects cache timeout

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

#### Projects assets rules

- Type: list of string
- Default: `["*.tif", "*.tiff", "*.geojson"]`
- Environment variable:
  - Name: `STAC_PROJECTS_ASSETS_RULES`
  - Example value: `*.tif *.tiff`
- YAML:
  - Path: `stac.categories.[0].assets`
  - Example value:

    ```yaml
    stac:
      categories:
        dashboard:
          assets:
            - "*.tiff"
            - "*.py"
    ```

#### Projects assets release source format

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

#### Search page default size

- Type: integer number
- Default: `12`
- Environment variable:
  - Name: `STAC_SEARCH_PAGE_DEFAULT_SIZE`
  - Example value: `20`
- YAML:
  - Path: `stac.search.page-size`
  - Example value:

    ```yaml
    stac:
      search:
        page-size: 20
    ```

### Front config

#### External urls

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

#### Visitor alert message

- Type: mapping
- Default: read from [config file](./app/config.yaml)
- YAML:
  - Path: `alerts`
  - Example value:

    ```yaml
      alerts:
        timeout: 3 # days unit
        type: info # color of alert | possibility (info, danger, success, warning,primary, dark, secondary)
        title: "Welcome to new SharingHub"
        message: "To see all projects and unlock all features, please login.." # Possible to render primitives html component in message ex: <a href='url'> text here <a/>
        locales:
          fr:
            title: "Bienvenue sur le nouveau sharing hub"
            message: "Pour voir tous les projets et débloquer toutes les fonctionnalités, veuillez vous connecter..." # Possible to render primitives html component in message ex: <a href='url'> text here <a/>
    ```

#### Tags sections

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
