document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.view-section');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            navLinks.forEach(l => l.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));

            link.classList.add('active');
            const targetId = `${link.dataset.view}-view`;
            document.getElementById(targetId).classList.add('active');
            
            if (link.dataset.view === 'inventory') {
                loadInventory();
            }
        });
    });

    // --- Inventory Management ---
    const inventoryTableBody = document.getElementById('inventory-table-body');
    const refreshBtn = document.getElementById('refresh-inventory');
    
    // Modal elements
    const editModal = document.getElementById('edit-modal');
    const closeBtns = document.querySelectorAll('.close-modal');
    const saveBtn = document.getElementById('save-inventory');
    const editItemId = document.getElementById('edit-item-id');
    const editQty = document.getElementById('edit-qty');

    async function loadInventory() {
        try {
            inventoryTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Loading...</td></tr>';
            const res = await fetch('/api/inventory');
            const data = await res.json();
            
            inventoryTableBody.innerHTML = '';
            data.forEach(item => {
                const badgeClass = `badge-${item.item_type.toLowerCase()}`;
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${item.item_id}</strong></td>
                    <td>${item.description}</td>
                    <td><span class="badge ${badgeClass}">${item.item_type}</span></td>
                    <td style="font-weight: 600;">${item.on_hand_qty}</td>
                    <td>
                        <button class="btn btn-primary btn-sm edit-btn" data-id="${item.item_id}" data-qty="${item.on_hand_qty}">
                            <i class="fa-solid fa-pen-to-square"></i> Edit
                        </button>
                    </td>
                `;
                inventoryTableBody.appendChild(tr);
            });

            // Add event listeners to edit buttons
            document.querySelectorAll('.edit-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    editItemId.value = btn.dataset.id;
                    editQty.value = btn.dataset.qty;
                    editModal.classList.remove('hidden');
                });
            });
        } catch (error) {
            console.error("Failed to load inventory", error);
            inventoryTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--danger);">Failed to load data.</td></tr>';
        }
    }

    refreshBtn.addEventListener('click', loadInventory);

    // Close Modal logic
    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => editModal.classList.add('hidden'));
    });

    // Save Inventory logic
    saveBtn.addEventListener('click', async () => {
        const itemId = editItemId.value;
        const newQty = parseInt(editQty.value, 10);
        
        if (isNaN(newQty) || newQty < 0) {
            alert("Please enter a valid quantity.");
            return;
        }

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        try {
            await fetch('/api/inventory/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_id: itemId, on_hand_qty: newQty })
            });
            
            editModal.classList.add('hidden');
            loadInventory(); // Refresh table
        } catch (error) {
            console.error("Update failed", error);
            alert("Failed to update inventory.");
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = 'Save Changes';
        }
    });

    // --- MRP Engine ---
    const runMrpBtn = document.getElementById('run-mrp');
    const mrpTableBody = document.getElementById('mrp-table-body');
    const loadingState = document.getElementById('mrp-loading');

    runMrpBtn.addEventListener('click', async () => {
        // Show loading state
        mrpTableBody.innerHTML = '';
        loadingState.classList.remove('hidden');
        runMrpBtn.disabled = true;
        
        // Remove pulse animation after first click
        runMrpBtn.classList.remove('pulse-btn');

        try {
            const res = await fetch('/api/mrp/run');
            const schedule = await res.json();
            
            loadingState.classList.add('hidden');
            
            if (schedule.length === 0) {
                mrpTableBody.innerHTML = `
                    <tr class="empty-state">
                        <td colspan="4" style="text-align: center;">No orders need to be placed. Current inventory meets all demands.</td>
                    </tr>
                `;
                return;
            }

            schedule.forEach(order => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${order.item_id}</strong></td>
                    <td>Day <span style="color: var(--accent-secondary); font-weight: 600;">${order.release_date}</span></td>
                    <td>Day ${order.due_date}</td>
                    <td><span style="font-weight: 600; font-size: 1.1rem;">${order.qty}</span> units</td>
                `;
                mrpTableBody.appendChild(tr);
            });
        } catch (error) {
            console.error("MRP run failed", error);
            loadingState.classList.add('hidden');
            mrpTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--danger);">Engine execution failed.</td></tr>`;
        } finally {
            runMrpBtn.disabled = false;
        }
    });

    // Initial load
    loadInventory();
});
