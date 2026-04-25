/* Document map page logic */
(function () {
    'use strict';

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    var canvas = document.getElementById('mapCanvas');
    var emptyState = document.getElementById('mapEmptyState');
    if (!canvas) {
        return;
    }

    var projectId = canvas.dataset.projectId;

    function showEmptyState() {
        canvas.innerHTML = '';
        if (emptyState) {
            emptyState.hidden = false;
        }
    }

    function renderGraph(nodes, edges) {
        var nodeMarkup = nodes.map(function (node) {
            var typeClass = node.type === 'document'
                ? 'document-map-node document-map-node-document'
                : 'document-map-node document-map-node-code';
            return '<span class="' + typeClass + '">' + escapeHtml(node.label) + '</span>';
        }).join('');

        var edgeMarkup = edges.map(function (edge) {
            return '<span class="document-map-edge">' +
                escapeHtml(edge.from) + ' &rarr; ' + escapeHtml(edge.to) +
                '</span>';
        }).join('');

        canvas.innerHTML = '<div class="document-map-node-list">' + nodeMarkup + '</div>' +
            '<div class="document-map-edge-list">' + edgeMarkup + '</div>';
    }

    fetch('/projects/' + projectId + '/map')
        .then(function (r) { return r.json(); })
        .then(function (j) {
            if (!j.nodes || j.nodes.length === 0) {
                showEmptyState();
                return;
            }

            if (emptyState) {
                emptyState.hidden = true;
            }

            var nodes = j.nodes.map(function (n) {
                return { id: n.id, label: n.label, type: n.type || 'node' };
            });
            var edges = (j.edges || []).map(function (e) {
                return { from: e.source, to: e.target };
            });

            renderGraph(nodes, edges);
        })
        .catch(function () {
            showEmptyState();
        });
})();
