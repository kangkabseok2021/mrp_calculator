import sqlite3
import pandas as pd

class MRPEngine:
    """
    Material Requirements Planning (MRP) Engine.
    Computes required raw material orders based on Forecast, BOM, Inventory, and Lead Times.
    """
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.items = pd.read_sql("SELECT * FROM Items", self.conn)
        self.inventory = pd.read_sql("SELECT * FROM Inventory", self.conn)
        self.bom = pd.read_sql("SELECT * FROM BOM", self.conn)
        self.forecast = pd.read_sql("SELECT * FROM Forecast", self.conn)
        
        # Lookup dictionaries for fast access
        self.lead_times = dict(zip(self.items.item_id, self.items.lead_time_days))
        self.on_hand = dict(zip(self.inventory.item_id, self.inventory.on_hand_qty))
        
        # Ensure all items exist in the inventory dictionary
        for item in self.items.item_id:
            if item not in self.on_hand:
                self.on_hand[item] = 0
                
        self.llc = self._calculate_llc()
        self.gross_requirements = []  # [{'item_id': str, 'due_date': int, 'qty': int}]
        self.planned_order_releases = [] # [{'item_id': str, 'release_date': int, 'due_date': int, 'qty': int}]

    def _calculate_llc(self):
        """
        Calculates Low-Level Code (LLC) for all items.
        Finished Goods are 0. Subcomponents have higher values.
        """
        llc = {item: 0 for item in self.items.item_id}
        
        changed = True
        while changed:
            changed = False
            for _, row in self.bom.iterrows():
                parent = row['parent_item_id']
                child = row['child_item_id']
                
                # The child must be at a lower level (higher LLC number) than its lowest parent
                if llc[child] <= llc[parent]:
                    llc[child] = llc[parent] + 1
                    changed = True
        return llc

    def run(self):
        """
        Executes the main MRP logic level by level.
        """
        # 1. Initialize Gross Requirements from Forecast (Level 0 demand)
        for _, row in self.forecast.iterrows():
            self.gross_requirements.append({
                'item_id': row['item_id'],
                'due_date': row['due_date'],
                'qty': row['demand_qty']
            })
            
        max_llc = max(self.llc.values()) if self.llc else 0
        
        # 2. Process MRP level by level
        for current_llc in range(max_llc + 1):
            items_at_level = [item for item, level in self.llc.items() if level == current_llc]
            
            for item in items_at_level:
                # Gather all gross requirements for this item
                item_gr = [gr for gr in self.gross_requirements if gr['item_id'] == item]
                
                gr_df = pd.DataFrame(item_gr)
                if gr_df.empty:
                    continue
                    
                # Group by due_date to combine overlapping demands and sort chronologically
                gr_df = gr_df.groupby('due_date', as_index=False)['qty'].sum().sort_values('due_date')
                
                for _, row in gr_df.iterrows():
                    due_date = int(row['due_date'])
                    qty = int(row['qty'])
                    
                    # Consume available on-hand inventory
                    if self.on_hand[item] > 0:
                        consumed = min(self.on_hand[item], qty)
                        qty -= consumed
                        self.on_hand[item] -= consumed
                        
                    # Net Requirement is whatever is left to satisfy
                    if qty > 0:
                        release_date = due_date - self.lead_times[item]
                        por_qty = qty
                        
                        # Record the Planned Order Release
                        self.planned_order_releases.append({
                            'item_id': item,
                            'release_date': release_date,
                            'due_date': due_date,
                            'qty': por_qty
                        })
                        
                        # Propagate demand down to child components
                        children = self.bom[self.bom['parent_item_id'] == item]
                        for _, child_row in children.iterrows():
                            child = child_row['child_item_id']
                            child_qty = child_row['qty_required'] * por_qty
                            
                            self.gross_requirements.append({
                                'item_id': child,
                                'due_date': release_date, # Due date for child is when the parent needs to start
                                'qty': child_qty
                            })

    def get_planned_orders(self):
        """Returns the planned order schedule as a Pandas DataFrame."""
        return pd.DataFrame(self.planned_order_releases)

if __name__ == "__main__":
    engine = MRPEngine("mrp_database.db")
    engine.run()
    por = engine.get_planned_orders()
    
    if not por.empty:
        por = por.sort_values(['release_date', 'item_id'])
        print("\n--- Planned Order Releases (Purchase Schedule) ---")
        print(por.to_string(index=False))
    else:
        print("No planned orders generated.")
