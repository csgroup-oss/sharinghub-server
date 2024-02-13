# STAC

The SpatioTemporal Asset Catalog (STAC) is an emerging community-driven specification
for organizing geospatial data, particularly satellite imagery and related geospatial
assets. It is designed to provide a common language and structure for describing
spatiotemporal datasets, making it easier to search, discover, and share geospatial
data across different platforms and tools.

This specification is the core of SharingHub, where categories are STAC collections,
and projects generates STAC Items. By using it, we benefit from its ecosystem, inheriting
tools compatible with it.

STAC is built on top of existing web technologies and standards, such as JSON and HTTP,
making it lightweight, flexible, and easy to implement. It adopts a modular approach,
allowing for extensions to support different types of geospatial data and use cases.

Key components of STAC include:

- **Catalogs**: STAC catalogs are hierarchical structures that organize collections of
  spatiotemporal assets. They provide metadata about the datasets, such as the spatial
  and temporal extent, as well as links to individual assets and related resources.
- **Items**: STAC items are individual metadata records that describe specific spatiotemporal
  assets, such as satellite images or geospatial datasets. They contain information about
  the asset's spatial and temporal properties, as well as any additional metadata or links
  to data files.
- **Assets**: STAC assets represent the actual data files or resources associated with a
  spatiotemporal asset. They can include imagery files, data cubes, metadata files,
  or any other type of geospatial data resource.
- **Extensions**: STAC extensions allow for the customization and extension of the core
  specification to support additional metadata fields, properties, or use cases.
  Examples of extensions include support for point cloud data, radar imagery,
  or additional metadata fields.

Learn more:

- [🔗 STAC website](https://stacspec.org/)
- [🔗 STAC Spec](https://github.com/radiantearth/stac-spec/)
- [🔗 STAC API Spec](https://github.com/radiantearth/stac-api-spec)
- [🔗 STAC Extensions](https://stac-extensions.github.io/)
- [🔗 STAC API Extensions](https://stac-api-extensions.github.io/)
- [🔗 STAC Lint](https://staclint.com/)
