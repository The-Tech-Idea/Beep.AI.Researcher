(function () {
    'use strict';

    const configNode = document.getElementById('data-page-config');
    if (!configNode?.textContent) {
        return;
    }

    let config = {};
    try {
        config = JSON.parse(configNode.textContent);
    } catch (error) {
        console.error('Failed to parse data page config.', error);
        return;
    }

    const projectId = config.projectId;
    const uploadInput = document.getElementById('dataFileInput');
    const uploadButton = document.getElementById('dataUploadBtn');
    const refreshButton = document.getElementById('refreshChartBtn');
    const chartSource = document.getElementById('chartSource');
    const chartType = document.getElementById('chartType');
    const chartCanvas = document.getElementById('chartCanvas');
    const dataStatus = document.getElementById('dataStatus');
    const dataProgress = document.getElementById('dataUploadBar');
    const sourceButtons = document.querySelectorAll('.data-source-button');
    const strings = config.strings || {};
    let chartInstance = null;

    function notify(message, options = {}) {
        if (message) {
            window.beepUI.notify(message, options);
        }
    }

    function updateDataStatus(text, variant = 'info') {
        if (!dataStatus) {
            return;
        }

        window.beepUI.setFlowStatus(dataStatus, text, variant);
    }

    function setUploadProgress(percent) {
        if (!dataProgress) {
            return;
        }

        dataProgress.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    }

    async function loadChart(sourceId) {
        if (!sourceId || !chartSource || !chartType || !chartCanvas || !config.chartUrl) {
            return;
        }

        chartSource.value = sourceId;
        updateDataStatus(strings.loadingChart, 'info');

        const response = await fetch(config.chartUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_id: sourceId, chart_type: chartType.value }),
        });
        const payload = await response.json();
        const context = chartCanvas.getContext('2d');

        if (chartInstance) {
            chartInstance.destroy();
        }

        if (payload.chart && payload.chart.labels && payload.chart.values && typeof Chart !== 'undefined') {
            chartInstance = new Chart(context, {
                type: payload.chart.chart_type || 'bar',
                data: {
                    labels: payload.chart.labels,
                    datasets: [{
                        label: payload.chart.y_column || 'value',
                        data: payload.chart.values,
                        backgroundColor: 'rgba(99,102,241,0.5)',
                    }],
                },
                options: { responsive: true },
            });
            updateDataStatus(strings.chartReady, 'success');
            return;
        }

        updateDataStatus(strings.chartFailed, 'danger');
    }

    function refreshChart() {
        if (!chartSource?.value) {
            return;
        }

        loadChart(parseInt(chartSource.value, 10));
    }

    uploadButton?.addEventListener('click', () => uploadInput?.click());
    refreshButton?.addEventListener('click', refreshChart);

    sourceButtons.forEach((button) => {
        button.addEventListener('click', () => {
            const sourceId = parseInt(button.dataset.sourceId || '', 10);
            if (!Number.isNaN(sourceId)) {
                loadChart(sourceId);
            }
        });
    });

    uploadInput?.addEventListener('change', function onFileChange() {
        const file = this.files && this.files[0];
        if (!file) {
            return;
        }

        const ext = file.name.split('.').pop().toLowerCase();
        if (!['csv', 'xlsx'].includes(ext)) {
            notify(strings.invalidType, { variant: 'warning' });
            return;
        }

        const xhr = new XMLHttpRequest();
        xhr.open('POST', config.uploadUrl);
        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
                setUploadProgress((event.loaded / event.total) * 100);
            }
        });
        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                updateDataStatus(strings.uploadSuccess, 'success');
                notify(strings.uploadSuccess, { variant: 'success' });
                setTimeout(() => window.location.reload(), 700);
                return;
            }

            updateDataStatus(strings.uploadFailed, 'danger');
            notify(xhr.responseText || strings.uploadFailed, { variant: 'danger' });
            setUploadProgress(0);
        };
        xhr.onerror = () => {
            updateDataStatus(strings.uploadFailed, 'danger');
            notify(strings.uploadFailed, { variant: 'danger' });
            setUploadProgress(0);
        };

        const form = new FormData();
        form.append('file', file);
        updateDataStatus(strings.uploading, 'info');
        xhr.send(form);
    });

    chartSource?.addEventListener('change', function onSourceChange() {
        if (this.value) {
            loadChart(parseInt(this.value, 10));
        }
    });
    chartType?.addEventListener('change', refreshChart);

    if (projectId && config.initialSourceId) {
        loadChart(config.initialSourceId);
    }
})();
