document.addEventListener('DOMContentLoaded', function() {
    initializeCharts();
    setupEventListeners();
    addHoverEffects();
});

function initializeCharts() {
    // Monthly Trends Chart
    const monthlyTrendsOptions = {
        series: [{
            name: 'Income',
            data: chartData.incomeValues
        }, {
            name: 'Expenses',
            data: chartData.expenseValues
        }],
        chart: {
            type: 'area',
            height: 350,
            toolbar: {
                show: false
            },
            animations: {
                enabled: true,
                easing: 'easeinout',
                speed: 800
            }
        },
        colors: ['#28a745', '#dc3545'],
        fill: {
            type: 'gradient',
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.7,
                opacityTo: 0.3,
                stops: [0, 90, 100]
            }
        },
        stroke: {
            curve: 'smooth',
            width: 2
        },
        xaxis: {
            categories: chartData.trendLabels,
            labels: {
                rotate: -45,
                rotateAlways: false
            }
        },
        yaxis: {
            labels: {
                formatter: function(value) {
                    return '$' + value.toLocaleString();
                }
            }
        },
        tooltip: {
            shared: true,
            y: {
                formatter: function(value) {
                    return '$' + value.toLocaleString();
                }
            }
        }
    };

    // Expense Distribution Chart
    const expenseDistributionOptions = {
        series: chartData.expenseData,
        chart: {
            type: 'donut',
            height: 350
        },
        labels: chartData.expenseLabels,
        colors: chartData.categoryColors,
        plotOptions: {
            pie: {
                donut: {
                    size: '70%'
                }
            }
        },
        tooltip: {
            y: {
                formatter: function(value) {
                    return '$' + value.toLocaleString();
                }
            }
        },
        legend: {
            position: 'bottom'
        },
        responsive: [{
            breakpoint: 480,
            options: {
                chart: {
                    height: 300
                },
                legend: {
                    position: 'bottom'
                }
            }
        }]
    };

    const monthlyTrendsChart = new ApexCharts(
        document.querySelector("#monthlyTrendsChart"), 
        monthlyTrendsOptions
    );

    const expenseDistributionChart = new ApexCharts(
        document.querySelector("#expenseDistributionChart"), 
        expenseDistributionOptions
    );

    monthlyTrendsChart.render();
    expenseDistributionChart.render();
}

function setupEventListeners() {
    // Time range selector
    document.getElementById('timeRange').addEventListener('change', function() {
        updateData(this.value);
    });

    // Refresh button
    document.getElementById('refreshData').addEventListener('click', function() {
        const range = document.getElementById('timeRange').value;
        updateData(range);
    });
}

async function updateData(timeRange) {
    try {
        showLoading(true);
        const response = await fetch(`/api/expense-data?range=${timeRange}`);
        const data = await response.json();
        
        if (data.success) {
            updateCharts(data);
            updateSummaryCards(data);
            updateBudgetTable(data);
        } else {
            showToast('Error', data.error || 'Failed to update data', 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error', 'An unexpected error occurred', 'danger');
    } finally {
        showLoading(false);
    }
}

function showLoading(show) {
    const elements = document.querySelectorAll('.card');
    elements.forEach(element => {
        if (show) {
            element.classList.add('loading');
        } else {
            element.classList.remove('loading');
        }
    });

    const refreshBtn = document.getElementById('refreshData');
    if (show) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    } else {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
    }
}

function showToast(title, message, type = 'success') {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(container);
    }

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-${type} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <strong>${title}</strong><br>${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl);
    toast.show();

    toastEl.addEventListener('hidden.bs.toast', () => {
        toastEl.remove();
    });
}

function addHoverEffects() {
    // Add any additional hover effects if needed
    // Most hover effects are handled in CSS
}
