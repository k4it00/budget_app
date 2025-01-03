document.addEventListener('DOMContentLoaded', function() {
    const goalForm = document.getElementById('goalForm');
    const goalModal = new bootstrap.Modal(document.getElementById('goalModal'));

    if (goalForm) {
        goalForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(goalForm);
            
            const data = {
                name: formData.get('name'),
                type: formData.get('type'),
                target_amount: parseFloat(formData.get('target_amount')),
                target_date: formData.get('target_date')
            };

            try {
                const response = await fetch('/add_goal', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data)
                });

                const result = await response.json();
                
                if (result.success) {
                    location.reload(); // Refresh the page to show updated data
                    showFlash('Goal created successfully!', 'success');
                } else {
                    showFlash(result.error || 'Error creating goal', 'danger');
                }
            } catch (error) {
                console.error('Error:', error);
                showFlash('An error occurred while saving the goal.', 'danger');
            }
        });
    }

    // Edit goal function
    window.editGoal = async function(goalId) {
        try {
            const response = await fetch(`/get_goal/${goalId}`);
            const data = await response.json();
            
            if (data.success) {
                const goal = data.goal;
                const form = document.getElementById('goalForm');
                
                // Set form values
                form.querySelector('[name="name"]').value = goal.name;
                form.querySelector('[name="type"]').value = goal.type;
                form.querySelector('[name="target_amount"]').value = goal.target_amount;
                form.querySelector('[name="target_date"]').value = goal.target_date;
                form.querySelector('[name="goal_id"]').value = goal.id;
                
                // Show modal
                const modal = new bootstrap.Modal(document.getElementById('goalModal'));
                modal.show();
            } else {
                showFlash('Error loading goal details', 'danger');
            }
        } catch (error) {
            console.error('Error:', error);
            showFlash('Error loading goal details', 'danger');
        }
    };

    // Delete goal function with confirmation
    window.deleteGoal = async function(goalId) {
        if (!confirm('Are you sure you want to delete this goal?')) {
            return;
        }

        try {
            const response = await fetch(`/delete_goal/${goalId}`, {
                method: 'DELETE',
            });
            
            const result = await response.json();
            
            if (result.success) {
                const goalElement = document.getElementById(`goal-${goalId}`);
                if (goalElement) {
                    goalElement.remove();
                }
                showFlash('Goal deleted successfully!', 'success');
                location.reload(); // Refresh to update any related data
            } else {
                showFlash(result.error || 'Error deleting goal', 'danger');
            }
        } catch (error) {
            console.error('Error:', error);
            showFlash('Error deleting goal', 'danger');
        }
    };

    function showFlash(message, type = 'success') {
        const flashContainer = document.getElementById('flash-messages') || createFlashContainer();
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.role = 'alert';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        flashContainer.appendChild(alert);
        
        setTimeout(() => {
            alert.remove();
        }, 5000);
    }

    function createFlashContainer() {
        const container = document.createElement('div');
        container.id = 'flash-messages';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1050';
        document.body.appendChild(container);
        return container;
    }

    // Flash message function
    function showFlash(message, type = 'success') {
        const flashDiv = document.createElement('div');
        flashDiv.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
        flashDiv.style.zIndex = '1050';
        flashDiv.textContent = message;
        document.body.appendChild(flashDiv);

        setTimeout(() => {
            flashDiv.remove();
        }, 5000);
    }

    // Function to add a new goal card to the UI
    function addGoalCard(goal) {
        const container = document.getElementById('goals-container');
        const progressPercentage = (goal.current_amount / goal.target_amount) * 100;
        
        const card = document.createElement('div');
        card.className = 'col-md-6 col-lg-4';
        card.id = `goal-card-${goal.id}`;
        
        card.innerHTML = `
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
                        <div class="progress-bar" 
                             role="progressbar" 
                             style="width: ${progressPercentage}%" 
                             aria-valuenow="${progressPercentage}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                            ${progressPercentage.toFixed(1)}%
                        </div>
                    </div>
                    <p class="card-text">
                        Current: ${goal.current_amount.toLocaleString()} Ft<br>
                        Target: ${goal.target_amount.toLocaleString()} Ft<br>
                        Due Date: ${goal.target_date}
                    </p>
                </div>
            </div>
        `;
        
        container.prepend(card);
    }

    // Delete goal handler
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('delete-goal')) {
            const goalId = e.target.dataset.goalId;
            const goalCard = document.getElementById(`goal-card-${goalId}`);
            
            fetch(`/delete_goal/${goalId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (goalCard) {
                        goalCard.remove();
                    }
                    showFlash('Goal deleted successfully!');
                } else {
                    showFlash(data.error, 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showFlash('An error occurred while deleting the goal.', 'danger');
            });
        }
    });

    // Edit goal handler
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('edit-goal')) {
            const goalId = e.target.dataset.goalId;
            fetch(`/get_goal/${goalId}`)
            .then(response => response.json())
            .then(data => {
                // In your edit goal handler
                if (data.success) {
                    document.getElementById('goal_id').value = data.goal.id;
                    document.getElementById('goal_name').value = data.goal.name;
                    document.getElementById('goal_type').value = data.goal.type;
                    document.getElementById('target_amount').value = data.goal.target_amount;
                    document.getElementById('target_date').value = data.goal.target_date;
                    
                    const modalTitle = document.querySelector('#goalModal .modal-title');
                    if (modalTitle) {
                        modalTitle.textContent = 'Edit Goal';
                    }
                    goalModal.show();
                } else {
                    showFlash(data.error, 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showFlash('Error loading goal details', 'danger');
            });
        }
    });

    function addGoalCard(goal) {
        const goalsContainer = document.getElementById('goals-container');
        const newCard = createGoalCardHtml(goal);
        goalsContainer.insertAdjacentHTML('beforeend', newCard);
    }

    function updateGoalCard(goal) {
        const goalCard = document.getElementById(`goal-card-${goal.id}`);
        if (goalCard) {
            goalCard.outerHTML = createGoalCardHtml(goal);
        }
    }

    function createGoalCardHtml(goal) {
        const formatNumber = (num) => num.toLocaleString('hu-HU', { maximumFractionDigits: 0 });
        let progressBarClass = 'bg-primary';
        if (goal.progress >= 100) {
            progressBarClass = 'bg-success';
        } else if (goal.progress >= 75) {
            progressBarClass = 'bg-info';
        } else if (goal.progress >= 50) {
            progressBarClass = 'bg-warning';
        }
    
        return `
            <div class="col-md-6 col-lg-4" id="goal-card-${goal.id}">
                <div class="card h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <div>
                                <h5 class="card-title">${goal.name}</h5>
                                <span class="badge ${goal.type === 'income' ? 'bg-success' : 'bg-danger'} mb-2">
                                    ${goal.type.charAt(0).toUpperCase() + goal.type.slice(1)}
                                </span>
                            </div>
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
                            <div class="progress-bar ${progressBarClass}" role="progressbar" 
                                 style="width: ${Math.min(goal.progress, 100)}%" 
                                 aria-valuenow="${goal.progress}" 
                                 aria-valuemin="0" 
                                 aria-valuemax="100">
                                ${goal.progress}%
                            </div>
                        </div>
                        <p class="card-text">
                            Current: ${formatNumber(goal.current_amount)} Ft<br>
                            Target: ${formatNumber(goal.target_amount)} Ft<br>
                            Due Date: ${goal.target_date}
                        </p>
                    </div>
                </div>
            </div>
        `;
    }
});