from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3
import pandas as pd
import os

from mrp_engine import MRPEngine

app = FastAPI(title="MRP ERP System")

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mrp_database.db'))

class InventoryUpdate(BaseModel):
    item_id: str
    on_hand_qty: int

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/inventory")
def get_inventory():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.item_id, i.on_hand_qty, it.description, it.item_type
        FROM Inventory i
        JOIN Items it ON i.item_id = it.item_id
        ORDER BY i.item_id
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/inventory/update")
def update_inventory(update: InventoryUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Inventory SET on_hand_qty = ? WHERE item_id = ?",
        (update.on_hand_qty, update.item_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Updated {update.item_id} to {update.on_hand_qty}"}

@app.get("/api/mrp/run")
def run_mrp():
    try:
        engine = MRPEngine(DB_PATH)
        engine.run()
        por = engine.get_planned_orders()
        if por.empty:
            return []
            
        por = por.sort_values(['release_date', 'item_id'])
        return por.to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bom")
def get_bom():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT parent_item_id, child_item_id, qty_required 
        FROM BOM
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Mount static directory to serve frontend
# Using check_dir to only mount if the directory exists (it should when we create it)
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))

# To run: uvicorn api:app --reload --host 0.0.0.0 --port 8000
