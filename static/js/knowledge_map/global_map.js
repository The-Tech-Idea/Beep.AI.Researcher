/**
 * Phase 3 Global Knowledge Map UI.
 * All user-facing strings use window.BEEP_I18N translations.
 */
(function () {
    'use strict';

    var t = window.BEEP_I18N || function(k) { return k; };

    var loadingEl = document.getElementById('globalMapLoading');
    var containerEl = document.getElementById('globalMapContainer');
    var graphCanvas = document.getElementById('globalGraphCanvas');
    var nodeList = document.getElementById('globalNodeList');

    if (!loadingEl || !containerEl) return;

    fetch('/knowledge-map/data')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            loadingEl.setAttribute('hidden', '');
            containerEl.removeAttribute('hidden');

            var nodes = data.nodes || [];
            var edges = data.edges || [];

            // Render node list
            if (nodeList) {
                nodeList.innerHTML = '';
                nodes.slice(0, 200).forEach(function (n) {
                    var div = document.createElement('div');
                    div.className = 'p-2 border-bottom border-secondary';
                    div.innerHTML =
                        '<strong class="small">' + esc(n.title || t('knowledge_map.global.untitled')) + '</strong>' +
                        '<div class="text-muted small">' + (n.project_name || '') + ' · ' + (n.year || t('knowledge_map.global.no_date')) + '</div>';
                    nodeList.appendChild(div);
                });
            }

            // Simple graph
            if (graphCanvas && nodes.length > 0) {
                renderGlobalGraph(graphCanvas, nodes, edges);
            }
        })
        .catch(function (e) {
            loadingEl.innerHTML = '<div class="alert alert-danger">' + t('knowledge_map.global.error.failed') + e.message + '</div>';
        });

    function renderGlobalGraph(container, nodes, edges) {
        var canvas = document.createElement('canvas');
        canvas.width = container.offsetWidth || 800;
        canvas.height = container.offsetHeight || 600;
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        container.innerHTML = '';
        container.appendChild(canvas);

        var ctx = canvas.getContext('2d');
        var W = canvas.width;
        var H = canvas.height;
        var pos = {};

        nodes.forEach(function (n, i) {
            pos[n.id] = {
                x: 30 + Math.random() * (W - 60),
                y: 30 + Math.random() * (H - 60),
                vx: 0, vy: 0,
            };
        });

        var alpha = 1;
        function tick() {
            alpha *= 0.985;
            if (alpha < 0.001) {
                draw(ctx, pos, nodes, edges);
                return;
            }

            for (var i = 0; i < nodes.length; i++) {
                for (var j = i + 1; j < nodes.length; j++) {
                    var a = pos[nodes[i].id], b = pos[nodes[j].id];
                    var dx = b.x - a.x, dy = b.y - a.y;
                    var dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    var force = 3000 / (dist * dist);
                    a.vx -= dx / dist * force * alpha;
                    a.vy -= dy / dist * force * alpha;
                    b.vx += dx / dist * force * alpha;
                    b.vy += dy / dist * force * alpha;
                }
            }

            edges.forEach(function (e) {
                var a = pos[e.source], b = pos[e.target];
                if (!a || !b) return;
                var dx = b.x - a.x, dy = b.y - a.y;
                var dist = Math.sqrt(dx * dx + dy * dy) || 1;
                var force = (dist - 80) * 0.005 * alpha;
                a.vx += dx / dist * force;
                a.vy += dy / dist * force;
                b.vx -= dx / dist * force;
                b.vy -= dy / dist * force;
            });

            nodes.forEach(function (n) {
                var p = pos[n.id];
                p.vx *= 0.85; p.vy *= 0.85;
                p.x += p.vx; p.y += p.vy;
                p.x = Math.max(10, Math.min(W - 10, p.x));
                p.y = Math.max(10, Math.min(H - 10, p.y));
            });

            draw(ctx, pos, nodes, edges);
            requestAnimationFrame(tick);
        }

        function draw(ctx, pos, nodes, edges) {
            ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
            edges.forEach(function (e) {
                var a = pos[e.source], b = pos[e.target];
                if (!a || !b) return;
                ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
                ctx.strokeStyle = 'rgba(13,202,240,0.15)';
                ctx.lineWidth = 0.5;
                ctx.stroke();
            });
            nodes.forEach(function (n) {
                var p = pos[n.id];
                ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
                ctx.fillStyle = '#0dcaf0';
                ctx.fill();
            });
        }

        tick();
    }

    function esc(str) { var el = document.createElement('span'); el.textContent = str || ''; return el.innerHTML; }
})();
