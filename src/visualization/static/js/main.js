document.addEventListener('DOMContentLoaded', function () {
    const tradingForm = document.getElementById('trading-form');
    if (tradingForm) {
        tradingForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const formData = new FormData(tradingForm);

            try {
                const chartContainer = document.getElementById('trading-chart');
                chartContainer.innerHTML = '<p class="text-white">Loading chart...</p>';

                // Fetch backtest results
                const response = await fetch('/backtest', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.error || 'Failed to run backtest');
                }

                // Validate received data
                if (!result.chart_json || !result.chart_json.data || !result.chart_json.layout) {
                    console.error('Invalid chart JSON:', result);
                    throw new Error('Invalid chart data received.');
                }

                // Render price and volume chart
                Plotly.newPlot('trading-chart', result.chart_json.data, result.chart_json.layout)
                    .then(() => console.log('Chart rendered successfully'))
                    .catch(err => console.error('Error rendering chart:', err));
            } catch (error) {
                console.error('Error fetching or rendering chart:', error);
                alert(`Failed to render chart: ${error.message}`);
            }
        });
    }
});
