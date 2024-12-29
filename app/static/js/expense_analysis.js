document.addEventListener('DOMContentLoaded', function() {
    // Chart Theme Configuration
    const chartTheme = {
        primary: '#0d6efd',
        success: '#198754',
        danger: '#dc3545',
        warning: '#ffc107',
        info: '#0dcaf0',
        dark: '#212529',
        light: '#f8f9fa',
        grid: '#e9ecef'
    };

    // Utility Functions
    const formatCurrency = (value) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(value);
    };

    // Initialize Monthly Trends Chart
    const monthlyTrendsOptions = {
        series: [{
            name: 'Income',
            data: chartData.monthly_income
        }, {
            name: 'Expenses',
            data: chartData.monthly_expenses
        }],
        chart: {
            type: 'line',
            height: 350,
            fontFamily: 'inherit',
            toolbar: {
                show: true,
                tools: {
                    download: true,
                    selection: true,
                    zoom: true,
                    zoomin: true,
                    zoomout: true,
                    pan: true,
                    reset: true
                }
            },
            animations: {
                enabled: true
            }
        },
        colors: [chartTheme.success, chartTheme.danger],
        stroke: {
            curve: 'smooth',
            width: 2
        },
        grid: {
            borderColor: chartTheme.grid,
            padding: {
                top: 0,
                right: 0,
                bottom: 0,
                left: 10
            }
        },
        markers: {
            size: 4,
            strokeWidth: 0,
            hover: {
                size: 6
            }
        },
        xaxis: {
            categories: chartData.months,
            labels: {
                rotate: -45,
                style: {
                    fontSize: '12px'
                }
            },
            axisBorder: {
                show: false
            }
        },
        yaxis: {
            labels: {
                formatter: function(value) {
                    return formatCurrency(value);
                }
            }
        },
        legend: {
            position: 'top',
            horizontalAlign: 'left',
            offsetY: -10
        },
        tooltip: {
            shared: true,
            intersect: false,
            y: {
                formatter: function(value) {
                    return formatCurrency(value);
                }
            }
        }
    };

    // Initialize Expense Distribution Chart
    const expenseDistributionOptions = {
        series: chartData.category_amounts,
        chart: {
            type: 'donut',
            height: 350,
            fontFamily: 'inherit'
        },
        labels: chartData.categories,
        colors: [
            chartTheme.primary,
            chartTheme.success,
            chartTheme.danger,
            chartTheme.warning,
            chartTheme.info,
            '#6f42c1',
            '#fd7e14',
            '#20c997'
        ],
        plotOptions: {
            pie: {
                donut: {
                    size: '70%',
                    labels: {
                        show: true,
                        name: {
                            show: true
                        },
                        value: {
                            show: true,
                            formatter: function(val) {
                                return formatCurrency(val);
                            }
                        },
                        total: {
                            show: true,
                            label: 'Total Expenses',
                            formatter: function(w) {
                                const total = w.globals.seriesTotals.reduce((a, b) => a + b, 0);
                                return formatCurrency(total);
                            }
                        }
                    }
                }
            }
        },
        legend: {
            position: 'bottom',
            offsetY: 0
        },
        tooltip: {
            y: {
                formatter: function(value) {
                    return formatCurrency(value);
                }
            }
        }
    };

    // Render Charts
    const monthlyTrendsChart = new ApexCharts(
        document.querySelector("#monthlyTrendsChart"), 
        monthlyTrendsOptions
    );
    monthlyTrendsChart.render();

    const expenseDistributionChart = new ApexCharts(
        document.querySelector("#expenseDistributionChart"), 
        expenseDistributionOptions
    );
    expenseDistributionChart.render();

    // Handle Time Range Changes
    const timeRangeSelect = document.getElementById('timeRange');
    const refreshButton = document.getElementById('refreshData');

    async function updateData() {
        try {
            refreshButton.querySelector('i').classList.add('refreshing');
            const response = await fetch(`/api/expense-analysis?timeRange=${timeRangeSelect.value}`);
            
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const newData = await response.json();
            
            // Update charts with new data
            monthlyTrendsChart.updateSeries([{
                name: 'Income',
                data: newData.monthly_income
            }, {
                name: 'Expenses',
                data: newData.monthly_expenses
            }]);

            expenseDistributionChart.updateSeries(newData.category_amounts);
            expenseDistributionChart.updateOptions({ labels: newData.categories });

            // Update summary cards
            // Add code here to update your summary cards if needed

        } catch (error) {
            console.error('Error fetching data:', error);
            // Show error notification to user
            alert('Failed to update data. Please try again.');
        } finally {
            refreshButton.querySelector('i').classList.remove('refreshing');
        }
    }

    timeRangeSelect.addEventListener('change', updateData);
    refreshButton.addEventListener('click', updateData);
});
