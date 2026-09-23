"""
Database migration script to add new columns to tracks table.

Adds: album_artist, track_number, disc_number, publisher, catalog_number, composer
Removes: tags_json
"""
import sqlite3
import sys
from pathlib import Path


def migrate_database(db_path: str):
    """Add new columns to tracks table."""
    print(f"Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(tracks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Current columns: {columns}")
        
        # Add new columns if they don't exist
        new_columns = {
            'album_artist': 'VARCHAR(255)',
            'track_number': 'VARCHAR(32)',
            'disc_number': 'VARCHAR(32)',
            'publisher': 'VARCHAR(255)',
            'catalog_number': 'VARCHAR(255)',
            'composer': 'VARCHAR(255)',
        }
        
        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                print(f"Adding column: {col_name}")
                cursor.execute(f"ALTER TABLE tracks ADD COLUMN {col_name} {col_type}")
            else:
                print(f"Column {col_name} already exists, skipping")
        
        # Remove tags_json column if it exists (optional, SQLite doesn't support DROP COLUMN easily)
        if 'tags_json' in columns:
            print("Note: tags_json column still exists (SQLite doesn't support DROP COLUMN)")
            print("      It will be ignored but won't cause issues")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        sys.exit(1)
    
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate database schema")
    parser.add_argument(
        "--db",
        default="data/library.db",
        help="Path to SQLite database file"
    )
    
    args = parser.parse_args()
    
    db_file = Path(args.db)
    if not db_file.exists():
        print(f"Error: Database file not found: {args.db}")
        sys.exit(1)
    
    migrate_database(args.db)
