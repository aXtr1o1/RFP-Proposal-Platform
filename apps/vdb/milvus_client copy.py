from pymilvus import MilvusClient

uri = "http://65.2.179.227:19530"  
client = MilvusClient(uri=uri)

collections = ["rfp_files", "supportive_files"]

for name in collections:
    if client.has_collection(name):
        client.drop_collection(name)
        print(f"🗑️ Dropped collection {name}")
