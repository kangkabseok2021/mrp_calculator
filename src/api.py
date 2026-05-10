from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3
import pandas as pd
import os
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta

from mrp_engine import MRPEngine
from auth import get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, verify_password, get_user

app = FastAPI(title="MRP ERP System")

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mrp_database.db'))

class InventoryUpdate(BaseModel):
    item_id: str
    on_hand_qty: int

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.post("/api/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user['hashed_password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/inventory")
def get_inventory(current_user: dict = Depends(get_current_user)):
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
def update_inventory(update: InventoryUpdate, current_user: dict = Depends(get_current_user)):
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
def run_mrp(current_user: dict = Depends(get_current_user)):
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
def get_bom(current_user: dict = Depends(get_current_user)):
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
def commit_pos(current_user: dict = Depends(get_current_user)):
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
def get_pos(current_user: dict = Depends(get_current_user)):
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
def update_po_status(update: POStatusUpdate, current_user: dict = Depends(get_current_user)):
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

class BOMUpdate(BaseModel):
    parent_id: str
    child_id: str
    qty_required: int

class BOMAdd(BaseModel):
    parent_id: str
    child_id: str
    qty_required: int

class BOMRemove(BaseModel):
    parent_id: str
    child_id: str

@app.get("/api/bom/tree")
def get_bom_tree(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all items
    cursor.execute("SELECT item_id, description, item_type FROM Items")
    items = {row['item_id']: dict(row) for row in cursor.fetchall()}
    
    # Get all BOM relationships
    cursor.execute("SELECT parent_item_id, child_item_id, qty_required FROM BOM")
    bom_rows = cursor.fetchall()
    
    conn.close()
    
    # Find root nodes (Items that are parents but never children)
    all_parents = set(row['parent_item_id'] for row in bom_rows)
    all_children = set(row['child_item_id'] for row in bom_rows)
    roots = all_parents - all_children
    
    # Build tree
    def build_node(item_id, qty=1):
        node = {
            'item_id': item_id,
            'description': items[item_id]['description'],
            'item_type': items[item_id]['item_type'],
            'qty_required': qty,
            'children': []
        }
        for row in bom_rows:
            if row['parent_item_id'] == item_id:
                node['children'].append(build_node(row['child_item_id'], row['qty_required']))
        return node

    tree = [build_node(root) for root in roots]
    return tree

@app.get("/api/items")
def get_items(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, description, item_type FROM Items ORDER BY item_id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def check_circular(cursor, new_parent, new_child):
    # If we add parent -> child, we must ensure child does not eventually lead to parent
    # BFS starting from child
    queue = [new_child]
    visited = set([new_child])
    
    while queue:
        current = queue.pop(0)
        if current == new_parent:
            return True
        cursor.execute("SELECT child_item_id FROM BOM WHERE parent_item_id = ?", (current,))
        for row in cursor.fetchall():
            if row['child_item_id'] not in visited:
                visited.add(row['child_item_id'])
                queue.append(row['child_item_id'])
    return False

@app.post("/api/bom/add")
def add_bom(add: BOMAdd, current_user: dict = Depends(get_current_user)):
    if add.parent_id == add.child_id:
        raise HTTPException(status_code=400, detail="An item cannot be a component of itself.")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if relationship already exists
    cursor.execute("SELECT 1 FROM BOM WHERE parent_item_id = ? AND child_item_id = ?", (add.parent_id, add.child_id))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="This component relationship already exists.")
        
    if check_circular(cursor, add.parent_id, add.child_id):
        conn.close()
        raise HTTPException(status_code=400, detail="Circular dependency detected.")
        
    cursor.execute(
        "INSERT INTO BOM (parent_item_id, child_item_id, qty_required) VALUES (?, ?, ?)",
        (add.parent_id, add.child_id, add.qty_required)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/bom/update")
def update_bom(update: BOMUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE BOM SET qty_required = ? WHERE parent_item_id = ? AND child_item_id = ?",
        (update.qty_required, update.parent_id, update.child_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/bom/remove")
def remove_bom(remove: BOMRemove, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM BOM WHERE parent_item_id = ? AND child_item_id = ?",
        (remove.parent_id, remove.child_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

class ForecastAdd(BaseModel):
    item_id: str
    due_date: int
    demand_qty: int

class ForecastUpdate(BaseModel):
    rowid: int
    due_date: int
    demand_qty: int

class ForecastRemove(BaseModel):
    rowid: int

@app.get("/api/forecast")
def get_forecast(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.rowid, f.item_id, f.due_date, f.demand_qty, it.description, it.item_type
        FROM Forecast f
        JOIN Items it ON f.item_id = it.item_id
        ORDER BY f.due_date ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/forecast/add")
def add_forecast(add: ForecastAdd, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Forecast (item_id, due_date, demand_qty) VALUES (?, ?, ?)",
        (add.item_id, add.due_date, add.demand_qty)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/forecast/update")
def update_forecast(update: ForecastUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Forecast SET due_date = ?, demand_qty = ? WHERE rowid = ?",
        (update.due_date, update.demand_qty, update.rowid)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/forecast/remove")
def remove_forecast(remove: ForecastRemove, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Forecast WHERE rowid = ?", (remove.rowid,))
    conn.commit()
    conn.close()
    return {"status": "success"}

class SupplierAdd(BaseModel):
    name: str
    contact_email: str
    lead_time_modifier: int

class SupplierUpdate(BaseModel):
    supplier_id: int
    name: str
    contact_email: str
    lead_time_modifier: int

class SupplierRemove(BaseModel):
    supplier_id: int

@app.get("/api/suppliers")
def get_suppliers(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Suppliers ORDER BY supplier_id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/suppliers/add")
def add_supplier(add: SupplierAdd, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Suppliers (name, contact_email, lead_time_modifier) VALUES (?, ?, ?)",
        (add.name, add.contact_email, add.lead_time_modifier)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/suppliers/update")
def update_supplier(update: SupplierUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Suppliers SET name = ?, contact_email = ?, lead_time_modifier = ? WHERE supplier_id = ?",
        (update.name, update.contact_email, update.lead_time_modifier, update.supplier_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/suppliers/remove")
def remove_supplier(remove: SupplierRemove, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if supplier is used by any item
    cursor.execute("SELECT 1 FROM Items WHERE default_supplier_id = ?", (remove.supplier_id,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot delete supplier: currently assigned to items.")
    cursor.execute("DELETE FROM Suppliers WHERE supplier_id = ?", (remove.supplier_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

from fastapi.responses import StreamingResponse
import io
from fpdf import FPDF
from jose import JWTError, jwt

@app.get("/api/export/mrp/excel")
def export_mrp_excel(token: str):
    # Verify token manually since it's a query param for window.open
    try:
        from auth import SECRET_KEY, ALGORITHM, get_user
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not get_user(username):
            raise HTTPException(status_code=401)
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    engine = MRPEngine(DB_PATH)
    results = engine.run()
    
    df = pd.DataFrame(results)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="MRP_Schedule")
    
    output.seek(0)
    headers = {
        'Content-Disposition': 'attachment; filename="mrp_schedule.xlsx"'
    }
    return StreamingResponse(output, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.get("/api/export/mrp/pdf")
def export_mrp_pdf(token: str):
    try:
        from auth import SECRET_KEY, ALGORITHM, get_user
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not get_user(username):
            raise HTTPException(status_code=401)
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    engine = MRPEngine(DB_PATH)
    results = engine.run()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    
    pdf.cell(200, 10, txt="Nexus ERP - MRP Schedule", ln=1, align='C')
    pdf.ln(10)
    
    if not results:
        pdf.cell(200, 10, txt="No purchase orders required.", ln=1)
    else:
        # Basic Table Header
        pdf.set_font("helvetica", style="B", size=10)
        pdf.cell(40, 10, "Item ID", 1)
        pdf.cell(40, 10, "Quantity", 1)
        pdf.cell(40, 10, "Order Date", 1)
        pdf.cell(40, 10, "Due Date", 1)
        pdf.ln()
        
        pdf.set_font("helvetica", size=10)
        for r in results:
            pdf.cell(40, 10, str(r['item_id']), 1)
            pdf.cell(40, 10, str(r['qty']), 1)
            pdf.cell(40, 10, str(r['order_date']), 1)
            pdf.cell(40, 10, str(r['due_date']), 1)
            pdf.ln()
            
    pdf_output = pdf.output(dest='S')
    
    headers = {
        'Content-Disposition': 'attachment; filename="mrp_schedule.pdf"'
    }
    return StreamingResponse(io.BytesIO(pdf_output), headers=headers, media_type="application/pdf")

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
