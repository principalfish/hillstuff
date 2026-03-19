document.addEventListener('DOMContentLoaded', function() {
    var table = document.getElementById('hills-table');
    if (!table) return;

    var headers = table.querySelectorAll('th[data-sort]');
    var tbody = table.querySelector('tbody');

    // Multi-sort: array of {key, type, ascending}
    var sortStack = [];

    headers.forEach(function(th) {
        th.style.cursor = 'pointer';
        th.addEventListener('click', function(e) {
            var key = th.dataset.sort;
            var type = th.dataset.type || 'string';

            if (e.shiftKey) {
                // Shift+click: add to / toggle in sort stack
                var idx = sortStack.findIndex(function(s) { return s.key === key; });
                if (idx >= 0) {
                    sortStack[idx].ascending = !sortStack[idx].ascending;
                } else {
                    sortStack.push({ key: key, type: type, ascending: type === 'string' });
                }
            } else {
                // Plain click: single sort (toggle if same column)
                var existing = sortStack.length === 1 && sortStack[0].key === key;
                if (existing) {
                    sortStack[0].ascending = !sortStack[0].ascending;
                } else {
                    sortStack = [{ key: key, type: type, ascending: type === 'string' }];
                }
            }

            updateHeaderIndicators();
            sortRows();
        });
    });

    function updateHeaderIndicators() {
        headers.forEach(function(h) {
            h.classList.remove('sort-asc', 'sort-desc');
            var badge = h.querySelector('.sort-badge');
            if (badge) badge.remove();
        });
        sortStack.forEach(function(s, i) {
            var th = table.querySelector('th[data-sort="' + s.key + '"]');
            th.classList.add(s.ascending ? 'sort-asc' : 'sort-desc');
            if (sortStack.length > 1) {
                var badge = document.createElement('span');
                badge.className = 'sort-badge';
                badge.textContent = ' ' + (i + 1);
                th.appendChild(badge);
            }
        });
    }

    function sortRows() {
        var rows = Array.from(tbody.querySelectorAll('tr'));
        rows.sort(function(a, b) {
            for (var i = 0; i < sortStack.length; i++) {
                var s = sortStack[i];
                var aVal = a.querySelector('td[data-' + s.key + ']').dataset[s.key];
                var bVal = b.querySelector('td[data-' + s.key + ']').dataset[s.key];
                var cmp;
                if (s.type === 'number') {
                    cmp = (parseFloat(aVal) || 0) - (parseFloat(bVal) || 0);
                } else {
                    cmp = aVal.localeCompare(bVal);
                }
                if (cmp !== 0) return s.ascending ? cmp : -cmp;
            }
            return 0;
        });
        rows.forEach(function(row) { tbody.appendChild(row); });
    }

    // --- Filtering ---
    var filterInput = document.getElementById('hills-filter');
    if (!filterInput) return;

    filterInput.addEventListener('input', function() {
        var term = filterInput.value.toLowerCase();
        var rows = tbody.querySelectorAll('tr');
        rows.forEach(function(row) {
            var text = row.textContent.toLowerCase();
            row.style.display = text.indexOf(term) >= 0 ? '' : 'none';
        });
    });
});
