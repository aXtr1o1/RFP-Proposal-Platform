from pymilvus import MilvusClient, DataType
from sentence_transformers import SentenceTransformer
import logging
import uuid
import os
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
import json

load_dotenv()
logger = logging.getLogger(__name__)

class MilvusVectorClient:
    def __init__(self, collection_name: str = "rfp_documents"):
        self.uri = os.getenv("MILVUS_URI", "http://localhost:19530")
        self.collection_name = collection_name
        
        # Initialize Sentence Transformers
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.embedding_dim = 384
            logger.info("Sentence Transformer model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Sentence Transformer: {e}")
            self.embedding_model = None
        
        # Initialize Milvus client
        try:
            self.client = MilvusClient(uri=self.uri)
            logger.info("Milvus client initialized successfully")
        except Exception as e:
            logger.error(f"Milvus initialization failed: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if both Milvus client and embedding model are available"""
        return self.client is not None and self.embedding_model is not None
    
    def set_collection(self, collection_name: str):
        """Dynamically change collection name"""
        self.collection_name = collection_name
        logger.info(f"Switched to collection: {collection_name}")
    
    def _chunk_content_by_bytes(self, text: str, max_bytes: int = 15000) -> List[str]:
        """Chunk text by byte length to ensure Milvus compatibility"""
        text_bytes = text.encode('utf-8')
        
        if len(text_bytes) <= max_bytes:
            return [text]
        
        chunks = []
        words = text.split()
        current_chunk = []
        current_bytes = 0
        
        for word in words:
            word_bytes = len(word.encode('utf-8')) + 1  # +1 for space
            
            if current_bytes + word_bytes > max_bytes and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append(chunk_text)
                current_chunk = [word]
                current_bytes = word_bytes
            else:
                current_chunk.append(word)
                current_bytes += word_bytes
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        # Final validation and truncation if needed
        for i, chunk in enumerate(chunks):
            chunk_bytes = len(chunk.encode('utf-8'))
            if chunk_bytes > max_bytes:
                logger.warning(f"Chunk {i} still exceeds byte limit: {chunk_bytes} bytes")
                chunks[i] = chunk[:max_bytes//2] + "..."
        
        return chunks
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist or recreate if needed"""
        try:
            # Drop existing collection for fresh start
            if self.client.has_collection(self.collection_name):
                try:
                    self.client.drop_collection(self.collection_name)
                    logger.info(f"Dropped existing collection: {self.collection_name}")
                except Exception as e:
                    logger.warning(f"Error dropping collection: {e}")

            # Create schema
            schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=100)
            schema.add_field("content", DataType.VARCHAR, max_length=16000)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.embedding_dim)
            schema.add_field("file_name", DataType.VARCHAR, max_length=500)
            schema.add_field("file_path", DataType.VARCHAR, max_length=1000)
            schema.add_field("file_type", DataType.VARCHAR, max_length=50)
            schema.add_field("total_pages", DataType.INT64)
            schema.add_field("total_words", DataType.INT64)
            schema.add_field("folder_name", DataType.VARCHAR, max_length=500)
            schema.add_field("chunk_index", DataType.INT64)
            schema.add_field("document_id", DataType.VARCHAR, max_length=100)
            schema.add_field("timestamp", DataType.VARCHAR, max_length=50)
            
            # Create collection
            self.client.create_collection(collection_name=self.collection_name, schema=schema)
            logger.info(f"Created collection: {self.collection_name}")
            
            # Create vector index
            self._create_vector_index()
            
            # Load collection
            try:
                self.client.load_collection(self.collection_name)
                logger.info("Collection loaded successfully")
            except Exception as e:
                logger.warning(f"Collection loading warning: {e}")
                
        except Exception as e:
            logger.error(f"Collection creation failed: {e}")
            raise
    
    def _create_vector_index(self):
        """Create vector index with fallback options"""
        try:
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_type="IVF_FLAT",
                metric_type="COSINE",
                params={"nlist": 128}
            )
            
            self.client.create_index(
                collection_name=self.collection_name,
                index_params=index_params
            )
            logger.info("Vector index created successfully")
            
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            try:
                # Fallback to AUTOINDEX
                index_params = self.client.prepare_index_params()
                index_params.add_index(
                    field_name="vector",
                    index_type="AUTOINDEX",
                    metric_type="COSINE"
                )
                
                self.client.create_index(
                    collection_name=self.collection_name,
                    index_params=index_params
                )
                logger.info("AUTOINDEX fallback created successfully")
            except Exception as e2:
                logger.error(f"Fallback index creation failed: {e2}")
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Sentence Transformers"""
        try:
            if not self.embedding_model:
                raise Exception("Embedding model not available")
            
            embedding = self.embedding_model.encode(
                text, 
                normalize_embeddings=True,
                convert_to_tensor=False
            )
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def save_documents_with_images(self, ocr_results: List[Dict], folder_name: str, image_metadata: List[Dict] = None) -> List[str]:
        """Enhanced save method that handles image metadata alongside text"""
        # Ensure collection exists
        self._ensure_collection()
        
        # First, save documents using existing method
        doc_ids = self.save_documents(ocr_results, folder_name)
        
        # Then, save image metadata if provided
        if image_metadata and doc_ids:
            try:
                self._save_image_metadata(image_metadata, folder_name)
                logger.info(f"Saved {len(image_metadata)} image metadata entries to {self.collection_name}")
            except Exception as e:
                logger.error(f"Error saving image metadata: {e}")
        
        return doc_ids

    def _save_image_metadata(self, image_metadata: List[Dict], folder_name: str):
        """Save image metadata as separate entries in Milvus"""
        if not self.is_available() or not image_metadata:
            return
        
        entities = []
        
        for img_data in image_metadata:
            try:
                # Generate embedding for image description/text
                img_text = img_data.get('extracted_text', img_data.get('type', 'image'))
                if not img_text.strip():
                    img_text = f"{img_data.get('type', 'image')} from page {img_data.get('page', 1)}"
                
                vector = self._generate_embedding(img_text)
                
                # Create metadata content for storage
                metadata_content = json.dumps({
                    'image_id': img_data['id'],
                    'image_type': img_data['type'],
                    'page': img_data['page'],
                    'blob_url': img_data['blob_url'],
                    'extracted_text': img_data.get('extracted_text', ''),
                    'dimensions': img_data.get('dimensions', {}),
                    'file_name': img_data.get('file_name', ''),
                    'confidence': img_data.get('confidence', 0.0)
                })
                
                entity = {
                    "id": f"img_{img_data['id']}_{uuid.uuid4().hex[:8]}",
                    "content": metadata_content,
                    "vector": vector,
                    "file_name": img_data.get('file_name', 'image_metadata'),
                    "file_path": img_data.get('file_path', 'images'),
                    "file_type": "image_metadata",
                    "total_pages": 1,
                    "total_words": len(img_data.get('extracted_text', '').split()),
                    "folder_name": folder_name,
                    "chunk_index": 0,
                    "document_id": img_data['id'],
                    "timestamp": datetime.now().isoformat()
                }
                entities.append(entity)
                
            except Exception as e:
                logger.error(f"Error processing image metadata {img_data.get('id', 'unknown')}: {e}")
                continue
        
        if entities:
            try:
                self.client.load_collection(self.collection_name)
                insert_result = self.client.insert(
                    collection_name=self.collection_name,
                    data=entities
                )
                self.client.flush(collection_name=self.collection_name)
                logger.info(f"Successfully inserted {len(entities)} image metadata entries to {self.collection_name}")
            except Exception as e:
                logger.error(f"Failed to insert image metadata: {e}")

    def get_images_metadata(self, limit: int = 50) -> List[Dict]:
        """Get all image metadata from Milvus with proper format"""
        if not self.is_available():
            return []
        
        try:
            # Check if collection exists
            if not self.client.has_collection(self.collection_name):
                return []
            
            self.client.load_collection(self.collection_name)
            
            result = self.client.query(
                collection_name=self.collection_name,
                filter='file_type == "image_metadata"',
                output_fields=["*"],
                limit=limit
            )
            
            images_data = []
            for item in result:
                try:
                    metadata = json.loads(item["content"])
                    
                    # Format according to specified structure
                    formatted_image = {
                        "id": metadata['image_id'],
                        "type": metadata['image_type'],
                        "page": metadata['page'],
                        "embedding": item["vector"][:10] if item.get("vector") else [],
                        "blob_url": metadata['blob_url'],
                        "extracted_text": metadata.get('extracted_text', ''),
                        "file_name": metadata.get('file_name', ''),
                        "dimensions": metadata.get('dimensions', {}),
                        "confidence": metadata.get('confidence', 0.0),
                        "timestamp": item["timestamp"]
                    }
                    images_data.append(formatted_image)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing image metadata: {e}")
                    continue
            
            return images_data
            
        except Exception as e:
            logger.error(f"Error retrieving image metadata from {self.collection_name}: {e}")
            return []
    
    def save_documents(self, ocr_results: List[Dict], folder_name: str) -> List[str]:
        """Save documents with byte-based chunking to handle Arabic text"""
        if not self.is_available() or not ocr_results:
            logger.warning("Milvus or embedding model not available")
            return []
        
        # Ensure collection exists
        self._ensure_collection()
        
        # Group results by document
        documents = self._group_results_by_document(ocr_results)
        
        entities = []
        doc_ids = []
        
        for file_name, doc_data in documents.items():
            try:
                document_id = str(uuid.uuid4())
                doc_ids.append(document_id)
                
                full_content = " ".join([p.get('content', '') for p in doc_data['pages']])
                if not full_content.strip():
                    logger.warning(f"Empty content for {file_name}")
                    continue
                
                content_chunks = self._chunk_content_by_bytes(full_content, max_bytes=12000)
                info = doc_data['info']
                
                for chunk_index, chunk_content in enumerate(content_chunks):
                    try:
                        # Validate chunk size
                        chunk_bytes = len(chunk_content.encode('utf-8'))
                        if chunk_bytes > 15000:
                            logger.error(f"Chunk {chunk_index} too large: {chunk_bytes} bytes, skipping")
                            continue
                        
                        vector = self._generate_embedding(chunk_content)
                        
                        entity = {
                            "id": f"{document_id}_chunk_{chunk_index}",
                            "content": chunk_content,
                            "vector": vector,
                            "file_name": file_name,
                            "file_path": info.get('file_path', 'unknown'),
                            "file_type": info.get('file_type', 'document'),
                            "total_pages": len(doc_data['pages']),
                            "total_words": sum([p.get('word_count', 0) for p in doc_data['pages']]),
                            "folder_name": folder_name,
                            "chunk_index": chunk_index,
                            "document_id": document_id,
                            "timestamp": datetime.now().isoformat()
                        }
                        entities.append(entity)
                        
                    except Exception as e:
                        logger.error(f"Error processing chunk {chunk_index} of {file_name}: {e}")
                        continue
                
                logger.info(f"Prepared {len(content_chunks)} chunks for {file_name}")
                
            except Exception as e:
                logger.error(f"Error processing {file_name}: {e}")
                continue
        
        # Insert entities in batches
        if entities:
            inserted_count = self._insert_entities_in_batches(entities)
            logger.info(f"Successfully saved {len(documents)} documents ({inserted_count} chunks) to {self.collection_name}")
            return doc_ids
        else:
            logger.warning("No valid entities to insert")
            return []
    
    def _group_results_by_document(self, ocr_results: List[Dict]) -> Dict:
        """Group OCR results by document"""
        documents = {}
        for result in ocr_results:
            file_name = result.get('file_name', 'unknown')
            if file_name not in documents:
                documents[file_name] = {'pages': [], 'info': result}
            documents[file_name]['pages'].append(result)
        return documents
    
    def _insert_entities_in_batches(self, entities: List[Dict], batch_size: int = 25) -> int:
        """Insert entities in batches to avoid memory issues"""
        try:
            self.client.load_collection(self.collection_name)
            inserted_count = 0
            
            logger.info(f"Inserting {len(entities)} entities in batches of {batch_size} to {self.collection_name}")
            
            for i in range(0, len(entities), batch_size):
                batch = entities[i:i + batch_size]
                
                try:
                    insert_result = self.client.insert(
                        collection_name=self.collection_name,
                        data=batch
                    )
                    
                    if hasattr(insert_result, 'insert_count'):
                        inserted_count += insert_result.insert_count
                    else:
                        inserted_count += len(batch)
                    
                    logger.info(f"Inserted batch {i//batch_size + 1}: {len(batch)} entities")
                    
                except Exception as e:
                    logger.error(f"Error inserting batch {i//batch_size + 1}: {e}")
                    continue
            
            # Flush and verify
            try:
                self.client.flush(collection_name=self.collection_name)
                logger.info(f"Flushed data to disk. Total inserted: {inserted_count}")
                self._verify_insertion()
            except Exception as e:
                logger.error(f"Flush failed: {e}")
            
            return inserted_count
            
        except Exception as e:
            logger.error(f"Insert operation failed: {e}")
            return 0
    
    def _verify_insertion(self):
        """Verify that data was successfully inserted"""
        try:
            self.client.load_collection(self.collection_name)
            stats = self.client.query(
                collection_name=self.collection_name,
                filter="",
                output_fields=["id"],
                limit=1
            )
            
            if stats:
                logger.info(f"Verification: Data successfully stored in {self.collection_name}")
            else:
                logger.warning("Verification: No data found after insertion")
                
        except Exception as e:
            logger.error(f"Verification failed: {e}")
    
    def get_all_documents(self, limit: int = 100) -> List[Dict]:
        """Get all stored documents, grouping chunks by document_id"""
        if not self.is_available():
            return []
        
        try:
            # Check if collection exists
            if not self.client.has_collection(self.collection_name):
                logger.warning(f"Collection {self.collection_name} does not exist")
                return []
            
            self.client.load_collection(self.collection_name)
            
            result = self.client.query(
                collection_name=self.collection_name,
                filter='file_type != "image_metadata"',
                output_fields=["*"],
                limit=limit * 3
            )
            
            # Group chunks by document
            grouped_docs = self._group_chunks_by_document(result)
            
            # Format documents
            formatted_docs = []
            for doc_data in list(grouped_docs.values())[:limit]:
                doc_data["chunks"].sort(key=lambda x: x["chunk_index"])
                full_content = " ".join([c["content"] for c in doc_data["chunks"]])
                
                formatted_docs.append({
                    "id": doc_data["id"],
                    "file_name": doc_data["file_name"],
                    "file_path": doc_data["file_path"],
                    "file_type": doc_data["file_type"],
                    "total_pages": doc_data["total_pages"],
                    "total_words": doc_data["total_words"],
                    "folder_name": doc_data["folder_name"],
                    "content_preview": full_content[:300] + "..." if len(full_content) > 300 else full_content,
                    "full_content": full_content,
                    "chunk_count": len(doc_data["chunks"]),
                    "timestamp": doc_data["timestamp"]
                })
            
            logger.info(f"Retrieved {len(formatted_docs)} documents from {self.collection_name}")
            return formatted_docs
            
        except Exception as e:
            logger.error(f"Query failed for collection {self.collection_name}: {e}")
            return []
    
    def _group_chunks_by_document(self, result: List[Dict]) -> Dict:
        """Group chunks by document ID"""
        grouped_docs = {}
        for chunk in result:
            doc_id = chunk.get("document_id", chunk["id"])
            if doc_id not in grouped_docs:
                grouped_docs[doc_id] = {
                    "id": doc_id,
                    "file_name": chunk["file_name"],
                    "file_path": chunk["file_path"],
                    "file_type": chunk["file_type"],
                    "total_pages": chunk["total_pages"],
                    "total_words": chunk["total_words"],
                    "folder_name": chunk["folder_name"],
                    "timestamp": chunk["timestamp"],
                    "chunks": []
                }
            
            grouped_docs[doc_id]["chunks"].append({
                "chunk_index": chunk.get("chunk_index", 0),
                "content": chunk["content"]
            })
        
        return grouped_docs
    
    def search_similar_documents(self, query_text: str, limit: int = 10) -> List[Dict]:
        """Search for similar documents"""
        if not self.is_available():
            return []
        
        try:
            # Check if collection exists
            if not self.client.has_collection(self.collection_name):
                logger.warning(f"Collection {self.collection_name} does not exist")
                return []
            
            self.client.load_collection(self.collection_name)
            query_vector = self._generate_embedding(query_text)
            
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                limit=limit * 2,
                output_fields=[
                    "document_id", "file_name", "file_path", "file_type",
                    "total_pages", "total_words", "folder_name", "timestamp", "content"
                ]
            )
            
            # Process search results
            doc_results = {}
            for hit in results[0]:
                entity = hit["entity"]
                doc_id = entity["document_id"]
                similarity = 1 - hit["distance"]
                
                if doc_id not in doc_results or similarity > doc_results[doc_id]["similarity_score"]:
                    doc_results[doc_id] = {
                        "id": doc_id,
                        "similarity_score": similarity,
                        "file_name": entity["file_name"],
                        "file_path": entity["file_path"],
                        "file_type": entity["file_type"],
                        "total_pages": entity["total_pages"],
                        "total_words": entity["total_words"],
                        "folder_name": entity["folder_name"],
                        "content_preview": entity["content"][:300] + "...",
                        "timestamp": entity["timestamp"]
                    }
            
            formatted_results = list(doc_results.values())
            formatted_results.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            logger.info(f"Found {len(formatted_results)} similar documents in {self.collection_name}")
            return formatted_results[:limit]
            
        except Exception as e:
            logger.error(f"Search failed for collection {self.collection_name}: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Get collection statistics"""
        if not self.is_available():
            return {"error": "Milvus not available"}
        
        try:
            # Check if collection exists
            if not self.client.has_collection(self.collection_name):
                return {
                    "collection_name": self.collection_name,
                    "error": "Collection does not exist",
                    "total_documents": 0,
                    "total_images": 0,
                    "total_chunks": 0
                }
            
            self.client.load_collection(self.collection_name)
            
            result = self.client.query(
                collection_name=self.collection_name,
                filter="",
                output_fields=["file_type", "folder_name", "document_id"],
                limit=10000
            )
            
            # Calculate statistics
            unique_docs = set()
            image_count = 0
            file_types = {}
            folders = {}
            
            for doc in result:
                if doc.get("file_type") == "image_metadata":
                    image_count += 1
                else:
                    unique_docs.add(doc.get("document_id", doc.get("id", "")))
                
                ft = doc.get("file_type", "unknown")
                file_types[ft] = file_types.get(ft, 0) + 1
                fn = doc.get("folder_name", "unknown")
                folders[fn] = folders.get(fn, 0) + 1
            
            return {
                "total_documents": len(unique_docs),
                "total_images": image_count,
                "total_chunks": len(result) - image_count,
                "file_types": file_types,
                "folders": folders,
                "embedding_model": "all-MiniLM-L6-v2 (Sentence Transformers)",
                "embedding_dimension": self.embedding_dim,
                "collection_name": self.collection_name
            }
        except Exception as e:
            logger.error(f"Stats query failed for collection {self.collection_name}: {e}")
            return {"error": str(e)}

# Global instances for different collections
_milvus_clients = {}

def get_milvus_client(collection_name: str = "rfp_documents"):
    """Get or create Milvus client for specific collection"""
    global _milvus_clients
    
    if collection_name not in _milvus_clients:
        _milvus_clients[collection_name] = MilvusVectorClient(collection_name)
        logger.info(f"Created new Milvus client for collection: {collection_name}")
    
    return _milvus_clients[collection_name]

def get_rfp_client():
    """Get Milvus client for RFP files"""
    return get_milvus_client("rfp_files")

def get_supportive_client():
    """Get Milvus client for supportive files"""
    return get_milvus_client("supportive_files")
