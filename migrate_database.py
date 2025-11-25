#!/usr/bin/env python3
"""
Database Migration Script
Migrates the existing database to support the new user fields
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Migrate database to new schema with person_id and additional fields"""
    
    db_path = 'instance/face_recognition.db'
    
    # Create instance directory if it doesn't exist
    os.makedirs('instance', exist_ok=True)
    
    print("Starting database migration...")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if person_id column already exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'person_id' not in columns:
            print("Adding new columns to user table...")
            
            # Add new columns to user table
            new_columns = [
                "ALTER TABLE user ADD COLUMN person_id VARCHAR(20)",
                "ALTER TABLE user ADD COLUMN phone VARCHAR(20)",
                "ALTER TABLE user ADD COLUMN address TEXT",
                "ALTER TABLE user ADD COLUMN city VARCHAR(100)",
                "ALTER TABLE user ADD COLUMN college_name VARCHAR(200)",
                "ALTER TABLE user ADD COLUMN course VARCHAR(100)",
                "ALTER TABLE user ADD COLUMN year_of_study VARCHAR(20)"
            ]
            
            for sql in new_columns:
                try:
                    cursor.execute(sql)
                    print(f"Added column: {sql.split('ADD COLUMN')[1].split()[0]}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e):
                        print(f"Column already exists: {sql.split('ADD COLUMN')[1].split()[0]}")
                    else:
                        print(f"Error adding column: {e}")
            
            # Generate person_id for existing users
            cursor.execute("SELECT id FROM user WHERE person_id IS NULL")
            users_without_person_id = cursor.fetchall()
            
            if users_without_person_id:
                print(f"Generating person IDs for {len(users_without_person_id)} existing users...")
                
                for i, (user_id,) in enumerate(users_without_person_id, 1):
                    person_id = f"P{str(i).zfill(3)}"
                    cursor.execute("UPDATE user SET person_id = ? WHERE id = ?", (person_id, user_id))
                    print(f"User ID {user_id} -> Person ID {person_id}")
            
            # Create unique index on person_id
            try:
                cursor.execute("CREATE UNIQUE INDEX idx_user_person_id ON user(person_id)")
                print("Created unique index on person_id")
            except sqlite3.OperationalError as e:
                if "already exists" in str(e):
                    print("Index on person_id already exists")
                else:
                    print(f"Error creating index: {e}")
            
            conn.commit()
            print("Database migration completed successfully!")
            
        else:
            print("Database already has new schema - no migration needed")
        
        # Verify the migration
        cursor.execute("PRAGMA table_info(user)")
        columns = cursor.fetchall()
        
        print("\nCurrent user table schema:")
        for column in columns:
            print(f"   - {column[1]} ({column[2]})")
        
        # Show existing users with person_ids
        cursor.execute("SELECT person_id, name, email FROM user ORDER BY person_id")
        users = cursor.fetchall()
        
        if users:
            print(f"\nExisting users ({len(users)}):")
            for person_id, name, email in users:
                print(f"   - {person_id}: {name} ({email})")
        else:
            print("\nNo existing users found")
        
        conn.close()
        
    except Exception as e:
        print(f"Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Face Recognition Database Migration")
    print("=" * 50)
    
    success = migrate_database()
    
    if success:
        print("\nMigration completed successfully!")
        print("You can now start the application with: python app_opencv_face_detection.py")
    else:
        print("\nMigration failed!")
        print("Please check the error messages above and try again.")
