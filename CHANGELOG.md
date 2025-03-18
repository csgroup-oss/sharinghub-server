# Changelog

## 0.4.0 (March 2025)

### Bug fixes

- Add redirect_uri to logout
- Pin pydantic<2.10 to avoid url serialization regression
- Project GraphQL query use userPermissions instead of maxAccessLevel

### Features

- Add mlflow registered models checkpoint files to assets
- Add external url for support contact
- OpenAPI aggregator for services
- Store enable changed to mode, describing http or s3 store

### Internal

- Fix mypy
- Mount UI at root
- Update copyright headers
- Update gitleaks v8.21.2
- Docker: fix format, uppercase 'as' and use 'ENV name=value'
- Docker: move gunicorn app parameter to conf file
- Docker: minimize use of app user home

## 0.3.0 (October 2024)

### Bug fixes

- Visitor access-level changed from guest to reporter
- Add read_repository and write_repository to oauth scope
- Handle null repository
- Handle packages null value
- Rename check API router tag
- STAC: Use project description if no readme content
- STAC: Add file extension to preview asset name
- STAC: improve mlflow tracking uri link, move models from assets to links
- STAC: license 'proprietary' value deprecated, use 'other' instead

### Features

- Add categories to checker API
- Add rest endpoint for project contributors and user
- Add gitlab 'public' mode
- Change access level values, add public and guest
- Add project packages and containers in stac links
- Add mlflow type field to config
- Add mlflow registered models to assets
- Add wizard config

### Internal

- Perf: Add gunicorn config file, calculate number of worker from available cpu
- Revert: remove cache for containers and registered models, use stac cache
- Refactor: use cache namespace and ttl
- Refactor: improve project mlflow definition
- CI: fix publish build to get true API version
- Docs: update CONFIGURATION.md with GITLAB_ALLOW_PUBLIC
- Docs: add new cache settings to CONFIGURATION.md
- Chore: remove deprecated STAC_PROJECTS_CACHE_TIMEOUT from settings

## 0.2.0 (August 2024)

### Bug fixes

- Correct DOI detection
- Stop changing heading level for readme
- GitlabClient request error detail was incomplete
- Return http 401 instead of 403 if no token found
- Load default config only if none provided

### Changes

- Sharinghub integration use request auth headers to call /auth/info
- Allow not having oauth2 configuration
- Allow multi-categories projects
- Add auth mode to config API
- Auto discovery of preview image
- Add default tags as configuration
- Add new sharinghub properties dvc_init
- Config streamlit deployer url from server
- Add project access-level to STAC metadata properties
- Add check API to verify if project found or not
- Allow config of session cookie name and cookies domain
- Add MLflow URL and Docs URL as server config
- Add mlflow configuration for categories
- Improve cache for stac, store and checker

## 0.1.0 (June 2024)

- Initial public release
