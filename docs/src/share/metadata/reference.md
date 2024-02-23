# Reference

This page references all of our [Metadata](./index.md)-related available features.

<!-- --8<-- [start:metadata-syntax] -->

## Syntax

The metadata of a project are defined in its `README.md` file. Markdown allows a syntax for metadata, as YAML:

```md title="README.md" hl_lines="1-3"
---
foo: bar
---

# Title

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Morbi neque neque,
malesuada vel sodales eu, pharetra sit amet nibh. Integer in nunc ante.
Morbi commodo metus est, id aliquet odio cursus id. Ut non sagittis metus.
```

By using a `---` delimited section at the start of your `README.md`, you can write metadata that will not be rendered in the project description on SharingHub. The informations here will be parsed and used to process the STAC Item of the project.

!!! warning
    We always require a `README.md` file, with the uppercase file name, and in [CommonMark](https://commonmark.org/) (Markdown) format.

<!-- --8<-- [end:metadata-syntax] -->

## Rendering

Our metadata schema relies a lot on STAC, but some helpers are available. All metadata are written inside the `---` section.

### Title

The title defaults to the project name, but you can easily override it with the `title` metadata.

```yaml title="Metadata example"
title: My Custom Title
```

### Preview

The preview can be auto-discovered in the README, if your image "alt" is "Preview" (not case-sensitive).

```md title="README.md"
![Preview](<url>)
```

Or, you can define it in the metadata.

```yaml title="Metadata"
preview: <url>
```

### License

We can retrieve the license if you have a LICENSE file in your repository, it will be automatically detected. However, it can still be configured.

```yaml title="Metadata"
license: <license name>
```

!!! warning
    Only a [SPDX License Identifier](https://spdx.org/licenses/) is allowed.

In addition, you can set an URL for the license. While it is automatically set to the URL of the project LICENSE file, or determined from the license given, you can also change it:

```yaml title="Metadata"
license-url: <license url>
```

!!! warning
    The STAC Item specification indicates that the URL of the license **SHOULD** be defined.

### Extent

#### Temporal

By default, a project temporal extent starts at the creation date of the gitlab repository, and ends at the date of last activity in this repository. But we do have search capabilities on datetime range, so you may want sometime to correct your project temporal extent. Do so with:

```yaml title="Metadata example"
extent:
  temporal: ["2023-11-01T12:00:00.0", "2024-01-01T12:00:00.0"]
```

!!! info
    Datetime should be expressed in UTC.

#### Spatial

You may define a spatial extent for your project.

We support bbox:

```yaml title="Metadata example"
extent:
  spatial: [-66.5902, 17.9823, -66.6407, 18.0299]
```

And WKT geometries:

```yaml title="Metadata example"
extent:
  spatial: "POLYGON ((-66.6407 17.9823, -66.6407 18.0299, -66.5902 18.0299, -66.5902 17.9823, -66.6407 17.9823))"
```

### Providers

The provider concept in STAC help to inform about the organizations capturing, producing, processing, hosting or publishing the data of the project.

By default, the "host" provider is set to the project GitLab URL, and the "producer" provider is set to the GitLab repository user or first-level group.

Example: for `https://gitlab.example.com/A/repo-b` with the user "A" having a repository "repo-b", the host is `https://gitlab.example.com/A/repo-b`, and the producer is `https://gitlab.example.com/A`.

However, you can still pass your own values for the providers. You must follow the [spec](https://github.com/radiantearth/stac-spec/blob/master/item-spec/common-metadata.md#provider) of the provider object.

```yaml title="Metadata"
providers:
  - name: <producer name>
    roles: ["producer"]
    url: <producer url>
  - name: <host name>
    roles: ["host"]
    url: <host url>
```

### Links

#### Related projects

You may want to add links to your projects. A common use-case would be linking an AI model to a dataset. You can link projects between them with the `related` metadata, but beware, in SharingHub, projects are categorized, and you will need to use that information. SharingHub categories are STAC collections, you will have to use the collection id (example: ai-model, dataset).

```yaml title="Metadata"
related:
  <collection id>: <gitlab project url>
```

List are also accepted for multiple links

```yaml title="Metadata"
related:
  <collection id>:
    - <gitlab project 1 url>
    - <gitlab project 2 url>
```

#### Raw links

You can also use a more "low-level" metadata to directly define additional STAC links with `links` metadata. Follow the [spec](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md#link-object).

```yaml title="Metadata"
links:
  - href: <url>
    rel: <rel>
```

!!! tip
    Check [Helpers](#helpers) to learn some extra features for the link's `href`.

### Assets

#### Basic usage

You will want to share files from your GitLab repository with SharingHub. Only the files defined in the `assets` metadata will be shared, to avoid bloating.

You can share a file:

```yaml title="Metadata example"
assets:
  - "requirements.txt"
```

But sometimes, you will have the need to include multiple files, in this case you can use basic [glob](https://en.wikipedia.org/wiki/Glob_(programming)) syntax with wildcards.

```yaml title="Metadata example"
assets:
  - "*.py"
```

All matching files will be added.

!!! note
    Your SharingHub instance can have some assets rules pre-configured, this is why you may find your project having assets without any configured.

#### Advanced usage

There is an advanced, more powerful syntax available to define your assets. This feature will be very useful for some use-cases.

##### Media type

The STAC asset `type` is guessed from the file extension, but sometimes you will want to change this type. In the following example we will declare the media type of our COG `.tiff` files, because it is only detected as `image/tiff`.

```yaml title="Metadata example"
assets:
  - glob: "*.tiff"
    type: image/tiff; application=geotiff; profile=cloud-optimized
```

There is a shortcut feature available for some file extensions, `type-as`.

```yaml title="Metadata example"
assets:
  - glob: "*.tiff"
    type-as: cog
```

Available `type-as` values:

| type-as    | type                                                       |
|------------|------------------------------------------------------------|
| `compose`  | `text/x-yaml; application=compose`                         |
| `cog`      | `image/tiff; application=geotiff; profile=cloud-optimized` |
| `geojson`  | `application/geo+json`                                     |
| `geotiff`  | `image/tiff; application=geotiff`                          |
| `json`     | `application/json`                                         |
| `notebook` | `application/x-ipynb+json`                                 |
| `text`     | `text/plain`                                               |
| `xml`      | `application/xml`                                          |
| `yaml`     | `text/x-yaml`                                              |
| `zip`      | `application/zip`                                          |

##### Custom assets

There may be times where you will want to add a custom asset. When a `glob` or `path` field is provided, we will try to match it with one of the project's files. In this case, we will loop over each match and create an asset with its `href` set to the file. But you can define assets that do not "match" the files. The thing is, we consider an asset valid if it has at least a `key` and a `href`. This let you add custom assets to reference external resources.

As an example, we will add an asset from [this](https://github.com/radiantearth/stac-spec/blob/master/examples/simple-item.json) simple STAC Item example of the stac spec repository.

```yaml title="Metadata example"
assets:
  - key: visual
    href: https://storage.googleapis.com/open-cogs/stac-examples/20201211_223832_CS2.tif
    type: image/tiff; application=geotiff; profile=cloud-optimized
    title: 3-Band Visual
    roles: [visual]
```

Notice that because our `assets` metadata is a list and not a mapping, we add the keyword `key` to define the asset key in the resulting asset mapping. Other than that, all [STAC asset fields](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md#asset-object) can always be set manually, `href`, `type`, `title`, `description`,  and `roles`.

!!! tip
    Check [Helpers](#helpers) to learn some extra features for the asset's `href`.

##### Alter files assets

By default, an asset generated from a file only have an `href`, a `roles: [data]`, and a `type` if it was guessed. But, don't hesitate to improve your assets by adding a `title` an a `description`! We offer some utility features to alter your assets per match.

```yaml title="Metadata example"
assets:
  - glob: "*.py"
    key: "python://{path}"
    title: "File '{path}'"
    description: "Python file '{key}'"
```

A file asset key in the assets mapping is by default the path of the file, but you can change it. You can use `{path}` in `key`, `title`, `description` and `{key}` in `title`, `description`. This will let you interpolate the value for each match, and is really helpful here to change the asset key for each of the python files.

### Extensions

We rely on STAC Extensions to enrich our metadata. You can use about every STAC extension you want like this:

```yaml title="Metadata"
extensions:
  <extension prefix>: <extension schema>

<extension prefix>:
  <prop>: <val>
```

Some STAC Extensions are pre-configured, with no need to specify them in `extensions` metadata. List of extensions pre-configured:

| Name | Source | Prefix |
|---|---|---|
| Electro-Optical | <https://github.com/stac-extensions/eo> | `eo` |
| Label | <https://github.com/stac-extensions/label> | `label` |
| ML Model | <https://github.com/stac-extensions/ml-model> | `ml-model` |
| Scientific Citation | <https://github.com/stac-extensions/scientific> | `sci` |

A concrete example for the Scientific Citation Extension:

```yaml title="Metadata example"
sci:
  doi: 10.XXXX/XXXXX
  citation: Lorem ipsum dolor sit amet, consectetur adipiscing elit.
```

You may have noticed that in STAC Extensions the properties are used like "sci:doi", "sci:citation", and you are right, but the syntax above help to avoid having to type multiple times the prefix of the extension.

#### Scientific Citation

This extension is built-in in STAC Browser with an interesting parsing capability. You can define their values like in the example above, or write them in your README directly.

```md title="README.md"
[DOI: Lorem ipsum dolor sit amet, consectetur adipiscing elit.](https://doi.org/10.XXXX/XXXXX)
```

If a markdown link href starts with `https://doi.org`, it will be retrieved as the DOI. If more than one link matches this condition, the first is still the project DOI, and the remaining DOIs will be added as publications, following the extension.

### Remaining properties

After every metadata described in the previous sections are processed, there may still remain other metadata. These metadata are passed as-is to the STAC Item **properties**.

For example, you may want declare the `gsd` or `platform` of a Sentinel 2 dataset:

```yaml title="Metadata example"
gsd: 10
platform: sentinel-2
```

These metadata will be passed as properties transparently.

```json title="Generated STAC Item"
{
  ...
  "properties": {
    ...
    "gsd": 10,
    "platform": "sentinel-2",
    ...
  }
  ...
}
```

### Helpers

Both [Links](#links) and [Assets](#assets) declare a `href` field, an URL to a resource. But, there are two cases where you don't have direct URL to the resource.

#### Repository file

If an href is detected to be a "local path", like "./myfile.txt" or "files/myfile.txt", the `href` is automatically changed to an URL using our download API for the file.

#### Other project

The `href` should never be a hard link to a SharingHub instance, and you may not want to use the [`related`](#related-projects) metadata in some cases. You can still generate an URL to the STAC Item of another project without hard linking the SharingHub instance.

Because a project's STAC Item is always in a collection (our [categories](../../explore/categories.md)), you will need the "collection id" / category of the target project, and you can use the following syntax:

```yaml title="Metadata"
href: <collection id>+<gitlab project url>
```

A more concrete example:

```yaml title="Metadata example"
href: dataset+https://gitlab.si.c-s.fr/space_applications/mlops-services/sharinghub-tests/dataset-sample
```

In SharingHub, an URL to the STAC Item will then be created.
