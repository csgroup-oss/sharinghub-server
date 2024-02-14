# STAC concepts

Because SharingHub relies on the STAC specification, with a project being transformed to a STAC Item, metadata are tightly tied to it. You can find some resources related to STAC in [Resources / STAC](../../resources/stac.md).

!!! info

    A STAC Item is a valid GeoJSON Feature. ➡️ [Item spec](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md).

## Properties

In STAC, the properties of a STAC Item are the closest thing to the concept of metadata. Its mostly a mapping of key-value pair.

```json title="STAC Item" hl_lines="4"
{
    ...
    "properties": {
        "<key>": "<value>"
    }
    ...
}
```

## Links

The "links" in a STAC object is a list of URLs, with for each a "relationship" (`rel`) to the item, and a `type`, which is the media type of the resources pointed by the URL (`href`).

```json title="STAC Item" hl_lines="5-9"
{
    ...
    "links": [
        ...
        {
            "rel": "<value>",
            "href": "<url>",
            "type": "<media type>",
        },
        ...
    ]
    ...
}
```

## Assets

The assets of a STAC Item are essentially links to the resources. Unlike links, it is a mapping, with unique keys.

```json title="STAC Item" hl_lines="5-10"
{
    ...
    "assets": {
        ...
        "<key>": {
            "href": "<url>",
            "title": "<string>",
            "roles": ["<string>", ...],
            "type": "<media type>",
        },
        ...
    }
    ...
}
```
