document.addEventListener('DOMContentLoaded', function () {
    // Handle chart form submission
    const chartForm = document.getElementById('chartForm');
    if (chartForm) {
        chartForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const formData = new FormData(chartForm);
            const response = await fetch(chartForm.action, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.error) {
                alert(data.error);
            } else {
                const chartContainer = document.getElementById('chart-container');
                chartContainer.innerHTML = ''; // Clear previous chart
                Plotly.newPlot('chart-1', data.data, data.layout);
            }
        });
    }
});