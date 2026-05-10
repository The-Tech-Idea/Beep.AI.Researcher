/**
 * Phase 3 Knowledge Map UI — force-directed graph + node list.
 * All user-facing strings use window.BEEP_I18N translations.
 */
(function () {
    'use strict';

    var t = window.BEEP_I18N || function(k) { return k; };

    var projectId = window.location.pathname.match(/\/projects\/(\d+)/);
    projectId = projectId ? projectId[1] : null;
    if (!projectId) return;

    var loadingEl = document.getElementById('mapLoading');
    var containerEl = document.getElementById('mapContainer');
    var graphCanvas = document.getElementById('graphCanvas');
    var nodeList = document.getElementById('nodeList');
    var listBody = document.getElementById('listBody');
    var listView = document.getElementById('listView');
    var toggleBtn = document.getElementById('btnToggleView');
    var exportBtn = document.getElementById('btnExportMap');

    var nodes = [];
    var edges = [];
    var isListView = false;

    if (!loadingEl || !containerEl) return;

    fetch('/projects/' + projectId + '/knowledge-map/data')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            loadingEl.setAttribute('hidden', '');
            containerEl.removeAttribute('hidden');

            nodes = data.nodes || [];
            edges = data.edges || [];

            renderNodeList(nodes, edges);
            renderListView(nodes, edges);
            renderSimpleGraph(nodes, edges);
        })
        .catch(function (e) {
            loadingEl.innerHTML = '<div class="alert alert-danger">' + t('knowledge_map.error.failed') + e.message + '</div>';
        });

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function () {
            isListView = !isListView;
            if (isListView) {
                containerEl.setAttribute('hidden', '');
                listView.removeAttribute('hidden');
                toggleBtn.innerHTML = '<i class="bi bi-graph-up me-1"></i>' + t('knowledge_map.show_graph');
            } else {
                listView.setAttribute('hidden', '');
                containerEl.removeAttribute('hidden');
                toggleBtn.innerHTML = '<i class="bi bi-grid-3x3-gap me-1"></i>' + t('knowledge_map.show_cards');
            }
        });
    }

    if (exportBtn) {
        exportBtn.addEventListener('click', function () {
            fetch('/projects/' + projectId + '/knowledge-map/export')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                    var url = URL.createObjectURL(blob);
                    var a = document.createElement('a');
                    a.href = url;
                    a.download = 'knowledge_map.json';
                    a.click();
                    URL.revokeObjectURL(url);
                })
                .catch(function () {
                    showToast(t('knowledge_map.error.export_failed'), 'warning');
                });
        });
    }

    function renderNodeList(nodes, edges) {
        nodeList.innerHTML = '';
        nodes.forEach(function (n) {
            var connCount = edges.filter(function (e) {
                return e.source === n.id || e.target === n.id;
            }).length;

            var div = document.createElement('div');
            div.className = 'p-2 border-bottom border-secondary cursor-pointer';
            div.style.cursor = 'pointer';
            div.innerHTML =
                '<strong class="small">' + esc(n.title || t('knowledge_map.untitled')) + '</strong>' +
                '<div class="text-muted small">' + (n.year || t('knowledge_map.no_date')) + ' · ' + connCount + ' ' + t('knowledge_map.connections_label') + '</div>';

            div.addEventListener('click', function () {
                showNodeDetail(n, connCount);
            });

            nodeList.appendChild(div);
        });
    }

    function renderListView(nodes, edges) {
        listBody.innerHTML = '';
        nodes.forEach(function (n) {
            var connCount = edges.filter(function (e) {
                return e.source === n.id || e.target === n.id;
            }).length;

            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td>' + esc(n.title || t('knowledge_map.untitled')) + '</td>' +
                '<td>' + (n.year || t('knowledge_map.no_date')) + '</td>' +
                '<td class="small text-muted">' + esc((n.id || '').replace('doi:', '')) + '</td>' +
                '<td><span class="badge bg-info">' + connCount + '</span></td>';
            listBody.appendChild(tr);
        });
    }

    function renderSimpleGraph(nodes, edges) {
        if (nodes.length === 0) {
            graphCanvas.innerHTML = '<div class="d-flex align-items-center justify-content-center h-100 text-muted">' + t('knowledge_map.empty_state') + '</div>';
            return;
        }

        // Simple canvas-based force-directed layout
        var canvas = document.createElement('canvas');
        canvas.width = graphCanvas.offsetWidth || 800;
        canvas.height = graphCanvas.offsetHeight || 600;
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        graphCanvas.innerHTML = '';
        graphCanvas.appendChild(canvas);

        var ctx = canvas.getContext('2d');
        var W = canvas.width;
        var H = canvas.height;

        // Initialize positions
        var pos = {};
        nodes.forEach(function (n, i) {
            pos[n.id] = {
                x: 50 + Math.random() * (W - 100),
                y: 50 + Math.random() * (H - 100),
                vx: 0,
                vy: 0,
            };
        });

        // Force simulation
        var alpha = 1;
        function tick() {
            alpha *= 0.99;
            if (alpha < 0.001) {
                draw(ctx, pos, nodes, edges);
                return;
            }

            // Repulsion between all nodes
            for (var i = 0; i < nodes.length; i++) {
                for (var j = i + 1; j < nodes.length; j++) {
                    var a = pos[nodes[i].id];
                    var b = pos[nodes[j].id];
                    var dx = b.x - a.x;
                    var dy = b.y - a.y;
                    var dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    var force = 5000 / (dist * dist);
                    a.vx -= dx / dist * force * alpha;
                    a.vy -= dy / dist * force * alpha;
                    b.vx += dx / dist * force * alpha;
                    b.vy += dy / dist * force * alpha;
                }
            }

            // Attraction along edges
            edges.forEach(function (e) {
                var a = pos[e.source];
                var b = pos[e.target];
                if (!a || !b) return;
                var dx = b.x - a.x;
                var dy = b.y - a.y;
                var dist = Math.sqrt(dx * dx + dy * dy) || 1;
                var force = (dist - 100) * 0.01 * alpha;
                a.vx += dx / dist * force;
                a.vy += dy / dist * force;
                b.vx -= dx / dist * force;
                b.vy -= dy / dist * force;
            });

            // Center gravity
            nodes.forEach(function (n) {
                var p = pos[n.id];
                p.vx += (W / 2 - p.x) * 0.005 * alpha;
                p.vy += (H / 2 - p.y) * 0.005 * alpha;
            });

            // Update positions
            nodes.forEach(function (n) {
                var p = pos[n.id];
                p.vx *= 0.8;
                p.vy *= 0.8;
                p.x = Math.max(20, Math.min(W - 20, p.x + p.vx));
                p.y = Math.max(20, Math.min(H - 20, p.y + p.vy));
            });

            draw(ctx, pos, nodes, edges);
            requestAnimationFrame(tick);
        }

        tick();

        // Click handling
        canvas.addEventListener('click', function (ev) {
            var rect = canvas.getBoundingClientRect();
            var mx = (ev.clientX - rect.left) * (canvas.width / rect.width);
            var my = (ev.clientY - rect.top) * (canvas.height / rect.height);

            nodes.forEach(function (n) {
                var p = pos[n.id];
                if (Math.abs(mx - p.x) < 15 && Math.abs(my - p.y) < 15) {
                    var connCount = edges.filter(function (e) {
                        return e.source === n.id || e.target === n.id;
                    }).length;
                    showNodeDetail(n, connCount);
                }
            });
        });
    }

    function draw(ctx, pos, nodes, edges) {
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);

        // Draw edges
        edges.forEach(function (e) {
            var a = pos[e.source];
            var b = pos[e.target];
            if (!a || !b) return;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = 'rgba(13,202,240,0.3)';
            ctx.lineWidth = 1;
            ctx.stroke();
        });

        // Draw nodes
        nodes.forEach(function (n) {
            var p = pos[n.id];
            ctx.beginPath();
            ctx.arc(p.x, p.y, n.is_ghost ? 5 : 8, 0, Math.PI * 2);
            ctx.fillStyle = n.is_ghost ? 'rgba(255,255,255,0.3)' : '#0dcaf0';
            ctx.fill();

            if (!n.is_ghost) {
                ctx.fillStyle = '#adb5bd';
                ctx.font = '9px sans-serif';
                ctx.fillText(n.title ? n.title.substring(0, 20) + '…' : '', p.x + 10, p.y + 3);
            }
        });
    }

    function showNodeDetail(node, connCount) {
        document.getElementById('nodeDetailTitle').textContent = node.title || 'Untitled';
        document.getElementById('nodeDetailBody').innerHTML =
            '<p><strong>' + t('knowledge_map.detail.year') + ':</strong> ' + (node.year || t('knowledge_map.no_date')) + '</p>' +
            '<p><strong>' + t('knowledge_map.detail.doi') + ':</strong> <code>' + esc((node.id || '').replace('doi:', '')) + '</code></p>' +
            '<p><strong>' + t('knowledge_map.detail.connections') + ':</strong> ' + connCount + '</p>' +
            '<p><strong>' + t('knowledge_map.detail.authors') + ':</strong> ' + esc((node.authors || []).join(', ')) + '</p>' +
            '<p><strong>' + t('knowledge_map.detail.source') + ':</strong> ' + esc(node.source || '') + '</p>';

        var expandBtn = document.getElementById('btnExpandNode');
        if (node.is_ghost || connCount === 0) {
            expandBtn.style.display = '';
            expandBtn.onclick = function () {
                fetch('/projects/' + projectId + '/knowledge-map/expand', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ doi: (node.id || '').replace('doi:', '') }),
                })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.error) {
                        showToast(t('knowledge_map.error.expand_failed') + data.error, 'warning');
                        return;
                    }
                    showToast(t('knowledge_map.toast.fetched_neighbours') + ' ' + (data.nodes || []).length + ' ' + t('knowledge_map.toast.fetched_neighbours'), 'success');
                })
                .catch(function (e) {
                    showToast(t('knowledge_map.error.expand_failed') + e.message, 'warning');
                });
            };
        } else {
            expandBtn.style.display = 'none';
        }

        var modal = new bootstrap.Modal(document.getElementById('nodeDetailModal'));
        modal.show();
    }

    function esc(str) { var el = document.createElement('span'); el.textContent = str || ''; return el.innerHTML; }
    function showToast(msg, type) {
        var toast = document.createElement('div');
        toast.style.cssText = 'position:fixed;bottom:2rem;right:2rem;z-index:9999;padding:0.75rem 1rem;border-radius:0.5rem;color:#fff;font-size:0.85rem;';
        toast.style.background = type === 'success' ? '#198754' : type === 'warning' ? '#fd7e14' : '#0dcaf0';
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(function () { toast.style.opacity = '0'; setTimeout(function () { toast.remove(); }, 300); }, 3000);
    }
})();
