import sqlite3
import pytest
import os
import sys
import pandas as pd

# Add the src directory to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from mrp_engine import MRPEngine

TEST_DB = "test_mrp.db"

@pytest.fixture
def setup_test_db():
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    # Drop existing tables
    for table in ["Items", "Inventory", "BOM", "Forecast"]:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        
    cursor.execute("CREATE TABLE Items (item_id TEXT PRIMARY KEY, description TEXT, item_type TEXT, lead_time_days INTEGER)")
    cursor.execute("CREATE TABLE Inventory (item_id TEXT PRIMARY KEY, on_hand_qty INTEGER)")
    cursor.execute("CREATE TABLE BOM (parent_item_id TEXT, child_item_id TEXT, qty_required INTEGER)")
    cursor.execute("CREATE TABLE Forecast (item_id TEXT, due_date INTEGER, demand_qty INTEGER)")
    
    # Insert simple test data
    # A -> B (qty 2)
    # A -> C (qty 1)
    # C -> B (qty 1) 
    # Therefore B's LLC should be 2.
    
    items = [
        ("A", "Finished Good", "FG", 1),
        ("B", "Raw Material", "RM", 2),
        ("C", "Sub Assembly", "SA", 3)
    ]
    cursor.executemany("INSERT INTO Items VALUES (?, ?, ?, ?)", items)
    
    inventory = [
        ("A", 10),
        ("B", 50),
        ("C", 5)
    ]
    cursor.executemany("INSERT INTO Inventory VALUES (?, ?)", inventory)
    
    bom = [
        ("A", "B", 2),
        ("A", "C", 1),
        ("C", "B", 1)
    ]
    cursor.executemany("INSERT INTO BOM VALUES (?, ?, ?)", bom)
    
    forecast = [
        ("A", 10, 100) # Demand of 100 on day 10
    ]
    cursor.executemany("INSERT INTO Forecast VALUES (?, ?, ?)", forecast)
    
    conn.commit()
    conn.close()
    
    yield TEST_DB
    
    # Teardown
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_llc_calculation(setup_test_db):
    engine = MRPEngine(setup_test_db)
    # A should be 0, C should be 1, B should be 2
    assert engine.llc["A"] == 0
    assert engine.llc["C"] == 1
    assert engine.llc["B"] == 2

def test_mrp_logic(setup_test_db):
    engine = MRPEngine(setup_test_db)
    engine.run()
    por = engine.get_planned_orders()
    
    # Calculate expected values manually:
    # A: Gross = 100, Inv = 10 -> Net = 90. Due = 10, Release = 10 - 1 = 9. POR = 90.
    # C: Gross (from A) = 90 * 1 = 90 on Day 9. Inv = 5 -> Net = 85. Due = 9, Release = 9 - 3 = 6. POR = 85.
    # B: 
    #   Gross (from A) = 90 * 2 = 180 on Day 9.
    #   Gross (from C) = 85 * 1 = 85 on Day 6.
    #   Total Gross for B: 85 on Day 6, 180 on Day 9.
    #   Inv = 50. 
    #   Day 6: consume 50 -> Net = 35. Due = 6, Release = 6 - 2 = 4. POR = 35.
    #   Day 9: consume 0 -> Net = 180. Due = 9, Release = 9 - 2 = 7. POR = 180.
    
    # Validate A
    por_a = por[por['item_id'] == 'A']
    assert len(por_a) == 1
    assert por_a.iloc[0]['qty'] == 90
    assert por_a.iloc[0]['release_date'] == 9
    
    # Validate C
    por_c = por[por['item_id'] == 'C']
    assert len(por_c) == 1
    assert por_c.iloc[0]['qty'] == 85
    assert por_c.iloc[0]['release_date'] == 6
    
    # Validate B
    por_b = por[por['item_id'] == 'B'].sort_values('release_date')
    assert len(por_b) == 2
    assert por_b.iloc[0]['qty'] == 35
    assert por_b.iloc[0]['release_date'] == 4
    
    assert por_b.iloc[1]['qty'] == 180
    assert por_b.iloc[1]['release_date'] == 7
