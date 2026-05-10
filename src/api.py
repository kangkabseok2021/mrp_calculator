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

class POStatusUpdate(BaseModel):
    po_id: int
    status: str

@app.post("/api/po/commit")
def commit_pos():
    try:
        # Run MRP engine to get latest schedule
        engine = MRPEngine(DB_PATH)
        engine.run()
        por = engine.get_planned_orders()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete only Pending POs to avoid duplicate inserts on multiple runs.
        # Ordered and Received POs are preserved.
        cursor.execute("DELETE FROM PurchaseOrders WHERE status = 'Pending'")
        
        if not por.empty:
            po_data = []
            for _, row in por.iterrows():
                po_data.append((row['item_id'], int(row['qty']), int(row['release_date']), int(row['due_date'])))
                
            cursor.executemany(
                "INSERT INTO PurchaseOrders (item_id, qty, order_date, due_date) VALUES (?, ?, ?, ?)", 
                po_data
            )
            
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Schedule committed to Purchase Orders."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pos")
def get_pos():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT po.po_id, po.item_id, po.qty, po.order_date, po.due_date, po.status, it.description
        FROM PurchaseOrders po
        JOIN Items it ON po.item_id = it.item_id
        ORDER BY po.order_date ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/po/status")
def update_po_status(update: POStatusUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check current status
    cursor.execute("SELECT status, item_id, qty FROM PurchaseOrders WHERE po_id = ?", (update.po_id,))
    po = cursor.fetchone()
    
    if not po:
        conn.close()
        raise HTTPException(status_code=404, detail="PO not found")
        
    if po['status'] == 'Received':
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot change status of an already received PO.")

    # Update PO status
    cursor.execute("UPDATE PurchaseOrders SET status = ? WHERE po_id = ?", (update.status, update.po_id))
    
    # If received, add to inventory
    if update.status == 'Received':
        cursor.execute(
            "UPDATE Inventory SET on_hand_qty = on_hand_qty + ? WHERE item_id = ?", 
            (po['qty'], po['item_id'])
        )
        
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"PO {update.po_id} updated to {update.status}"}

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
