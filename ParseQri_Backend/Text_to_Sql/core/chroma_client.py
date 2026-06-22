"""
Centralized ChromaDB client configuration to avoid conflicts
"""
import os
import chromadb
from chromadb.config import Settings

# Global ChromaDB client instance
_chroma_client = None
_chroma_collections = {}
_use_simple_client = False

def get_chroma_client():
    """Get or create a single ChromaDB client instance"""
    global _chroma_client, _use_simple_client
    
    if _chroma_client is None:
        # Create the ChromaDB directory
        chroma_db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents", "chroma_db")
        os.makedirs(chroma_db_dir, exist_ok=True)
        
        try:
            # Try to use the original ChromaDB first
            os.environ["ANONYMIZED_TELEMETRY"] = "False"
            
            # Initialize with consistent settings - completely disable telemetry
            settings = Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
            
            _chroma_client = chromadb.PersistentClient(
                path=chroma_db_dir,
                settings=settings
            )
            print("Successfully initialized ChromaDB client")
            
        except Exception as e:
            print(f"Failed to initialize ChromaDB client: {str(e)}")
            print("Falling back to simple vector database")
            
            # Fall back to simple client
            from .chroma_wrapper import get_simple_chroma_client
            _chroma_client = get_simple_chroma_client()
            _use_simple_client = True
    
    return _chroma_client

def get_or_create_collection(collection_name: str, metadata: dict = None):
    """Get or create a ChromaDB collection"""
    global _chroma_collections, _use_simple_client
    
    if collection_name not in _chroma_collections:
        client = get_chroma_client()
        
        try:
            if _use_simple_client:
                from .chroma_wrapper import get_or_create_simple_collection
                _chroma_collections[collection_name] = get_or_create_simple_collection(
                    collection_name, metadata
                )
            else:
                _chroma_collections[collection_name] = client.get_or_create_collection(
                    name=collection_name,
                    metadata=metadata or {}
                )
        except Exception as e:
            print(f"Error creating collection {collection_name}: {str(e)}")
            
            # If original ChromaDB fails, try simple client
            if not _use_simple_client:
                print("Falling back to simple vector database for collection")
                from .chroma_wrapper import get_or_create_simple_collection
                _chroma_collections[collection_name] = get_or_create_simple_collection(
                    collection_name, metadata
                )
                _use_simple_client = True
            else:
                raise
    
    return _chroma_collections[collection_name]

def reset_chroma_client():
    """Reset the ChromaDB client (useful for testing)"""
    global _chroma_client, _chroma_collections, _use_simple_client
    _chroma_client = None
    _chroma_collections = {}
    _use_simple_client = False
