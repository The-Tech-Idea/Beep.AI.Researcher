/* Scheduled reports page logic */
(function () {
    'use strict';
    var cfgEl = document.getElementById('scheduled-reports-config');
    if (!cfgEl || !cfgEl.textContent) return;
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { /* noop */ }
    var projectId = cfg.projectId;
    var scheduleUrl = cfg.scheduleUrl;
    if (!projectId || !scheduleUrl) return;

    var frequency = document.getElementById('reportFrequency');
    var cron = document.getElementById('reportCron');
    if (frequency && cron) {
        frequency.addEventListener('change', function () { cron.value = frequency.value; });
    }

    var btn = document.getElementById('btnCreateReport');
    if (btn) {
        btn.addEventListener('click', async function () {
            var name = document.getElementById('reportName').value.trim();
            var cron = document.getElementById('reportCron').value.trim();
            var recipientsRaw = document.getElementById('reportRecipients').value;
            var recipients = recipientsRaw.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
            if (!name) return;
            btn.disabled = true;
            try {
                var r = await fetch(scheduleUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, schedule_cron: cron || '0 9 * * 1', recipients: recipients })
                });
                if (r.ok) location.reload();
            } finally {
                btn.disabled = false;
            }
        });
    }
})();
