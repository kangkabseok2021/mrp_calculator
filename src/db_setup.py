import sqlite3
import os
from passlib.context import CryptContext

DB_FILE = "mrp_database.db"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def setup_database():
    # Ensure we start fresh or clear existing
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Drop existing tables to reset
    tables = ["Users", "Suppliers", "PurchaseOrders", "Items", "Inventory", "BOM", "Forecast"]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    # Create Users Table
    cursor.execute("""
        CREATE TABLE Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            hashed_password TEXT
        )
    """)

    # Create Suppliers Table
    cursor.execute("""
        CREATE TABLE Suppliers (
            supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            contact_email TEXT,
            lead_time_modifier INTEGER DEFAULT 0
        )
    """)

    # Create Items Table (Added default_supplier_id)
    cursor.execute("""
        CREATE TABLE Items (
            item_id TEXT PRIMARY KEY,
            description TEXT,
            item_type TEXT,
            lead_time_days INTEGER,
            default_supplier_id INTEGER,
            FOREIGN KEY(default_supplier_id) REFERENCES Suppliers(supplier_id)
        )
    """)

    # Create Inventory Table
    cursor.execute("""
        CREATE TABLE Inventory (
            item_id TEXT PRIMARY KEY,
            on_hand_qty INTEGER,
            FOREIGN KEY(item_id) REFERENCES Items(item_id)
        )
    """)

    # Create BOM Table
    cursor.execute("""
        CREATE TABLE BOM (
            parent_item_id TEXT,
            child_item_id TEXT,
            qty_required INTEGER,
            FOREIGN KEY(parent_item_id) REFERENCES Items(item_id),
            FOREIGN KEY(child_item_id) REFERENCES Items(item_id)
        )
    """)

    # Create Forecast Table
    cursor.execute("""
        CREATE TABLE Forecast (
            item_id TEXT,
            due_date INTEGER,  -- Storing dates as day integers for simplicity in logic (e.g., Day 15)
            demand_qty INTEGER,
            FOREIGN KEY(item_id) REFERENCES Items(item_id)
        )
    """)

    # Create PurchaseOrders Table
    cursor.execute("""
        CREATE TABLE PurchaseOrders (
            po_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT,
            qty INTEGER,
            order_date INTEGER,
            due_date INTEGER,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY(item_id) REFERENCES Items(item_id)
        )
    """)

    # Insert Sample Data
    
    # 1. Users
    hashed_pwd = pwd_context.hash("admin")
    cursor.execute("INSERT INTO Users (username, hashed_password) VALUES (?, ?)", ("admin", hashed_pwd))

    # 2. Suppliers
    suppliers_data = [
        ("Global Metals Inc", "sales@globalmetals.com", 0),
        ("Advanced Rubber Co", "orders@advancedrubber.com", 1),
        ("Nexus Manufacturing", "internal@nexus.com", 0)
    ]
    cursor.executemany("INSERT INTO Suppliers (name, contact_email, lead_time_modifier) VALUES (?, ?, ?)", suppliers_data)

    # 3. Items (Assigned to Suppliers: 1=Metals, 2=Rubber, 3=Internal)
    items_data = [
        ("FG001", "Mountain Bike", "FG", 1, 3),
        ("SA001", "Wheel Assembly", "SA", 2, 3),
        ("SA002", "Frame Assembly", "SA", 3, 3),
        ("RM001", "Tire", "RM", 5, 2),
        ("RM002", "Rim", "RM", 4, 1),
        ("RM003", "Spokes", "RM", 3, 1),
        ("RM004", "Frame Tube", "RM", 7, 1),
        ("RM005", "Handlebar", "RM", 4, 1),
        ("RM006", "Pedals", "RM", 2, 2)
    ]
    cursor.executemany("INSERT INTO Items VALUES (?, ?, ?, ?, ?)", items_data)

    # 4. Inventory
    inventory_data = [
        ("FG001", 10),
        ("SA001", 20),
        ("SA002", 5),
        ("RM001", 50),
        ("RM002", 40),
        ("RM003", 1000),
        ("RM004", 15),
        ("RM005", 30),
        ("RM006", 40)
    ]
    cursor.executemany("INSERT INTO Inventory VALUES (?, ?)", inventory_data)

    # 5. BOM
    bom_data = [
        ("FG001", "SA001", 2),
        ("FG001", "SA002", 1),
        ("FG001", "RM005", 1),
        ("FG001", "RM006", 2),
        ("SA001", "RM001", 1),
        ("SA001", "RM002", 1),
        ("SA001", "RM003", 36),
        ("SA002", "RM004", 1)
    ]
    cursor.executemany("INSERT INTO BOM VALUES (?, ?, ?)", bom_data)

    # 6. Forecast
    forecast_data = [
        ("FG001", 15, 50),
        ("FG001", 20, 100)
    ]
    cursor.executemany("INSERT INTO Forecast VALUES (?, ?, ?)", forecast_data)

    conn.commit()
    conn.close()
    print("Database setup complete with Auth and Supplier tables.")

if __name__ == "__main__":
    setup_database()
