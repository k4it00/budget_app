document.addEventListener('DOMContentLoaded', function() {
    // Initialize variables
    const goalForm = document.getElementById('goalForm');
    const goalModalElement = document.getElementById('goalModal');
    const deleteConfirmModalElement = document.getElementById('deleteConfirmModal');
    
    // Check if elements exist before initializing modals
    let goalModal, deleteConfirmModal;
    
    if (goalModalElement) {
        goalModal = new bootstrap.Modal(goalModalElement);
    }
    
    if (deleteConfirmModalElement) {
        deleteConfirmModal = new bootstrap.Modal(deleteConfirmModalElement);
    }
    
    let currentGoalId = null;

    // Add new goal button handler
    const newGoalButton = document.querySelector('[data-bs-target="#goalModal"]');
    if (newGoalButton) {
        newGoalButton.addEventListener('click', function() {
            resetForm();
            const modalTitle = document.querySelector('#goalModal .modal-title');
            if (modalTitle) {
                modalTitle.textContent = 'Create New Goal';
            }
        });
    }

    // Form submission handler
    if (goalForm) {
        goalForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(goalForm);
            const isEdit = formData.get('goal_id') !== '';
            
            fetch(isEdit ? '/update_goal' : '/add_goal', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (isEdit) {
                        updateGoalCard(data.goal);
                    } else {
                        addGoalCard(data.goal);
                    }
                    if (goalModal) {
                        goalModal.hide();
                    }
                    showToast('Success', `Goal ${isEdit ? 'updated' : 'created'} successfully!`);
                } else {
                    showToast('Error', data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Error', 'An error occurred while saving the goal.', 'error');
            });
        });
    }

    // Edit goal handler
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('edit-goal')) {
            const goalId = e.target.dataset.goalId;
            fetch(`/get_goal/${goalId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        populateForm(data.goal);
                        const modalTitle = document.querySelector('#goalModal .modal-title');
                        if (modalTitle) {
                            modalTitle.textContent = 'Edit Goal';
                        }
                        if (goalModal) {
                            goalModal.show();
                        }
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('Error', 'Error loading goal details', 'error');
                });
        }
    });

    // Delete goal handler
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('delete-goal')) {
            currentGoalId = e.target.dataset.goalId;
            if (deleteConfirmModal) {
                deleteConfirmModal.show();
            }
        }
    });

    // Confirm delete handler
    const confirmDeleteButton = document.getElementById('confirmDelete');
    if (confirmDeleteButton) {
        confirmDeleteButton.addEventListener('click', function() {
            if (currentGoalId) {
                fetch(`/delete_goal/${currentGoalId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const goalCard = document.getElementById(`goal-card-${currentGoalId}`);
                        if (goalCard) {
                            goalCard.remove();
                        }
                        showToast('Success', 'Goal deleted successfully!');
                    } else {
                        showToast('Error', data.error, 'error');
                    }
                    if (deleteConfirmModal) {
                        deleteConfirmModal.hide();
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('Error', 'Error deleting goal', 'error');
                    if (deleteConfirmModal) {
                        deleteConfirmModal.hide();
                    }
                });
            }
        });
    }

});

    // Helper Functions
    function resetForm() {
        goalForm.reset();
        document.getElementById('goal_id').value = '';
    }

    function populateForm(goal) {
        document.getElementById('goal_id').value = goal.id;
        document.getElementById('goal_name').value = goal.name;
        document.getElementById('target_amount').value = goal.target_amount;
        document.getElementById('current_amount').value = goal.current_amount;
        document.getElementById('target_date').value = goal.target_date;
    }

    function addGoalCard(goal) {
        const newGoalHtml = createGoalCardHtml(goal);
        document.getElementById('goals-container').insertAdjacentHTML('beforeend', newGoalHtml);
    }

    function updateGoalCard(goal) {
        const goalCard = document.getElementById(`goal-card-${goal.id}`);
        goalCard.outerHTML = createGoalCardHtml(goal);
    }

    function createGoalCardHtml(goal) {
        return `
            <div class="col-md-6 col-lg-4" id="goal-card-${goal.id}">
                <div class="card h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <h5 class="card-title">${goal.name}</h5>
                            <div class="dropdown">
                                <button class="btn btn-link" type="button" data-bs-toggle="dropdown">
                                    <i class="fas fa-ellipsis-v"></i>
                                </button>
                                <ul class="dropdown-menu dropdown-menu-end">
                                    <li><button class="dropdown-item edit-goal" data-goal-id="${goal.id}">Edit</button></li>
                                    <li><button class="dropdown-item delete-goal" data-goal-id="${goal.id}">Delete</button></li>
                                </ul>
                            </div>
                        </div>
                        <div class="progress mb-3">
                            <div class="progress-bar" role="progressbar" 
                                 style="width: ${goal.progress}%" 
                                 aria-valuenow="${goal.progress}" 
                                 aria-valuemin="0" 
                                 aria-valuemax="100">
                                ${goal.progress}%
                            </div>
                        </div>
                        <p class="card-text">
                            Current: $${goal.current_amount}<br>
                            Target: $${goal.target_amount}<br>
                            Due Date: ${goal.target_date}
                        </p>
                    </div>
                </div>
            </div>
        `;
    }

    function showToast(title, message, type = 'success') {
        // Implement your preferred toast notification system here
        alert(`${title}: ${message}`);
    }
});
