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
                document.getElementById('commit-pos').classList.add('hidden');
                return;
            }

            document.getElementById('commit-pos').classList.remove('hidden');

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

    // --- Commit to POs ---
    const commitPosBtn = document.getElementById('commit-pos');
    commitPosBtn.addEventListener('click', async () => {
        commitPosBtn.disabled = true;
        commitPosBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Committing...';
        
        try {
            await fetch('/api/po/commit', { method: 'POST' });
            
            // Switch to PO View
            navLinks.forEach(l => l.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));
            
            const poLink = document.querySelector('[data-view="po"]');
            poLink.classList.add('active');
            document.getElementById('po-view').classList.add('active');
            
            loadPOs();
        } catch (error) {
            console.error("Failed to commit POs", error);
            alert("Failed to commit schedule to Purchase Orders.");
        } finally {
            commitPosBtn.disabled = false;
            commitPosBtn.innerHTML = '<i class="fa-solid fa-check"></i> Commit Schedule';
            commitPosBtn.classList.add('hidden');
        }
    });

    // --- PO Management ---
    const poTableBody = document.getElementById('po-table-body');
    const refreshPOsBtn = document.getElementById('refresh-pos');

    async function loadPOs() {
        try {
            poTableBody.innerHTML = '<tr><td colspan="8" style="text-align: center;">Loading...</td></tr>';
            const res = await fetch('/api/pos');
            const data = await res.json();
            
            poTableBody.innerHTML = '';
            
            if (data.length === 0) {
                poTableBody.innerHTML = '<tr><td colspan="8" style="text-align: center;">No Purchase Orders found.</td></tr>';
                return;
            }

            data.forEach(po => {
                const tr = document.createElement('tr');
                
                let badgeClass = 'badge-pending';
                if (po.status === 'Ordered') badgeClass = 'badge-ordered';
                if (po.status === 'In Transit') badgeClass = 'badge-intransit';
                if (po.status === 'Received') badgeClass = 'badge-received';
                
                const isReceived = po.status === 'Received';
                
                tr.innerHTML = `
                    <td>#${po.po_id}</td>
                    <td><strong>${po.item_id}</strong></td>
                    <td>${po.description}</td>
                    <td><span style="font-weight: 600;">${po.qty}</span></td>
                    <td>Day ${po.order_date}</td>
                    <td>Day ${po.due_date}</td>
                    <td><span class="badge ${badgeClass}" id="badge-${po.po_id}">${po.status}</span></td>
                    <td>
                        <select class="status-select" data-poid="${po.po_id}" ${isReceived ? 'disabled' : ''}>
                            <option value="Pending" ${po.status === 'Pending' ? 'selected' : ''}>Pending</option>
                            <option value="Ordered" ${po.status === 'Ordered' ? 'selected' : ''}>Ordered</option>
                            <option value="In Transit" ${po.status === 'In Transit' ? 'selected' : ''}>In Transit</option>
                            <option value="Received" ${po.status === 'Received' ? 'selected' : ''}>Received</option>
                        </select>
                    </td>
                `;
                poTableBody.appendChild(tr);
            });
            
            // Add event listeners for status change
            document.querySelectorAll('.status-select').forEach(select => {
                select.addEventListener('change', async (e) => {
                    const poId = e.target.dataset.poid;
                    const newStatus = e.target.value;
                    
                    try {
                        const res = await fetch('/api/po/status', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ po_id: parseInt(poId), status: newStatus })
                        });
                        
                        if (!res.ok) throw new Error('Status update failed');
                        
                        // Update badge
                        const badge = document.getElementById(`badge-${poId}`);
                        badge.textContent = newStatus;
                        badge.className = 'badge'; // reset
                        if (newStatus === 'Pending') badge.classList.add('badge-pending');
                        if (newStatus === 'Ordered') badge.classList.add('badge-ordered');
                        if (newStatus === 'In Transit') badge.classList.add('badge-intransit');
                        if (newStatus === 'Received') {
                            badge.classList.add('badge-received');
                            e.target.disabled = true; // Lock the select once received
                        }
                    } catch (error) {
                        console.error(error);
                        alert("Failed to update status.");
                        // Revert select
                        loadPOs();
                    }
                });
            });

        } catch (error) {
            console.error("Failed to load POs", error);
            poTableBody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--danger);">Failed to load data.</td></tr>';
        }
    }

    refreshPOsBtn.addEventListener('click', loadPOs);

    // Initial load
    loadInventory();
});
