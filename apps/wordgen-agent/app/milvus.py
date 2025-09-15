from pymilvus import connections, Collection, list_collections

# Connect
connections.connect("default", host="localhost", port="19530")

collection_names = ["supportive_files", "rfp_files"]

for name in collection_names:
    coll = Collection(name)
    coll.load()  # must load before query

    print(f"\n📂 Data from collection: {name}")
    print(f"Schema: {[field.name for field in coll.schema.fields]}")
    print(f"Total entities: {coll.num_entities}")

    results = coll.query(
        expr="",  # empty expr = all entities
        output_fields=[field.name for field in coll.schema.fields],
        limit=100  # print first 100 rows only
    )

    for row in results:
        print(row)
