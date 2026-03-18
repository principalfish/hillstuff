// Format minutes as H:MM:SS or M:SS
function formatTime(minutes) {
    if (minutes == null || minutes === '') return '-';
    const totalSecs = Math.round(minutes * 60);
    const h = Math.floor(totalSecs / 3600);
    const m = Math.floor((totalSecs % 3600) / 60);
    const s = totalSecs % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
}

function formatDiff(minutes) {
    if (minutes == null || minutes === '') return '-';
    const sign = minutes >= 0 ? '+' : '-';
    return sign + formatTime(Math.abs(minutes));
}

function diffClass(diff) {
    if (diff > 0) return 'diff-positive';
    if (diff < 0) return 'diff-negative';
    return '';
}

// Get time for a leg from a source ("plan" or attempt id)
function getTime(source, legId) {
    if (source === 'plan') {
        const leg = calculatedData.find(l => l.id === legId);
        return leg ? leg.time : null;
    }
    const attempt = attemptsData.find(a => a.id === parseInt(source));
    if (!attempt) return null;
    const t = attempt.leg_times[legId];
    return t != null ? t : null;
}

function getLabel(source) {
    if (source === 'plan') return 'Plan';
    const attempt = attemptsData.find(a => a.id === parseInt(source));
    return attempt ? attempt.name : '?';
}

function updateComparison() {
    const compareA = document.getElementById('compare-a');
    const compareB = document.getElementById('compare-b');
    if (!compareA || !compareB) return;

    const aVal = compareA.value;
    const bVal = compareB.value;

    document.getElementById('col-a-header').textContent = getLabel(aVal);
    document.getElementById('col-b-header').textContent = getLabel(bVal);

    let totalA = 0, totalB = 0, cumA = 0, cumB = 0, bothHaveTotals = true;

    document.querySelectorAll('#attempts-table tbody tr').forEach(row => {
        const legId = parseInt(row.dataset.legId);
        const aTime = getTime(aVal, legId);
        const bTime = getTime(bVal, legId);

        row.querySelector('.col-a').textContent = formatTime(aTime);
        row.querySelector('.col-b').textContent = formatTime(bTime);

        const diffCell = row.querySelector('.col-diff');
        const pctCell = row.querySelector('.col-pct');
        const cumDiffCell = row.querySelector('.col-cum-diff');

        if (aTime != null && bTime != null) {
            const diff = aTime - bTime;
            diffCell.textContent = formatDiff(diff);
            diffCell.className = 'col-diff ' + diffClass(diff);

            if (bTime > 0) {
                const pct = (diff / bTime) * 100;
                pctCell.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(0) + '%';
                pctCell.className = 'col-pct ' + diffClass(diff);
            } else {
                pctCell.textContent = '-';
                pctCell.className = 'col-pct';
            }

            cumA += aTime;
            cumB += bTime;
            const cumDiff = cumA - cumB;
            cumDiffCell.textContent = formatDiff(cumDiff);
            cumDiffCell.className = 'col-cum-diff ' + diffClass(cumDiff);

            totalA += aTime;
            totalB += bTime;

            row.classList.remove('row-faster', 'row-slower');
            if (diff < 0) row.classList.add('row-faster');
            else if (diff > 0) row.classList.add('row-slower');
        } else {
            diffCell.textContent = '-';
            diffCell.className = 'col-diff';
            cumDiffCell.textContent = '-';
            cumDiffCell.className = 'col-cum-diff';
            pctCell.textContent = '-';
            pctCell.className = 'col-pct';
            row.classList.remove('row-faster', 'row-slower');
            bothHaveTotals = false;
        }
    });

    document.querySelector('.col-a-total strong').textContent = formatTime(totalA);
    document.querySelector('.col-b-total strong').textContent = formatTime(totalB);
    const diffTotal = document.querySelector('.col-diff-total strong');
    const pctTotal = document.querySelector('.col-pct-total strong');
    if (bothHaveTotals) {
        const d = totalA - totalB;
        diffTotal.textContent = formatDiff(d);
        diffTotal.parentElement.className = 'col-diff-total ' + diffClass(d);
        if (totalB > 0) {
            const pct = (d / totalB) * 100;
            pctTotal.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(0) + '%';
            pctTotal.parentElement.className = 'col-pct-total ' + diffClass(d);
        } else {
            pctTotal.textContent = '-';
            pctTotal.parentElement.className = 'col-pct-total';
        }
    } else {
        diffTotal.textContent = '-';
        diffTotal.parentElement.className = 'col-diff-total';
        pctTotal.textContent = '-';
        pctTotal.parentElement.className = 'col-pct-total';
    }
}

// Refresh calculatedData from server and update comparison table
function refreshCalculated() {
    const routeId = window.location.pathname.match(/\/bigruns\/(\d+)/);
    if (!routeId) return Promise.resolve();
    return fetch(`/walks/${routeId[1]}/calculated.json`)
        .then(r => r.json())
        .then(data => {
            calculatedData = data;
            updateComparison();
        });
}

// Submit form, reload page to get fresh server-rendered legs table, but keep scroll position
function submitAndReload(form) {
    const formData = new FormData(form);
    fetch(form.action, { method: 'POST', body: formData, redirect: 'manual' })
        .then(() => {
            const scrollY = window.scrollY;
            sessionStorage.setItem('scrollY', scrollY);
            window.location.reload();
        });
}

document.addEventListener('DOMContentLoaded', function () {
    const compareA = document.getElementById('compare-a');
    const compareB = document.getElementById('compare-b');

    if (compareA && compareB) {
        compareA.addEventListener('change', updateComparison);
        compareB.addEventListener('change', updateComparison);
        updateComparison();
    }

    // Intercept legs form — submit via fetch, reload to refresh server-rendered table
    const legsForm = document.querySelector('form[action*="/legs"]');
    if (legsForm) {
        legsForm.addEventListener('submit', function (e) {
            e.preventDefault();
            submitAndReload(this);
        });
    }

    // Intercept paces form
    const pacesForm = document.querySelector('form[action*="/paces"]');
    if (pacesForm) {
        pacesForm.addEventListener('submit', function (e) {
            e.preventDefault();
            submitAndReload(this);
        });
    }

    // Intercept settings form
    const settingsForm = document.querySelector('form[action*="/settings"]');
    if (settingsForm) {
        settingsForm.addEventListener('submit', function (e) {
            e.preventDefault();
            submitAndReload(this);
        });
    }

    // Restore scroll position after reload
    const savedScroll = sessionStorage.getItem('scrollY');
    if (savedScroll) {
        window.scrollTo(0, parseInt(savedScroll));
        sessionStorage.removeItem('scrollY');
    }
});

// Import attempt times from pasted text
function importAttemptTimes() {
    const text = document.getElementById('attempt-csv').value.trim();
    if (!text) return;

    const values = text.split('\n').map(l => l.trim()).filter(l => l);
    const inputs = document.querySelectorAll('#attempt-times-body input[type="number"]');

    values.forEach((val, i) => {
        if (i < inputs.length) {
            const num = parseFloat(val);
            if (!isNaN(num)) inputs[i].value = num;
        }
    });

    document.getElementById('attempt-csv').value = '';
}

// Pace tier management
function addPaceTier() {
    const tbody = document.getElementById('pace-body');
    const idx = tbody.querySelectorAll('tr').length;
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="number" step="1" name="up_to_${idx}" placeholder="∞"></td>
        <td><input type="number" step="0.1" name="flat_pace_${idx}" required></td>
        <td><input type="number" step="0.1" name="ascent_pace_${idx}" required></td>
        <td><input type="number" step="0.1" name="descent_pace_${idx}" required></td>
        <td><button type="button" class="btn btn-small btn-danger" onclick="removePaceTier(this)">×</button></td>
    `;
    tbody.appendChild(tr);
}

function removePaceTier(btn) {
    const tbody = document.getElementById('pace-body');
    if (tbody.querySelectorAll('tr').length > 1) {
        btn.closest('tr').remove();
        renumberPaceTiers();
    }
}

function renumberPaceTiers() {
    document.querySelectorAll('#pace-body tr').forEach((row, i) => {
        row.querySelectorAll('input').forEach(input => {
            input.name = input.name.replace(/_\d+$/, `_${i}`);
        });
    });
}
