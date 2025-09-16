from pymilvus import connections, list_collections, Collection

# Connect
connections.connect(alias="default", host="localhost", port="19530")

# Drop all collections
collections = list_collections()
print("📂 Collections before drop:", collections)

for name in collections:
    try:
        Collection(name).drop()
        print(f"🗑️ Dropped collection: {name}")
    except Exception as e:
        print(f"⚠️ Failed to drop {name}: {e}")

print("📂 Collections after drop:", list_collections())




# from pymilvus import connections, Collection, list_collections

# # Connect
# connections.connect(alias="default", host="localhost", port="19530")

# # Get all collections
# collections = list_collections()
# print("📂 Found collections:", collections)

# for name in collections:
#     try:
#         coll = Collection(name)
#         coll.load()  # must load before query/search

#         # Query with empty expr but set limit
#         results = coll.query(
#             expr="",  
#             output_fields=["folder_name"],
#             limit=1000   # adjust as needed
#         )

#         print(f"\n📂 Collection: {name}")
#         folder_names = [r["folder_name"] for r in results if "folder_name" in r]
#         print("📁 Folder names:", folder_names)

#         coll.release()
#     except Exception as e:
#         print(f"⚠️ Could not fetch from {name}: {e}")
