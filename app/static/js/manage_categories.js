document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => new bootstrap.Tooltip(tooltip));

    // Setup edit category handlers
    document.querySelectorAll('.edit-category').forEach(button => {
        button.addEventListener('click', function() {
            const data = this.dataset;
            document.getElementById('edit-category-id').value = data.id;
            document.getElementById('edit-name').value = data.name;
            document.getElementById('edit-description').value = data.description;
            
            if (data.type === 'income') {
                document.getElementById('editTypeIncome').checked = true;
            } else {
                document.getElementById('editTypeExpense').checked = true;
            }
        });
    });

    // Setup delete category handlers
    document.querySelectorAll('.delete-category').forEach(button => {
        button.addEventListener('click', async function() {
            const categoryId = this.dataset.id;
            const categoryName = this.dataset.name;
            
            if (await confirmDelete(categoryName)) {
                deleteCategory(categoryId);
            }
        });
    });

    // Add form submission handlers
    setupFormHandlers();
    
    // Add hover effects
    addHoverEffects();
});

function setupFormHandlers() {
    // Add Category Form
    document.getElementById('addCategoryForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        await handleFormSubmit(this, 'Category added successfully!');
    });

    // Edit Category Form
    document.getElementById('editCategoryForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        await handleFormSubmit(this, 'Category updated successfully!');
    });
}

async function handleFormSubmit(form, successMessage) {
    const submitButton = form.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    
    try {
        setLoading(true, submitButton);
        const formData = new FormData(form);
        
        const response = await fetch(form.action, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (data.success) {
            showToast('Success', successMessage, 'success');
            location.reload(); // Reload to show changes
        } else {
            showToast('Error', data.error || 'An error occurred', 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An unexpected error occurred', 'danger');
    } finally {
        setLoading(false, submitButton, originalText);
    }
}

async function confirmDelete(categoryName) {
    return new Promise(resolve => {
        const modal = new bootstrap.Modal(document.createElement('div'));
        modal.element.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Confirm Delete</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        Are you sure you want to delete the category "${categoryName}"?
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-danger confirm-delete">Delete</button>
                    </div>
                </div>
            </div>
        `;
        
        modal.element.querySelector('.confirm-delete').addEventListener('click', () => {
            modal.hide();
            resolve(true);
        });
        
        modal.element.addEventListener('hidden.bs.modal', () => {
            resolve(false);
        });
        
        modal.show();
    });
}

async function deleteCategory(categoryId) {
    try {
        const response = await fetch('/delete_category', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ category_id: categoryId })
        });

        const data = await response.json();
        
        if (data.success) {
            showToast('Success', 'Category deleted successfully!', 'success');
            location.reload(); // Reload to show changes
        } else {
            showToast('Error', data.error || 'An error occurred', 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An unexpected error occurred', 'danger');
    }
}

function setLoading(isLoading, button, originalText) {
    if (isLoading) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
    } else {
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

function showToast(title, message, type = 'success') {
    const toastContainer = document.querySelector('.toast-container');
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-${type} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <strong>${title}</strong><br>${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 3000 });
    toast.show();
    
    toastEl.addEventListener('hidden.bs.toast', () => {
        toastEl.remove();
    });
}

function addHoverEffects() {
    const style = document.createElement('style');
    style.textContent = `
        .card {
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15) !important;
        }
        .btn-outline-primary:hover, .btn-outline-danger:hover {
            transform: translateY(-2px);
        }
        .category-icon {
            transition: transform 0.2s ease-in-out;
        }
        tr:hover .category-icon {
            transform: scale(1.2);
        }
    `;
    document.head.appendChild(style);
}
