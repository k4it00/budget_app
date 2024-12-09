document.addEventListener('DOMContentLoaded', function() {
    // Utility function to format currency
    const formatCurrency = (value) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(value);
    };

    // Common chart options
    const commonChartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: {
                    boxWidth: 12,
                    padding: 15,
                    font: {
                        size: window.innerWidth < 768 ? 10 : 11
                    }
                }
            }
        }
    };

    // Pie chart options
    const pieChartOptions = {
        ...commonChartOptions,
        cutout: '40%',
        radius: '90%'
    };

    // Income Chart
    const incomeChart = document.getElementById('incomeChart');
    if (incomeChart && chartData.incomeLabels.length > 0) {
        new Chart(incomeChart, {
            type: 'doughnut',
            data: {
                labels: chartData.incomeLabels,
                datasets: [{
                    data: chartData.incomeData,
                    backgroundColor: [
                        '#4CAF50', '#8BC34A', '#CDDC39', '#FFEB3B', '#FFC107',
                        '#FF9800', '#FF5722', '#795548', '#9E9E9E', '#607D8B'
                    ],
                    borderWidth: 1,
                    borderColor: '#fff'
                }]
            },
            options: {
                ...pieChartOptions,
                plugins: {
                    ...pieChartOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.raw;
                                const index = context.dataIndex;
                                const amount = chartData.income_amounts ? chartData.income_amounts[index] : 0;
                                return `${context.label}: ${value.toFixed(1)}% (${formatCurrency(amount)})`;
                            }
                        }
                    }
                }
            }
        });
    }

    // Expense Chart
    const expenseChart = document.getElementById('expenseChart');
    if (expenseChart && chartData.expenseLabels.length > 0) {
        new Chart(expenseChart, {
            type: 'doughnut',
            data: {
                labels: chartData.expenseLabels,
                datasets: [{
                    data: chartData.expenseData,
                    backgroundColor: [
                        '#f44336', '#E91E63', '#9C27B0', '#673AB7', '#3F51B5',
                        '#2196F3', '#03A9F4', '#00BCD4', '#009688', '#4CAF50'
                    ],
                    borderWidth: 1,
                    borderColor: '#fff'
                }]
            },
            options: {
                ...pieChartOptions,
                plugins: {
                    ...pieChartOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.raw;
                                const index = context.dataIndex;
                                const amount = chartData.expense_amounts ? chartData.expense_amounts[index] : 0;
                                return `${context.label}: ${value.toFixed(1)}% (${formatCurrency(amount)})`;
                            }
                        }
                    }
                }
            }
        });
    }

    // Trend Chart
    const trendChart = document.getElementById('trendChart');
    if (trendChart && chartData.trendLabels.length > 0) {
        new Chart(trendChart, {
            type: 'line',
            data: {
                labels: chartData.trendLabels,
                datasets: [{
                    label: 'Income',
                    data: chartData.incomeValues,
                    borderColor: '#4CAF50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    fill: true,
                    tension: 0.1,
                    borderWidth: 2
                }, {
                    label: 'Expenses',
                    data: chartData.expenseValues,
                    borderColor: '#f44336',
                    backgroundColor: 'rgba(244, 67, 54, 0.1)',
                    fill: true,
                    tension: 0.1,
                    borderWidth: 2
                }]
            },
            options: {
                ...commonChartOptions,
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            font: {
                                size: window.innerWidth < 768 ? 8 : 10
                            }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return formatCurrency(value);
                            },
                            font: {
                                size: window.innerWidth < 768 ? 8 : 10
                            }
                        }
                    }
                },
                plugins: {
                    ...commonChartOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: ${formatCurrency(context.raw)}`;
                            }
                        }
                    }
                }
            }
        });
    }

    // Budget Comparison Chart
    const budgetChart = document.getElementById('budgetChart');
    if (budgetChart && chartData.budgetLabels.length > 0) {
        new Chart(budgetChart, {
            type: 'bar',
            data: {
                labels: chartData.budgetLabels,
                datasets: [{
                    label: 'Budget Used (%)',
                    data: chartData.budgetValues,
                    backgroundColor: chartData.budgetValues.map(value => 
                        value > 100 ? '#f44336' : 
                        value > 80 ? '#FFA726' : '#4CAF50'
                    ),
                    borderWidth: 1
                }]
            },
            options: {
                ...commonChartOptions,
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            font: {
                                size: window.innerWidth < 768 ? 8 : 10
                            }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            },
                            font: {
                                size: window.innerWidth < 768 ? 8 : 10
                            }
                        }
                    }
                },
                plugins: {
                    ...commonChartOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const index = context.dataIndex;
                                const spent = chartData.budgetSpent[index];
                                const limit = chartData.budgetLimits[index];
                                return [
                                    `Spent: ${formatCurrency(spent)}`,
                                    `Budget: ${formatCurrency(limit)}`,
                                    `Used: ${context.raw.toFixed(1)}%`
                                ];
                            }
                        }
                    }
                }
            }
        });
    }

    // Handle window resize
    let resizeTimeout;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(function() {
            // Reload the page to redraw charts
            window.location.reload();
        }, 250);
    });
});
