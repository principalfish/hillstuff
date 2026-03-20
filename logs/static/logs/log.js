(function () {
    'use strict';

    var typeSelect = document.getElementById('hill-type-select');
    var nameSelect = document.getElementById('hill-name-select');
    var addBtn = document.getElementById('add-hill-btn');
    var listDiv = document.getElementById('linked-hills-list');
    var munrosInput = document.getElementById('munros_count');
    var corbettsInput = document.getElementById('corbetts_count');
    var wainwrightsInput = document.getElementById('wainwrights_count');

    if (!typeSelect) return;

    var linkedHills = (typeof INITIAL_HILLS !== 'undefined') ? INITIAL_HILLS.slice() : [];

    // Render any pre-existing hills (edit form)
    if (linkedHills.length) render();

    typeSelect.addEventListener('change', function () {
        var hillType = typeSelect.value;
        nameSelect.innerHTML = '<option value="">Loading...</option>';
        nameSelect.disabled = true;
        addBtn.disabled = true;

        if (!hillType) {
            nameSelect.innerHTML = '<option value="">— choose hill —</option>';
            return;
        }

        fetch('/logs/api/hills/' + hillType)
            .then(function (r) { return r.json(); })
            .then(function (hills) {
                nameSelect.innerHTML = '<option value="">— choose hill —</option>';
                hills.forEach(function (h) {
                    var opt = document.createElement('option');
                    opt.value = h.id;
                    opt.dataset.name = h.name;
                    opt.textContent = h.name + ' (' + h.height_m + 'm, ' + h.region + ')';
                    nameSelect.appendChild(opt);
                });
                nameSelect.disabled = false;
                // Make the name select searchable by size
                nameSelect.size = 1;
            })
            .catch(function () {
                nameSelect.innerHTML = '<option value="">Error loading</option>';
            });
    });

    nameSelect.addEventListener('change', function () {
        addBtn.disabled = !nameSelect.value;
    });

    addBtn.addEventListener('click', function () {
        var id = parseInt(nameSelect.value, 10);
        var selected = nameSelect.options[nameSelect.selectedIndex];
        var name = selected.dataset.name || selected.textContent;
        var type = typeSelect.value;
        if (!id) return;
        if (linkedHills.some(function (h) { return h.id === id; })) return;
        linkedHills.push({ id: id, name: name, type: type });
        render();
    });

    function render() {
        listDiv.innerHTML = '';
        linkedHills.forEach(function (h, i) {
            var row = document.createElement('div');
            row.style.cssText = 'display:flex;gap:0.5rem;align-items:center;margin-bottom:0.25rem';
            row.innerHTML =
                '<span>' + h.name + ' <em>(' + h.type + ')</em></span>' +
                '<button type="button" class="btn btn-small" data-idx="' + i + '">&times;</button>' +
                '<input type="hidden" name="hill_id_' + i + '" value="' + h.id + '">';
            listDiv.appendChild(row);
        });

        listDiv.querySelectorAll('button[data-idx]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                linkedHills.splice(parseInt(btn.dataset.idx, 10), 1);
                render();
                updateCounts();
            });
        });

        updateCounts();
    }

    function updateCounts() {
        var munros = 0, corbetts = 0, wainwrights = 0;
        linkedHills.forEach(function (h) {
            if (h.type === 'munro') munros++;
            else if (h.type === 'corbett') corbetts++;
            else if (h.type === 'wainwright') wainwrights++;
        });
        if (munrosInput) munrosInput.value = munros;
        if (corbettsInput) corbettsInput.value = corbetts;
        if (wainwrightsInput) wainwrightsInput.value = wainwrights;

        var hillsTextInput = document.getElementById('hills_text');
        if (hillsTextInput) {
            hillsTextInput.value = linkedHills.map(function (h) { return h.name; }).join(', ');
        }
    }
}());

(function () {
    'use strict';

    var table = document.getElementById('log-table');
    var filterInput = document.getElementById('log-filter');
    if (!table) return;

    // --- Sort ---
    var sortCol = -1;
    var sortDir = 1; // 1 = asc, -1 = desc

    function numOrStr(s) {
        var n = parseFloat(s);
        return isNaN(n) ? s.toLowerCase() : n;
    }

    // Returns a sort key: raw string when data-sort is present (e.g. ISO date),
    // otherwise numeric or lowercased string.
    function cellSortKey(row, col) {
        var cell = row.cells[col];
        if (!cell) return '';
        if (cell.dataset.sort !== undefined) return cell.dataset.sort;
        return numOrStr(cell.textContent.trim());
    }

    table.querySelectorAll('th.sortable').forEach(function (th) {
        th.style.cursor = 'pointer';
        th.addEventListener('click', function () {
            var col = parseInt(th.dataset.col, 10);
            if (sortCol === col) {
                sortDir = -sortDir;
            } else {
                sortCol = col;
                sortDir = 1;
            }
            table.querySelectorAll('th.sortable').forEach(function (h) {
                h.textContent = h.textContent.replace(/ [▲▼]$/, '');
            });
            th.textContent = th.textContent + (sortDir === 1 ? ' ▲' : ' ▼');

            var tbody = table.tBodies[0];
            var rows = Array.prototype.slice.call(tbody.rows);
            rows.sort(function (a, b) {
                var av = cellSortKey(a, col);
                var bv = cellSortKey(b, col);
                if (av < bv) return -sortDir;
                if (av > bv) return sortDir;
                return 0;
            });
            rows.forEach(function (r) { tbody.appendChild(r); });
            applyFilter();
        });
    });

    // --- Filter ---
    // Columns to search: With(4), Region(5), Hills(6), Notes(11)
    var FILTER_COLS = [4, 5, 6, 11];

    function applyFilter() {
        if (!filterInput) return;
        var q = filterInput.value.toLowerCase().trim();
        var tbody = table.tBodies[0];
        Array.prototype.forEach.call(tbody.rows, function (row) {
            if (!q) {
                row.style.display = '';
                return;
            }
            var match = FILTER_COLS.some(function (col) {
                var cell = row.cells[col];
                return cell ? cell.textContent.toLowerCase().indexOf(q) !== -1 : false;
            });
            row.style.display = match ? '' : 'none';
        });
    }

    if (filterInput) {
        filterInput.addEventListener('input', applyFilter);
    }
}());
