"""
Cache service for Answer.json to provide quick SQL retrieval for known questions.
"""
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from difflib import SequenceMatcher

class AnswerCacheService:
    """Service to manage cached answers from Answer.json"""
    
    def __init__(self, cache_file_path: Optional[str] = None):
        """
        Initialize the cache service.
        
        Args:
            cache_file_path: Path to Answer.json file. If None, uses default location.
        """
        if cache_file_path is None:
            # Default to Answer.json in the same directory as this file
            base_dir = Path(__file__).parent.parent
            cache_file_path = base_dir / "Answer.json"
        
        self.cache_file_path = Path(cache_file_path)
        self.cache_data = []
        self.load_cache()
    
    def load_cache(self) -> None:
        """Load the cache from Answer.json file."""
        try:
            if self.cache_file_path.exists():
                with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                    self.cache_data = json.load(f)
                print(f"Loaded {len(self.cache_data)} cached answers from {self.cache_file_path}")
            else:
                print(f"Warning: Cache file not found at {self.cache_file_path}")
                self.cache_data = []
        except Exception as e:
            print(f"Error loading cache: {str(e)}")
            self.cache_data = []
    
    def find_match(self, question: str, similarity_threshold: float = 0.85) -> Optional[Dict[str, Any]]:
        """
        Find a matching question in the cache.
        
        Args:
            question: The user's question to search for
            similarity_threshold: Minimum similarity ratio (0-1) to consider a match
            
        Returns:
            Dictionary with 'sql', 'db_schema', and 'id' if match found, None otherwise
        """
        if not self.cache_data:
            return None
        
        question_lower = question.strip().lower()
        
        # First try exact match (case-insensitive)
        for entry in self.cache_data:
            cached_question = entry.get("question", "").strip().lower()
            if cached_question == question_lower:
                print(f"Exact cache match found for question: {question}")
                return {
                    "sql": entry.get("sql", ""),
                    "db_schema": entry.get("db_schema", ""),
                    "id": entry.get("id"),
                    "question": entry.get("question", question)
                }
        
        # If no exact match, try fuzzy matching
        best_match = None
        best_similarity = 0.0
        
        for entry in self.cache_data:
            cached_question = entry.get("question", "").strip().lower()
            similarity = SequenceMatcher(None, question_lower, cached_question).ratio()
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = entry
        
        if best_similarity >= similarity_threshold:
            print(f"Fuzzy cache match found (similarity: {best_similarity:.2f}) for question: {question}")
            return {
                "sql": best_match.get("sql", ""),
                "db_schema": best_match.get("db_schema", ""),
                "id": best_match.get("id"),
                "question": best_match.get("question", question),
                "similarity": best_similarity
            }
        
        print(f"No cache match found for question: {question}")
        return None
    
    def reload_cache(self) -> None:
        """Reload the cache from the file (useful if Answer.json is updated)."""
        self.load_cache()
    
    def get_cache_size(self) -> int:
        """Get the number of cached entries."""
        return len(self.cache_data)

# Global cache instance
_cache_instance = None

def get_cache_service(cache_file_path: Optional[str] = None) -> AnswerCacheService:
    """Get or create the global cache service instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = AnswerCacheService(cache_file_path)
    return _cache_instance

