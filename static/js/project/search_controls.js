(function () {
    function applySliderState(slider, select, label) {
        var modes = ['fast', 'balanced', 'deep'];
        var presets = [
            { rewriteQuery: false, hybridSearch: false, rerank: false, groundedOnly: false },
            { rewriteQuery: true, hybridSearch: true, rerank: true, groundedOnly: true },
            { rewriteQuery: true, hybridSearch: true, rerank: true, groundedOnly: true },
        ];
        var rawValue = Number.parseInt(slider.value, 10);
        var index = Number.isFinite(rawValue) ? Math.max(1, Math.min(3, rawValue)) - 1 : 1;
        var selectedMode = modes[index];
        var selectedLabel = select && select.options[index] ? select.options[index].text : '';

        if (select) {
            select.value = selectedMode;
        }
        if (label) {
            label.textContent = selectedLabel;
        }

        ['rewriteQuery', 'hybridSearch', 'rerank', 'groundedOnly'].forEach(function (id) {
            var element = document.getElementById(id);
            if (element) {
                element.checked = Boolean(presets[index][id]);
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var slider = document.getElementById('answerQualitySlider');
        var select = document.getElementById('qualityMode');
        var label = document.getElementById('qualityLabel');
        if (!slider || !select || !label) {
            return;
        }

        slider.addEventListener('input', function () {
            applySliderState(slider, select, label);
        });

        applySliderState(slider, select, label);
    });
})();
