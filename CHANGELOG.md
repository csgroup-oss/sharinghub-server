# Changelog

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
