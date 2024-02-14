---
hide:
  - navigation
---

# Welcome to SharingHub

<figure markdown>
  ![SharingHub Logo](assets/img/logo.png#only-light){ width="200" }
  ![SharingHub Logo](assets/img/logo-white.png#only-dark){ width="200" }
</figure>

Welcome to our **AI-focused** web portal, SharingHub, designed to help you discover, navigate, and analyze your AI-related **[Git](https://git-scm.com/)** projects hosted on [GitLab](https://about.gitlab.com/). Here you can download code, models and datasets with our interface focused on navigation and accessibility!

We take inspiration from [Hugging Face](https://huggingface.co/), the most used AI sharing website in the world, but our goal is turned towards the geospatial component, with **GIS capabilities**, with datasets and AI models referenced in space and time. This portal is intended to improve exchanges and collaboration between scientists by integrating voting mechanisms, code reviews, and the complete management of the shared assets life cycle.

## Features

### GitLab integration

Very light, SharingHub is deployed on top of a [GitLab](https://about.gitlab.com/) instance, and dynamically extracts metadata from the shared projects to serve them through its web interface, as well as a normalized API.

### Standardized API

Our API implements the [STAC specification](https://stacspec.org), and more precisely the [STAC API](https://github.com/radiantearth/stac-api-spec). This specification is strongly integrated to [OGC](https://www.ogc.org/) standards, and we are compliant with the [OGC API Features](https://ogcapi.ogc.org/features/).

### Data storage

We can deliver large datasets by offering a [DVC](https://dvc.org) remote (S3 store), and support of [Git LFS](https://git-lfs.com/) for compatible GitLab instances.
