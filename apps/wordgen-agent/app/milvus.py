from pymilvus import connections, Collection

# Connect to Milvus
connections.connect("default", host="localhost", port="19530")

# Load collection
collection = Collection("rfp_documents")

# Query where folder_name matches the given UUID
folder_uuid = "235e02c8-a413-4a87-9eb4-6f1b020e4284"
results = collection.query(
    expr=f'folder_name == "{folder_uuid}"',  # Filter by specific folder_uuid
    output_fields=["folder_name", "file_name", "file_type", "content", "document_id", "timestamp"],  # Add other fields as needed
    limit=10000
)


for row in results:
    print(row)