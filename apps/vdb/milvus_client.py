from pymilvus import MilvusClient, DataType
from sentence_transformers import SentenceTransformer
import logging
import uuid
import os
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class MilvusVectorClient:
    def __init__(self):
        self.uri = os.getenv("MILVUS_URI", "http://localhost:19530")
        self.collection_name = "rfp_documents"
        
        # Sentence Transformers
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.embedding_dim = 384
            logger.info("Sentence Transformer model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Sentence Transformer: {e}")
            self.embedding_model = None
        
        try:
            self.client = MilvusClient(uri=self.uri)
            self._ensure_collection()
            logger.info("Milvus client initialized successfully")
        except Exception as e:
            logger.error(f"Milvus initialization failed: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        return self.client is not None and self.embedding_model is not None
    
    def _chunk_content_by_bytes(self, text: str, max_bytes=15000) -> List[str]:
        """Chunk text by byte length to ensure Milvus compatibility"""
        chunks = []
        
        text_bytes = text.encode('utf-8')
        
        if len(text_bytes) <= max_bytes:
            return [text]
        
        words = text.split()
        current_chunk = []
        current_bytes = 0
        
        for word in words:
            word_bytes = len(word.encode('utf-8')) + 1  
            
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
        for i, chunk in enumerate(chunks):
            chunk_bytes = len(chunk.encode('utf-8'))
            if chunk_bytes > max_bytes:
                logger.warning(f"Chunk {i} still exceeds byte limit: {chunk_bytes} bytes")
                chunks[i] = chunk[:max_bytes//2] + "..."  
        
        return chunks
    
    def _ensure_collection(self):
        if self.client.has_collection(self.collection_name):
            try:
                self.client.drop_collection(self.collection_name)
                logger.info(f"Dropped existing collection: {self.collection_name}")
            except Exception as e:
                logger.warning(f"Error dropping collection: {e}")

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
        
        self.client.create_collection(collection_name=self.collection_name, schema=schema)
        
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
        
        try:
            self.client.load_collection(self.collection_name)
            logger.info("Collection loaded successfully")
        except Exception as e:
            logger.warning(f"Collection loading warning: {e}")
    
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
    
    def save_documents(self, ocr_results: List[Dict], folder_name: str) -> List[str]:
        """Save documents with byte-based chunking to handle Arabic text"""
        if not self.is_available() or not ocr_results:
            logger.warning("Milvus or embedding model not available")
            return []
        documents = {}
        for result in ocr_results:
            file_name = result.get('file_name', 'unknown')
            if file_name not in documents:
                documents[file_name] = {'pages': [], 'info': result}
            documents[file_name]['pages'].append(result)
        
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
                
                logger.info(f"Prepared {len(content_chunks)} chunks for {file_name} (total bytes: {len(full_content.encode('utf-8'))})")
                
            except Exception as e:
                logger.error(f"Error processing {file_name}: {e}")
                continue
        
        if entities:
            try:
                self.client.load_collection(self.collection_name)
                batch_size = 25  
                inserted_count = 0
                
                logger.info(f"Inserting {len(entities)} entities in batches of {batch_size}...")
                
                for i in range(0, len(entities), batch_size):
                    batch = entities[i:i + batch_size]
                    for j, entity in enumerate(batch):
                        content_bytes = len(entity["content"].encode('utf-8'))
                        if content_bytes > 15000:
                            logger.error(f"Entity {j} in batch {i//batch_size + 1} exceeds byte limit: {content_bytes}")
                            continue
                    
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
                
                try:
                    self.client.flush(collection_name=self.collection_name)
                    logger.info(f"Flushed data to disk. Total inserted: {inserted_count}")
                except Exception as e:
                    logger.error(f"Flush failed: {e}")
                try:
                    self.client.load_collection(self.collection_name)
                    stats = self.client.query(
                        collection_name=self.collection_name,
                        filter="",
                        output_fields=["id"],
                        limit=1
                    )
                    
                    if stats:
                        logger.info(f"Verification: Data successfully stored in Milvus")
                    else:
                        logger.warning("Verification: No data found after insertion")
                        
                except Exception as e:
                    logger.error(f"Verification failed: {e}")
                
                logger.info(f"Successfully saved {len(documents)} documents ({inserted_count} chunks) to Milvus")
                return doc_ids
                
            except Exception as e:
                logger.error(f"Insert operation failed: {e}")
                return []
        else:
            logger.warning("No valid entities to insert")
            return []
    
    def get_all_documents(self, limit: int = 100) -> List[Dict]:
        """Get all stored documents, grouping chunks by document_id"""
        if not self.is_available():
            return []
        
        try:
            self.client.load_collection(self.collection_name)
            
            result = self.client.query(
                collection_name=self.collection_name,
                filter="",
                output_fields=["*"],
                limit=limit * 3
            )
            
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
            
            return formatted_docs
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    def search_similar_documents(self, query_text: str, limit: int = 10) -> List[Dict]:
        """Search for similar documents"""
        if not self.is_available():
            return []
        
        try:
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
            
            return formatted_results[:limit]
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_stats(self) -> Dict:
        if not self.is_available():
            return {"error": "Milvus not available"}
        
        try:
            self.client.load_collection(self.collection_name)
            
            result = self.client.query(
                collection_name=self.collection_name,
                filter="",
                output_fields=["file_type", "folder_name", "document_id"],
                limit=10000
            )
            
            unique_docs = set(r.get("document_id", r.get("id", "")) for r in result)
            
            file_types = {}
            folders = {}
            for doc in result:
                ft = doc.get("file_type", "unknown")
                file_types[ft] = file_types.get(ft, 0) + 1
                fn = doc.get("folder_name", "unknown")
                folders[fn] = folders.get(fn, 0) + 1
            
            return {
                "total_documents": len(unique_docs),
                "total_chunks": len(result),
                "file_types": file_types,
                "folders": folders,
                "embedding_model": "all-MiniLM-L6-v2 (Sentence Transformers)",
                "embedding_dimension": self.embedding_dim,
                "collection_name": self.collection_name
            }
        except Exception as e:
            logger.error(f"Stats query failed: {e}")
            return {"error": str(e)}

# Global instance
_milvus_client = None

def get_milvus_client():
    global _milvus_client
    if _milvus_client is None:
        _milvus_client = MilvusVectorClient()
    return _milvus_client
