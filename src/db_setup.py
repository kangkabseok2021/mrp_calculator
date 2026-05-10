import sqlite3
import os

DB_FILE = "mrp_database.db"

def setup_database():
    # Ensure we start fresh or clear existing
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Drop existing tables to reset
    tables = ["Items", "Inventory", "BOM", "Forecast"]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    # Create Items Table
    cursor.execute("""
        CREATE TABLE Items (
            item_id TEXT PRIMARY KEY,
            description TEXT,
            item_type TEXT,
            lead_time_days INTEGER
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

    # Insert Sample Data - "Bicycle"

    items_data = [
        ("FG001", "Mountain Bike", "FG", 1),
        ("SA001", "Wheel Assembly", "SA", 2),
        ("SA002", "Frame Assembly", "SA", 3),
        ("RM001", "Tire", "RM", 5),
        ("RM002", "Rim", "RM", 4),
        ("RM003", "Spokes", "RM", 3),
        ("RM004", "Frame Tube", "RM", 7),
        ("RM005", "Handlebar", "RM", 4),
        ("RM006", "Pedals", "RM", 2)
    ]
    cursor.executemany("INSERT INTO Items VALUES (?, ?, ?, ?)", items_data)

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

    bom_data = [
        ("FG001", "SA001", 2),  # 2 Wheels per bike
        ("FG001", "SA002", 1),  # 1 Frame assembly per bike
        ("FG001", "RM005", 1),  # 1 Handlebar per bike
        ("FG001", "RM006", 2),  # 2 Pedals per bike
        ("SA001", "RM001", 1),  # 1 Tire per wheel
        ("SA001", "RM002", 1),  # 1 Rim per wheel
        ("SA001", "RM003", 36), # 36 Spokes per wheel
        ("SA002", "RM004", 1)   # 1 Frame Tube set per Frame Assembly
    ]
    cursor.executemany("INSERT INTO BOM VALUES (?, ?, ?)", bom_data)

    forecast_data = [
        ("FG001", 15, 50),  # Demand of 50 bikes on day 15
        ("FG001", 20, 100)  # Demand of 100 bikes on day 20
    ]
    cursor.executemany("INSERT INTO Forecast VALUES (?, ?, ?)", forecast_data)

    conn.commit()
    conn.close()
    print("Database setup complete with sample Bicycle data.")

if __name__ == "__main__":
    setup_database()
