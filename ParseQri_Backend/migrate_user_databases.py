#!/usr/bin/env python3
"""
Migration script to update user_databases table for MSSQL support
"""

from sqlalchemy import create_engine, text
from app.core.config import settings
import sys

def migrate_user_databases():
    """Update user_databases table structure for MSSQL support"""
    
    try:
        # Create engine for MySQL (the app database)
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as connection:
            print("🔄 Starting user_databases table migration...")
            
            # Start transaction
            trans = connection.begin()
            
            try:
                # Check if old columns exist
                result = connection.execute(text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'user_databases' 
                    AND TABLE_SCHEMA = DATABASE()
                """))
                
                existing_columns = [row[0] for row in result.fetchall()]
                print(f"📋 Existing columns: {existing_columns}")
                
                # Backup existing data if old structure exists
                if 'host' in existing_columns:
                    print("💾 Backing up existing data...")
                    result = connection.execute(text("SELECT * FROM user_databases"))
                    existing_data = result.fetchall()
                    print(f"📊 Found {len(existing_data)} existing records")
                
                # Drop and recreate table with new structure
                print("🗑️ Dropping old table structure...")
                connection.execute(text("DROP TABLE IF EXISTS user_databases"))
                
                print("🔨 Creating new table structure...")
                connection.execute(text("""
                    CREATE TABLE user_databases (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        db_type VARCHAR(50) NOT NULL DEFAULT 'mssql',
                        server_name VARCHAR(255) NOT NULL,
                        database_name VARCHAR(255) NOT NULL,
                        use_windows_auth BOOLEAN NOT NULL DEFAULT TRUE,
                        description VARCHAR(500) NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_id (user_id)
                    )
                """))
                
                print("✅ New table structure created successfully!")
                print("📝 Table now supports:")
                print("   - server_name: SQL Server instance name")
                print("   - database_name: Database name")
                print("   - use_windows_auth: Windows Authentication flag")
                print("   - description: Optional description")
                
                # Commit transaction
                trans.commit()
                print("✅ Migration completed successfully!")
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Migration failed: {str(e)}")
                raise
                
    except Exception as e:
        print(f"❌ Error connecting to database: {str(e)}")
        print("💡 Make sure your MySQL server is running and DATABASE_URL is configured correctly")
        sys.exit(1)

def verify_migration():
    """Verify the migration was successful"""
    try:
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as connection:
            # Check new table structure
            result = connection.execute(text("""
                DESCRIBE user_databases
            """))
            
            columns = result.fetchall()
            print("\n🔍 Verifying new table structure:")
            for column in columns:
                print(f"   {column[0]}: {column[1]} {column[2] if column[2] else ''}")
            
            # Check for required columns
            column_names = [col[0] for col in columns]
            required_columns = ['server_name', 'database_name', 'use_windows_auth', 'description']
            
            missing_columns = [col for col in required_columns if col not in column_names]
            if missing_columns:
                print(f"❌ Missing required columns: {missing_columns}")
                return False
            
            print("✅ All required columns present!")
            return True
            
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 MSSQL User Databases Migration Tool")
    print("=" * 40)
    
    # Run migration
    migrate_user_databases()
    
    # Verify migration
    if verify_migration():
        print("\n🎉 Migration completed successfully!")
        print("📌 You can now:")
        print("   1. Connect to MSSQL databases using Windows Authentication")
        print("   2. Store multiple database configurations per user")
        print("   3. Extract metadata using database_agent.py")
        print("\n🚀 Ready to start the backend server!")
    else:
        print("\n❌ Migration verification failed!")
        sys.exit(1)
