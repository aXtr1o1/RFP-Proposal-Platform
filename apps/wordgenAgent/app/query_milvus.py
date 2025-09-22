from pymilvus import Collection, connections

# Connect to Milvus
connections.connect(alias="default", uri="http://65.2.179.227:19530")

# Load collection
col = Collection("rfp_files")
col.load()

# Print only field names (headings)
headings = [field.name for field in col.schema.fields]
print(headings)
