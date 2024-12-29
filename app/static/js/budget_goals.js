// Helper function to show loading state
function setLoading(isLoading, button) {
    if (isLoading) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
    } else {
        button.disabled = false;
        button.innerHTML = button.getAttribute('data-original-text');
    }
}

async function handleAddGoal(event) {
    event.preventDefault();
    const form = event.target;
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.setAttribute('data-original-text', submitButton.innerHTML);
    
    const formData = new FormData(form);
    
    // Basic validation
    if (!formData.get('amount') || !formData.get('target_date')) {
        showToast('Error', 'Please fill in all required fields.', 'danger');
        return;
    }

    try {
        setLoading(true, submitButton);
        const response = await fetch('/add_goal', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData,
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('Success', 'Goal added successfully!', 'success');
            // Instead of reloading, add the new goal card to the UI
            addGoalToUI(data.goal);
        } else {
            showToast('Error', data.message, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An error occurred while adding the goal.', 'danger');
    } finally {
        setLoading(false, submitButton);
    }
}

// Function to add new goal to UI without reloading
function addGoalToUI(goal) {
    const goalsContainer = document.getElementById('goals-container');
    const goalCard = createGoalCard(goal);
    goalsContainer.insertAdjacentHTML('beforeend', goalCard);
}

// Function to create goal card HTML
function createGoalCard(goal) {
    return `
    <div class="col-md-4 mb-4" id="goal-card-${goal.id}">
        <div class="card h-100">
            <div class="card-body">
                <h5 class="card-title">${goal.category_name}</h5>
                <p class="card-text">Target: $${goal.amount.toLocaleString()}</p>
                <p class="card-text">Period: ${goal.period}</p>
                <div class="progress mb-3">
                    <div class="progress-bar" role="progressbar" 
                         style="width: ${goal.progress}%" 
                         aria-valuenow="${goal.progress}" 
                         aria-valuemin="0" 
                         aria-valuemax="100">
                        ${goal.progress}%
                    </div>
                </div>
                <button class="btn btn-sm btn-danger" 
                        onclick="handleDelete(${goal.id}, ${goal.category_id})">
                    Delete
                </button>
            </div>
        </div>
    </div>`;
}

    // Basic validation
    if (!formData.get('amount') || !formData.get('target_date')) {
        showToast('Error', 'Please fill in all required fields.', 'danger');
        return;
    }

    try {
        setLoading(true, submitButton);
        const response = await fetch('/add_goal', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'  // CSRF protection
            },
            body: formData,
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('Success', 'Goal added successfully!', 'success');
            location.reload();
        } else {
            showToast('Error', data.message, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An error occurred while adding the goal.', 'danger');
    } finally {
        setLoading(false, submitButton);
    }
}

async function handleEdit(event, goalId) {
    event.preventDefault();
    const form = event.target;
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.setAttribute('data-original-text', submitButton.innerHTML);
    
    const formData = new FormData(form);

    try {
        setLoading(true, submitButton);
        const response = await fetch(`/edit_goal/${goalId}`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData,
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('Success', 'Goal updated successfully!', 'success');
            location.reload();
        } else {
            showToast('Error', data.message, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An error occurred while editing the goal.', 'danger');
    } finally {
        setLoading(false, submitButton);
    }
}

async function handleDelete(goalId, categoryId) {
    if (!confirm('Are you sure you want to delete this goal?')) {
        return;
    }

    try {
        const response = await fetch(`/delete_goal/${goalId}`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        const data = await response.json();a
        
        if (data.success) {
            const goalCard = document.getElementById(`goal-card-${categoryId}`);
            goalCard.style.animation = 'fadeOut 0.3s';
            setTimeout(() => goalCard.remove(), 300);
            showToast('Success', 'Goal deleted successfully.', 'success');
        } else {
            showToast('Error', data.message, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An error occurred while deleting the goal.', 'danger');
    }
}

async function handleAddRecurring(event) {
    event.preventDefault();
    const form = event.target;
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.setAttribute('data-original-text', submitButton.innerHTML);
    
    const formData = new FormData(form);

    // Detailed validation
    const validationErrors = [];
    
    // ... (existing validation code) ...

    try {
        setLoading(true, submitButton);
        const response = await fetch('/add_recurring', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData,
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('Success', 'Recurring transaction added successfully!', 'success');
            // Instead of reloading, add the new recurring transaction to the UI
            addRecurringToUI(data.recurring);
            // Close the modal if it exists
            const modal = bootstrap.Modal.getInstance(document.getElementById('addRecurringModal'));
            if (modal) modal.hide();
        } else {
            showToast('Error', data.message, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An error occurred while adding the recurring transaction.', 'danger');
    } finally {
        setLoading(false, submitButton);
    }
}

// Function to add new recurring transaction to UI without reloading
function addRecurringToUI(recurring) {
    const recurringContainer = document.getElementById('recurring-container');
    const recurringRow = createRecurringRow(recurring);
    recurringContainer.insertAdjacentHTML('beforeend', recurringRow);
}

// Function to create recurring transaction row HTML
function createRecurringRow(recurring) {
    return `
    <tr data-recurring-id="${recurring.id}">
        <td>${recurring.category_name}</td>
        <td>$${recurring.amount.toLocaleString()}</td>
        <td>${recurring.description}</td>
        <td>${recurring.frequency}</td>
        <td>${new Date(recurring.next_date).toLocaleDateString()}</td>
        <td>
            <button class="btn btn-sm btn-primary" 
                    onclick="handleEditRecurring(${recurring.id})">
                Edit
            </button>
            <button class="btn btn-sm btn-danger" 
                    onclick="deleteRecurring(${recurring.id})">
                Delete
            </button>
        </td>
    </tr>`;
}


    // Detailed validation
    const validationErrors = [];
    
    // Check amount
    const amount = formData.get('amount');
    if (!amount) {
        validationErrors.push('Amount is required');
    } else if (isNaN(amount) || parseFloat(amount) <= 0) {
        validationErrors.push('Amount must be a positive number');
    }

    // Check frequency
    const frequency = formData.get('frequency');
    if (!frequency) {
        validationErrors.push('Frequency is required');
    }

    // Check next date
    const nextDate = formData.get('next_date');
    if (!nextDate) {
        validationErrors.push('Next date is required');
    } else {
        const selectedDate = new Date(nextDate);
        const today = new Date();
        if (selectedDate < today) {
            validationErrors.push('Next date cannot be in the past');
        }
    }

    // Check description (if required)
    const description = formData.get('description');
    if (!description || description.trim() === '') {
        validationErrors.push('Description is required');
    }

    // Show all validation errors if any
    if (validationErrors.length > 0) {
        showToast('Error', validationErrors.join(', '), 'danger');
        return;
    }

    try {
        setLoading(true, submitButton);
        const response = await fetch('/add_recurring', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData,
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('Success', 'Recurring transaction added successfully!', 'success');
            location.reload();
        } else {
            showToast('Error', data.message, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An error occurred while adding the recurring transaction.', 'danger');
    } finally {
        setLoading(false, submitButton);
    }
}

// Function to set default date to first day of previous month
function setDefaultRecurringDate() {
    const dateInput = document.getElementById('next_date'); // Adjust ID as needed
    if (dateInput) {
        const today = new Date();
        // Set to first day of previous month
        const firstDayLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        
        // Format date as YYYY-MM-DD
        const formattedDate = firstDayLastMonth.toISOString().split('T')[0];
        dateInput.value = formattedDate;
        
        // Set min date attribute to prevent selecting past dates
        dateInput.min = formattedDate;
    }
}

// Call this function when the page loads
document.addEventListener('DOMContentLoaded', setDefaultRecurringDate);

async function handleEditRecurring(event) {
    event.preventDefault();
    const form = event.target;
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.setAttribute('data-original-text', submitButton.innerHTML);
    
    const formData = new FormData(form);
    const recurringId = formData.get('recurring_id');

    try {
        setLoading(true, submitButton);
        const response = await fetch(`/edit_recurring/${recurringId}`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData,
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('Success', 'Recurring transaction updated successfully!', 'success');
            location.reload();
        } else {
            showToast('Error', data.message, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An error occurred while editing the recurring transaction.', 'danger');
    } finally {
        setLoading(false, submitButton);
    }
}

function deleteRecurring(recurringId) {
    const modal = new bootstrap.Modal(document.getElementById('deleteRecurringModal'));
    
    document.getElementById('confirmDeleteRecurring').onclick = async function() {
        try {
            const response = await fetch(`/delete_recurring/${recurringId}`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await response.json();
            
            if (data.success) {
                const element = document.querySelector(`[data-recurring-id="${recurringId}"]`);
                element.style.animation = 'fadeOut 0.3s';
                setTimeout(() => element.remove(), 300);
                showToast('Success', 'Recurring transaction deleted successfully.', 'success');
                modal.hide();
            } else {
                showToast('Error', data.message, 'danger');
            }
        } catch (error) {
            console.error('Error:', error);
            showToast('Error', 'An error occurred while deleting the recurring transaction.', 'danger');
        }
    };
    
    modal.show();
}

async function editRecurring(recurringId) {
    try {
        const response = await fetch(`/get_recurring/${recurringId}`);
        const data = await response.json();
        
        if (data.success) {
            const transaction = data.transaction;
            document.getElementById('edit_recurring_id').value = transaction.id;
            document.getElementById('edit_category_id').value = transaction.category_id;
            document.getElementById('edit_amount').value = transaction.amount;
            document.getElementById('edit_description').value = transaction.description;
            document.getElementById('edit_frequency').value = transaction.frequency;
            document.getElementById('edit_next_date').value = transaction.next_date;
            
            new bootstrap.Modal(document.getElementById('editRecurringModal')).show();
        } else {
            showToast('Error', data.message, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An error occurred while fetching the recurring transaction.', 'danger');
    }
}

function showToast(title, message, type) {
    const toastContainer = document.querySelector('.toast-container');
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <strong>${title}</strong> ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove toast after it's hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Add CSS for animations
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; }
    }
`;
document.head.appendChild(style);