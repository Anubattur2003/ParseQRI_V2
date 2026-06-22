import os
import shutil
import chromadb
from chromadb.config import Settings
import argparse

def get_user_confirmation(message: str) -> bool:
    """Get user confirmation before proceeding with deletion"""
    while True:
        response = input(f"\n⚠️  {message} (yes/no): ").lower().strip()
        if response in ['yes', 'y']:
            return True
        if response in ['no', 'n']:
            return False
        print("Please answer 'yes' or 'no'")

def clear_chroma_collection(collection_name: str = "database_metadata") -> None:
    """Clear a specific collection in ChromaDB"""
    try:
        # Get user confirmation
        if not get_user_confirmation(f"Are you sure you want to clear the ChromaDB collection '{collection_name}'?"):
            print("❌ Operation cancelled by user")
            return

        # Initialize ChromaDB client
        chroma_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
        chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        
        # Get the collection
        collection = chroma_client.get_collection(name=collection_name)
        
        # Get all items in the collection
        results = collection.get()
        if results and results['ids']:
            # Delete all items
            collection.delete(ids=results['ids'])
            print(f"✅ Successfully cleared collection: {collection_name}")
        else:
            print(f"ℹ️ Collection {collection_name} is already empty")
            
    except Exception as e:
        print(f"❌ Error clearing ChromaDB collection: {str(e)}")

def delete_json_history() -> None:
    """Delete all JSON files in the schema_history directory"""
    try:
        schema_history_dir = os.path.join("chroma_db", "schema_history")
        if not os.path.exists(schema_history_dir):
            print("ℹ️ Schema history directory does not exist")
            return

        # Count JSON files
        json_files = [f for f in os.listdir(schema_history_dir) if f.endswith('.json')]
        if not json_files:
            print("ℹ️ No JSON files to delete")
            return

        # Get user confirmation with file count
        if not get_user_confirmation(f"Are you sure you want to delete {len(json_files)} JSON schema history files?"):
            print("❌ Operation cancelled by user")
            return

        # Delete all files in the directory
        for filename in json_files:
            file_path = os.path.join(schema_history_dir, filename)
            os.remove(file_path)
            print(f"✅ Deleted: {filename}")
        print("✅ Successfully cleared schema history JSON files")

    except Exception as e:
        print(f"❌ Error deleting JSON files: {str(e)}")

def reset_chroma_db() -> None:
    """Completely reset ChromaDB by deleting its directory"""
    try:
        chroma_dir = "chroma_db"
        if not os.path.exists(chroma_dir):
            print("ℹ️ ChromaDB directory does not exist")
            return

        # Get user confirmation with warning
        if not get_user_confirmation("⚠️  WARNING: This will completely delete all ChromaDB data and schema history.\nAre you absolutely sure you want to proceed?"):
            print("❌ Operation cancelled by user")
            return

        # Delete the entire ChromaDB directory
        shutil.rmtree(chroma_dir)
        print("✅ Successfully reset ChromaDB")
        
        # Recreate the necessary directories
        os.makedirs(chroma_dir)
        os.makedirs(os.path.join(chroma_dir, "schema_history"))
        print("✅ Recreated ChromaDB directories")

    except Exception as e:
        print(f"❌ Error resetting ChromaDB: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Clear ChromaDB and schema history data')
    parser.add_argument('--mode', type=str, choices=['collection', 'json', 'all', 'reset'],
                      default='all', help='What to clear: collection (ChromaDB collection only), '
                      'json (JSON files only), all (both), or reset (complete reset)')
    parser.add_argument('--collection', type=str, default='database_metadata',
                      help='Name of the ChromaDB collection to clear')
    parser.add_argument('--force', action='store_true',
                      help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    print("\n🗑️ Database Clearing Tool")
    print("========================\n")

    # Show warning based on mode
    if not args.force:
        mode_warnings = {
            'collection': "You are about to clear ChromaDB collection data",
            'json': "You are about to delete schema history JSON files",
            'all': "You are about to clear both ChromaDB collection and schema history files",
            'reset': "You are about to completely reset the ChromaDB directory"
        }
        warning = mode_warnings.get(args.mode, "Unknown operation")
        if not get_user_confirmation(f"{warning}. Do you want to continue?"):
            print("❌ Operation cancelled by user")
            return
    
    if args.mode in ['collection', 'all']:
        print("\n📊 Clearing ChromaDB collection...")
        clear_chroma_collection(args.collection)
        
    if args.mode in ['json', 'all']:
        print("\n📄 Clearing JSON schema history...")
        delete_json_history()
        
    if args.mode == 'reset':
        print("\n🔄 Performing complete reset...")
        reset_chroma_db()
    
    print("\n✨ Operation completed!")

if __name__ == "__main__":
    main() 