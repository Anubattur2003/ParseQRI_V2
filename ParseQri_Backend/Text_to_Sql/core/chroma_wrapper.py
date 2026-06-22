"""
ChromaDB wrapper that bypasses telemetry issues
"""
import os
import tempfile
import sqlite3
from typing import Dict, List, Any, Optional
import json


class SimpleVectorDB:
    """Simple vector database implementation that mimics ChromaDB without telemetry"""
    
    def __init__(self, path: str):
        self.path = path
        os.makedirs(path, exist_ok=True)
        self.db_path = os.path.join(path, "simple_vector_db.sqlite")
        self._init_db()
        self.collections = {}
    
    def _init_db(self):
        """Initialize the SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create collections table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                name TEXT PRIMARY KEY,
                metadata TEXT
            )
        """)
        
        # Create documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                collection_name TEXT,
                document TEXT,
                metadata TEXT,
                FOREIGN KEY (collection_name) REFERENCES collections (name)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_or_create_collection(self, name: str, metadata: Dict = None):
        """Get or create a collection"""
        if name not in self.collections:
            self.collections[name] = SimpleCollection(name, self.db_path, metadata or {})
            
            # Store in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO collections (name, metadata) VALUES (?, ?)",
                (name, json.dumps(metadata or {}))
            )
            conn.commit()
            conn.close()
        
        return self.collections[name]
    
    def list_collections(self):
        """List all collections"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM collections")
        collections = [CollectionInfo(row[0]) for row in cursor.fetchall()]
        conn.close()
        return collections
    
    def delete_collection(self, name: str):
        """Delete a collection"""
        if name in self.collections:
            del self.collections[name]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE collection_name = ?", (name,))
        cursor.execute("DELETE FROM collections WHERE name = ?", (name,))
        conn.commit()
        conn.close()
    
    def create_collection(self, name: str, metadata: Dict = None):
        """Create a new collection"""
        if name in self.collections:
            raise ValueError(f"Collection {name} already exists")
        return self.get_or_create_collection(name, metadata)


class CollectionInfo:
    """Simple collection info class"""
    def __init__(self, name: str):
        self.name = name


class SimpleCollection:
    """Simple collection implementation"""
    
    def __init__(self, name: str, db_path: str, metadata: Dict):
        self.name = name
        self.db_path = db_path
        self.metadata = metadata
    
    def upsert(self, documents: List[str], metadatas: List[Dict], ids: List[str]):
        """Add or update documents"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for doc, meta, doc_id in zip(documents, metadatas, ids):
            cursor.execute(
                "INSERT OR REPLACE INTO documents (id, collection_name, document, metadata) VALUES (?, ?, ?, ?)",
                (doc_id, self.name, doc, json.dumps(meta))
            )
        
        conn.commit()
        conn.close()
    
    def get(self, where: Dict = None, ids: List[str] = None) -> Dict:
        """Get documents from collection"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if ids:
            placeholders = ','.join(['?' for _ in ids])
            cursor.execute(
                f"SELECT id, document, metadata FROM documents WHERE collection_name = ? AND id IN ({placeholders})",
                [self.name] + ids
            )
        else:
            cursor.execute(
                "SELECT id, document, metadata FROM documents WHERE collection_name = ?",
                (self.name,)
            )
        
        rows = cursor.fetchall()
        conn.close()
        
        result = {
            'ids': [],
            'documents': [],
            'metadatas': []
        }
        
        for row in rows:
            doc_id, document, metadata_str = row
            metadata = json.loads(metadata_str) if metadata_str else {}
            
            # Apply where filter if provided
            if where and not self._matches_where(metadata, where):
                continue
                
            result['ids'].append(doc_id)
            result['documents'].append(document)
            result['metadatas'].append(metadata)
        
        return result
    
    def _matches_where(self, metadata: Dict, where: Dict) -> bool:
        """Check if metadata matches where clause"""
        if "$and" in where:
            return all(self._matches_condition(metadata, cond) for cond in where["$and"])
        elif "$or" in where:
            return any(self._matches_condition(metadata, cond) for cond in where["$or"])
        else:
            return self._matches_condition(metadata, where)
    
    def _matches_condition(self, metadata: Dict, condition: Dict) -> bool:
        """Check if metadata matches a single condition"""
        for key, value in condition.items():
            if isinstance(value, dict) and "$eq" in value:
                if metadata.get(key) != value["$eq"]:
                    return False
            elif metadata.get(key) != value:
                return False
        return True
    
    def query(self, query_texts: List[str], n_results: int = 10, where: Dict = None) -> Dict:
        """Query the collection (simplified - just returns first n_results)"""
        all_docs = self.get(where=where)
        
        # Simple text matching - in a real implementation, this would use embeddings
        result = {
            'ids': [all_docs['ids'][:n_results]],
            'documents': [all_docs['documents'][:n_results]],
            'metadatas': [all_docs['metadatas'][:n_results]]
        }
        
        return result


# Global simple client instance
_simple_client = None
_simple_collections = {}


def get_simple_chroma_client():
    """Get or create a simple ChromaDB client"""
    global _simple_client
    
    if _simple_client is None:
        chroma_db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents", "chroma_db")
        _simple_client = SimpleVectorDB(chroma_db_dir)
    
    return _simple_client


def get_or_create_simple_collection(collection_name: str, metadata: dict = None):
    """Get or create a simple collection"""
    client = get_simple_chroma_client()
    return client.get_or_create_collection(collection_name, metadata)

