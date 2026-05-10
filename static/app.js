document.addEventListener('DOMContentLoaded', () => {
    // --- Auth Setup ---
    const originalFetch = window.fetch;
    window.fetch = async function() {
        let [resource, config] = arguments;
        if (!config) config = {};
        if (!config.headers) config.headers = {};
        
        const token = localStorage.getItem('erp_token');
        if (token) {
            if (config.headers instanceof Headers) {
                config.headers.append('Authorization', `Bearer ${token}`);
            } else {
                config.headers['Authorization'] = `Bearer ${token}`;
            }
        }
        
        const response = await originalFetch(resource, config);
        if (response.status === 401 && resource !== '/api/token') {
            showLogin();
        }
        return response;
    };

    function showLogin() {
        document.getElementById('login-overlay').style.display = 'flex';
        document.getElementById('dashboard-wrapper').style.display = 'none';
    }

    function hideLogin() {
        document.getElementById('login-overlay').style.display = 'none';
        document.getElementById('dashboard-wrapper').style.display = 'flex';
        loadInventory(); // Initial load after auth
    }

    // Check token on load
    if (!localStorage.getItem('erp_token')) {
        showLogin();
    } else {
        hideLogin();
    }

    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const u = document.getElementById('login-username').value;
        const p = document.getElementById('login-password').value;
        const err = document.getElementById('login-error');
        err.style.display = 'none';
        
        const formData = new URLSearchParams();
        formData.append('username', u);
        formData.append('password', p);

        try {
            const res = await originalFetch('/api/token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData
            });
            if (!res.ok) throw new Error("Invalid credentials");
            const data = await res.json();
            localStorage.setItem('erp_token', data.access_token);
            hideLogin();
        } catch (error) {
            err.innerText = error.message;
            err.style.display = 'block';
        }
    });

    document.getElementById('logout-btn').addEventListener('click', (e) => {
        e.preventDefault();
        localStorage.removeItem('erp_token');
        showLogin();
    });

    // --- Navigation ---
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
                document.getElementById('export-mrp-excel').classList.add('hidden');
                document.getElementById('export-mrp-pdf').classList.add('hidden');
                return;
            }

            document.getElementById('commit-pos').classList.remove('hidden');
            document.getElementById('export-mrp-excel').classList.remove('hidden');
            document.getElementById('export-mrp-pdf').classList.remove('hidden');

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

    // --- BOM Editor ---
    const bomTreeRoot = document.getElementById('bom-tree');
    const refreshBOMBtn = document.getElementById('refresh-bom');
    
    // Modals
    const bomAddModal = document.getElementById('bom-add-modal');
    const bomEditModal = document.getElementById('bom-edit-modal');
    const bomAddSelect = document.getElementById('bom-add-child');
    let allItemsCache = [];

    async function loadItemsForSelect() {
        if (allItemsCache.length === 0) {
            const res = await fetch('/api/items');
            allItemsCache = await res.json();
        }
        bomAddSelect.innerHTML = allItemsCache.map(item => 
            `<option value="${item.item_id}">${item.item_id} - ${item.description}</option>`
        ).join('');
    }

    async function loadBOM() {
        try {
            bomTreeRoot.innerHTML = '<li>Loading BOM...</li>';
            const res = await fetch('/api/bom/tree');
            const data = await res.json();
            
            bomTreeRoot.innerHTML = '';
            data.forEach(node => {
                bomTreeRoot.appendChild(renderBOMNode(node, true));
            });
        } catch (e) {
            console.error(e);
            bomTreeRoot.innerHTML = '<li style="color:var(--danger)">Failed to load BOM.</li>';
        }
    }

    function renderBOMNode(node, isRoot = false, parentId = null) {
        const li = document.createElement('li');
        li.className = 'tree-node';
        
        const hasChildren = node.children && node.children.length > 0;
        const badgeClass = `badge-${node.item_type.toLowerCase()}`;
        
        // Build the item UI
        const itemDiv = document.createElement('div');
        itemDiv.className = 'tree-item';
        
        // Toggle chevron
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'tree-toggle';
        toggleBtn.innerHTML = hasChildren ? '<i class="fa-solid fa-chevron-down"></i>' : '';
        itemDiv.appendChild(toggleBtn);
        
        // Content
        let contentHtml = `<strong>${node.item_id}</strong> - ${node.description} <span class="badge ${badgeClass}">${node.item_type}</span>`;
        if (!isRoot) {
            contentHtml += `<span style="margin-left: 10px; color: var(--text-secondary);">Qty: <strong>${node.qty_required}</strong></span>`;
        }
        itemDiv.insertAdjacentHTML('beforeend', `<div>${contentHtml}</div>`);
        
        // Actions
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'tree-actions';
        
        if (!isRoot) {
            const editBtn = document.createElement('button');
            editBtn.className = 'bom-action-btn';
            editBtn.innerHTML = '<i class="fa-solid fa-pen"></i>';
            editBtn.onclick = (e) => {
                e.stopPropagation();
                openEditBOMModal(parentId, node.item_id, node.qty_required);
            };
            actionsDiv.appendChild(editBtn);
        }
        
        // Only FG and SA can have children realistically, but let's allow adding to anything for flexibility
        if (node.item_type !== 'RM') {
            const addBtn = document.createElement('button');
            addBtn.className = 'bom-action-btn';
            addBtn.innerHTML = '<i class="fa-solid fa-plus"></i>';
            addBtn.onclick = (e) => {
                e.stopPropagation();
                openAddBOMModal(node.item_id);
            };
            actionsDiv.appendChild(addBtn);
        }

        itemDiv.appendChild(actionsDiv);
        li.appendChild(itemDiv);
        
        // Children list
        if (hasChildren) {
            const childrenUl = document.createElement('ul');
            childrenUl.className = 'tree-children';
            node.children.forEach(child => {
                childrenUl.appendChild(renderBOMNode(child, false, node.item_id));
            });
            li.appendChild(childrenUl);
            
            // Toggle logic
            toggleBtn.onclick = (e) => {
                e.stopPropagation();
                toggleBtn.classList.toggle('collapsed');
                childrenUl.style.display = childrenUl.style.display === 'none' ? 'block' : 'none';
            };
        }
        
        return li;
    }

    refreshBOMBtn.addEventListener('click', loadBOM);

    // Add Modal Logic
    async function openAddBOMModal(parentId) {
        document.getElementById('bom-add-parent-id').innerText = parentId;
        document.getElementById('bom-add-qty').value = 1;
        await loadItemsForSelect();
        // Remove parent from options to prevent trivial direct cycle
        Array.from(bomAddSelect.options).forEach(opt => {
            opt.disabled = opt.value === parentId;
        });
        bomAddModal.classList.remove('hidden');
    }

    document.getElementById('save-bom-add').addEventListener('click', async () => {
        const parentId = document.getElementById('bom-add-parent-id').innerText;
        const childId = bomAddSelect.value;
        const qty = parseInt(document.getElementById('bom-add-qty').value, 10);
        
        try {
            const res = await fetch('/api/bom/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({parent_id: parentId, child_id: childId, qty_required: qty})
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to add component.");
            }
            bomAddModal.classList.add('hidden');
            loadBOM();
        } catch (e) {
            alert(e.message);
        }
    });

    // Edit/Delete Logic
    function openEditBOMModal(parentId, childId, qty) {
        document.getElementById('bom-edit-parent').value = parentId;
        document.getElementById('bom-edit-child').value = childId;
        document.getElementById('bom-edit-qty').value = qty;
        bomEditModal.classList.remove('hidden');
    }

    document.getElementById('save-bom-edit').addEventListener('click', async () => {
        const parentId = document.getElementById('bom-edit-parent').value;
        const childId = document.getElementById('bom-edit-child').value;
        const qty = parseInt(document.getElementById('bom-edit-qty').value, 10);
        
        try {
            await fetch('/api/bom/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({parent_id: parentId, child_id: childId, qty_required: qty})
            });
            bomEditModal.classList.add('hidden');
            loadBOM();
        } catch (e) {
            alert("Failed to update.");
        }
    });

    document.getElementById('delete-bom-component').addEventListener('click', async () => {
        if (!confirm("Are you sure you want to remove this component?")) return;
        const parentId = document.getElementById('bom-edit-parent').value;
        const childId = document.getElementById('bom-edit-child').value;
        
        try {
            await fetch('/api/bom/remove', {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({parent_id: parentId, child_id: childId})
            });
            bomEditModal.classList.add('hidden');
            loadBOM();
        } catch (e) {
            alert("Failed to delete.");
        }
    });

    // --- Sales & Forecasting (MPS) ---
    const forecastTableBody = document.getElementById('forecast-table-body');
    const refreshForecastBtn = document.getElementById('refresh-forecast');
    const addForecastBtn = document.getElementById('add-forecast-btn');
    
    // Modals
    const forecastAddModal = document.getElementById('forecast-add-modal');
    const forecastEditModal = document.getElementById('forecast-edit-modal');
    const forecastAddSelect = document.getElementById('forecast-add-item');

    async function loadForecasts() {
        try {
            forecastTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center;">Loading...</td></tr>';
            const res = await fetch('/api/forecast');
            const data = await res.json();
            
            forecastTableBody.innerHTML = '';
            if (data.length === 0) {
                forecastTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No forecast demand found.</td></tr>';
                return;
            }

            data.forEach(entry => {
                const badgeClass = `badge-${entry.item_type.toLowerCase()}`;
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${entry.item_id}</strong></td>
                    <td>${entry.description}</td>
                    <td><span class="badge ${badgeClass}">${entry.item_type}</span></td>
                    <td>Day ${entry.due_date}</td>
                    <td><span style="font-weight: 600; font-size: 1.1rem;">${entry.demand_qty}</span> units</td>
                    <td>
                        <button class="btn btn-secondary" onclick="openEditForecastModal(${entry.rowid}, '${entry.item_id}', ${entry.due_date}, ${entry.demand_qty})">
                            <i class="fa-solid fa-pen"></i> Edit
                        </button>
                    </td>
                `;
                forecastTableBody.appendChild(tr);
            });
        } catch (e) {
            console.error(e);
            forecastTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--danger);">Failed to load forecast data.</td></tr>';
        }
    }

    refreshForecastBtn.addEventListener('click', loadForecasts);

    // Add Forecast
    addForecastBtn.addEventListener('click', async () => {
        await loadItemsForSelect();
        // Populate items in Forecast select (reuse the cache from BOM)
        forecastAddSelect.innerHTML = allItemsCache.map(item => 
            `<option value="${item.item_id}">${item.item_id} - ${item.description}</option>`
        ).join('');
        
        // Default to FG001 if available
        if (allItemsCache.find(i => i.item_id === 'FG001')) {
            forecastAddSelect.value = 'FG001';
        }
        
        forecastAddModal.classList.remove('hidden');
    });

    document.getElementById('save-forecast-add').addEventListener('click', async () => {
        const itemId = forecastAddSelect.value;
        const date = parseInt(document.getElementById('forecast-add-date').value, 10);
        const qty = parseInt(document.getElementById('forecast-add-qty').value, 10);
        
        if (qty <= 0 || date <= 0) {
            alert("Quantity and Date must be positive integers.");
            return;
        }

        try {
            const res = await fetch('/api/forecast/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({item_id: itemId, due_date: date, demand_qty: qty})
            });
            if (!res.ok) throw new Error("Failed to add forecast");
            forecastAddModal.classList.add('hidden');
            loadForecasts();
        } catch (e) {
            alert(e.message);
        }
    });

    // Edit/Delete Forecast
    window.openEditForecastModal = function(rowid, itemId, dueDate, qty) {
        document.getElementById('forecast-edit-rowid').value = rowid;
        document.getElementById('forecast-edit-item-display').innerText = `(${itemId})`;
        document.getElementById('forecast-edit-date').value = dueDate;
        document.getElementById('forecast-edit-qty').value = qty;
        forecastEditModal.classList.remove('hidden');
    };

    document.getElementById('save-forecast-edit').addEventListener('click', async () => {
        const rowid = parseInt(document.getElementById('forecast-edit-rowid').value, 10);
        const date = parseInt(document.getElementById('forecast-edit-date').value, 10);
        const qty = parseInt(document.getElementById('forecast-edit-qty').value, 10);
        
        if (qty <= 0 || date <= 0) {
            alert("Quantity and Date must be positive integers.");
            return;
        }
        
        try {
            const res = await fetch('/api/forecast/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({rowid: rowid, due_date: date, demand_qty: qty})
            });
            if (!res.ok) throw new Error("Failed to update forecast");
            forecastEditModal.classList.add('hidden');
            loadForecasts();
        } catch (e) {
            alert(e.message);
        }
    });

    document.getElementById('delete-forecast-btn').addEventListener('click', async () => {
        if (!confirm("Are you sure you want to remove this demand entry?")) return;
        const rowid = parseInt(document.getElementById('forecast-edit-rowid').value, 10);
        
        try {
            const res = await fetch('/api/forecast/remove', {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({rowid: rowid})
            });
            if (!res.ok) throw new Error("Failed to delete forecast");
            forecastEditModal.classList.add('hidden');
            loadForecasts();
        } catch (e) {
            alert(e.message);
        }
    });

    // --- Export Logic ---
    document.getElementById('export-mrp-excel').addEventListener('click', () => {
        const token = localStorage.getItem('erp_token');
        window.open('/api/export/mrp/excel?token=' + token, '_blank');
    });

    document.getElementById('export-mrp-pdf').addEventListener('click', () => {
        const token = localStorage.getItem('erp_token');
        window.open('/api/export/mrp/pdf?token=' + token, '_blank');
    });

    // --- Supplier Database ---
    const suppliersTableBody = document.getElementById('suppliers-table-body');
    const refreshSuppliersBtn = document.getElementById('refresh-suppliers');
    const addSupplierBtn = document.getElementById('add-supplier-btn');
    
    const supplierAddModal = document.getElementById('supplier-add-modal');
    const supplierEditModal = document.getElementById('supplier-edit-modal');

    async function loadSuppliers() {
        try {
            suppliersTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Loading...</td></tr>';
            const res = await fetch('/api/suppliers');
            const data = await res.json();
            
            suppliersTableBody.innerHTML = '';
            if (data.length === 0) {
                suppliersTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center;">No suppliers found.</td></tr>';
                return;
            }

            data.forEach(supplier => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${supplier.supplier_id}</td>
                    <td><strong>${supplier.name}</strong></td>
                    <td>${supplier.contact_email}</td>
                    <td>${supplier.lead_time_modifier}</td>
                    <td>
                        <button class="btn btn-secondary" onclick="openEditSupplierModal(${supplier.supplier_id}, '${supplier.name}', '${supplier.contact_email}', ${supplier.lead_time_modifier})">
                            <i class="fa-solid fa-pen"></i> Edit
                        </button>
                    </td>
                `;
                suppliersTableBody.appendChild(tr);
            });
        } catch (e) {
            console.error(e);
            suppliersTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--danger);">Failed to load suppliers.</td></tr>';
        }
    }

    refreshSuppliersBtn.addEventListener('click', loadSuppliers);

    addSupplierBtn.addEventListener('click', () => {
        supplierAddModal.classList.remove('hidden');
    });

    document.getElementById('save-supplier-add').addEventListener('click', async () => {
        const name = document.getElementById('supplier-add-name').value;
        const email = document.getElementById('supplier-add-email').value;
        const ltm = parseInt(document.getElementById('supplier-add-ltm').value, 10);
        
        try {
            const res = await fetch('/api/suppliers/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, contact_email: email, lead_time_modifier: ltm})
            });
            if (!res.ok) throw new Error("Failed to add supplier");
            supplierAddModal.classList.add('hidden');
            loadSuppliers();
        } catch (e) {
            alert(e.message);
        }
    });

    window.openEditSupplierModal = function(id, name, email, ltm) {
        document.getElementById('supplier-edit-id').value = id;
        document.getElementById('supplier-edit-name').value = name;
        document.getElementById('supplier-edit-email').value = email;
        document.getElementById('supplier-edit-ltm').value = ltm;
        supplierEditModal.classList.remove('hidden');
    };

    document.getElementById('save-supplier-edit').addEventListener('click', async () => {
        const id = parseInt(document.getElementById('supplier-edit-id').value, 10);
        const name = document.getElementById('supplier-edit-name').value;
        const email = document.getElementById('supplier-edit-email').value;
        const ltm = parseInt(document.getElementById('supplier-edit-ltm').value, 10);
        
        try {
            const res = await fetch('/api/suppliers/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({supplier_id: id, name, contact_email: email, lead_time_modifier: ltm})
            });
            if (!res.ok) throw new Error("Failed to update supplier");
            supplierEditModal.classList.add('hidden');
            loadSuppliers();
        } catch (e) {
            alert(e.message);
        }
    });

    document.getElementById('delete-supplier-btn').addEventListener('click', async () => {
        if (!confirm("Are you sure you want to remove this supplier?")) return;
        const id = parseInt(document.getElementById('supplier-edit-id').value, 10);
        
        try {
            const res = await fetch('/api/suppliers/remove', {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({supplier_id: id})
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to delete supplier");
            }
            supplierEditModal.classList.add('hidden');
            loadSuppliers();
        } catch (e) {
            alert(e.message);
        }
    });

    // Nav extension
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            if (link.dataset.view === 'forecast') {
                loadForecasts();
            } else if (link.dataset.view === 'suppliers') {
                loadSuppliers();
            }
        });
    });

    // Remove loadInventory() from here since it's called after login
});
