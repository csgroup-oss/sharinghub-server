# Configuration

We rely on user-defined metadata to pass information to SharingHub. The metadata are always handled the same way, regardless of the project's category, although some of them are more suited for specific categories. We will not detail every feature available, for a more in-depth insight of the metadata configuration refer to our [Reference](./reference.md).

--8<-- "share/metadata/reference.md:metadata-syntax"

## Usage

### Overview

| Name | Default value | Configuration |
|---|---|---|
| [Title](./reference.md#title) | Name of the GitLab project. | Metadata `title`. |
| Description | The project description is the README content for the project view, but for the project card in the list we prioritize the GitLab project description (General Settings). | - |
| [Preview](./reference.md#preview) | - | Metadata `preview` or in the "README.md" as a link named "Preview". |
| [License](./reference.md#license) | - | Metadata `license` or the license detected by GitLab. |
| [Temporal Extent](./reference.md#extent) | For the temporal extent the start is the datetime of the project creation, and the end is the project last activity datetime | Metadata `extent.temporal`. |
| [Spatial Extent](./reference.md#extent) | - | Metadata `extent.spatial`. |
| [Providers](./reference.md#providers) | The "host" provider is linked to the GitLab project URL, and the "producer" provider is the GitLab top-level namespace of the project. | Metadata `providers`. |
| [Links](./reference.md#links) | The default links are STAC recommended links, `self`, `parent`, `root`, `collection`, and a link to the project bug tracker as well as the license if one is found. | Metadata `links` and `related`. Note: values will be added and not replace defaults. |
| [Assets](./reference.md#assets) | Inherit global configuration for the project's category. | Metadata `assets`. |
| [Extensions](./reference.md#extensions) | Inherit global configuration. | Metadata `extensions`. |

### Example

A small example to better understand the structure:

```yaml title="Metadata example"
title: My Project
preview: https://avatars.githubusercontent.com/u/6223127
license: MIT

extent:
  temporal: ["2023-11-01T12:00:00.0", "2024-01-01T12:00:00.0"]
  spatial: [-66.5902, 17.9823, -66.6407, 18.0299]

providers:
  - name: CS Group
    roles: ["producer"]
    url: https://www.csgroup.eu
  - name: GitLab CS
    roles: ["host"]
    url: https://gitlab.si.c-s.fr/

related:
  ai-model: https://gitlab.si.c-s.fr/space_applications/mlops-services/sharinghub-tests/model-sample

assets:
  - "*.py"
```
