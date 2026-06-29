// Repeatable date-range rows for a goal's "Active periods". Uses event
// delegation so it works for the add-goal form and every edit dropdown.
(function () {
    'use strict';

    function periodRow() {
        var row = document.createElement('div');
        row.className = 'period-row';
        row.innerHTML =
            '<input type="date" name="period_start">' +
            '<span>to</span>' +
            '<input type="date" name="period_end">' +
            '<button type="button" class="btn btn-small btn-danger remove-period" ' +
            'title="Remove range">×</button>';
        return row;
    }

    document.addEventListener('click', function (e) {
        var add = e.target.closest('.add-period');
        if (add) {
            e.preventDefault();
            var set = add.closest('.period-set');
            set.querySelector('.period-rows').appendChild(periodRow());
            return;
        }
        var remove = e.target.closest('.remove-period');
        if (remove) {
            e.preventDefault();
            remove.closest('.period-row').remove();
        }
    });
})();
