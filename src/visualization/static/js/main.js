document.addEventListener('DOMContentLoaded', function () {
    const chartForm = document.getElementById('chartForm');
    if (chartForm) {
        chartForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const formData = new FormData(chartForm);

            try {
                const response = await fetch(chartForm.action, {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();

                if (data.error) {
                    alert(data.error);
                    return;
                }

                // Validate received data
                if (!data.chart_json || !data.chart_json.data || !data.chart_json.layout) {
                    console.error('Invalid chart JSON:', data);
                    return;
                }

                // Render chart
                Plotly.newPlot('chart-1', data.chart_json.data, data.chart_json.layout)
                    .then(() => console.log('Chart rendered successfully'))
                    .catch(err => console.error('Error rendering chart:', err));
            } catch (error) {
                console.error('Error fetching or rendering chart:', error);
                alert(`Failed to render chart: ${error.message}`);
            }
        });
    }
});
