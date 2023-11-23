from h3 import h3


def hash_polygon(geojson, limit=80):
    cells_ok = list()
    for i in range(15):
        cells = h3.polyfill(geojson, i, geo_json_conformant=True)
        # cells = h3.compact(cells)
        if len(cells) > limit:
            break
        cells_ok = cells
    return cells_ok


def find_parent_of_hashes(h3_hashes):
    parent_hashes = set()

    for h3_hash in h3_hashes:
        parent_hash = h3.h3_to_parent(h3_hash)
        parent_hashes.add(parent_hash)

    return parent_hashes
