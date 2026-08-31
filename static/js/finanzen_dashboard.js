/*
 * Finanzen-Dashboard: Liniendiagramm Einnahmen/Ausgaben im Jahresverlauf.
 *
 * Die Daten kommen über ein <script type="application/json">-Element aus dem
 * Template (json_script), damit hier kein Server-Wert in JavaScript-Code
 * interpoliert wird.
 *
 * Die beiden Linien sind neben der Farbe über Linienform und Punktmarker
 * unterscheidbar (Einnahmen: durchgezogen, runde Punkte; Ausgaben: gestrichelt,
 * dreieckige Punkte), damit sie auch ohne Farbwahrnehmung lesbar bleiben.
 */
(function () {
    'use strict';

    const dataElement = document.getElementById('finance-chart-data');
    const canvas = document.getElementById('finance-year-chart');
    if (!dataElement || !canvas || typeof Chart === 'undefined') {
        return;
    }

    const data = JSON.parse(dataElement.textContent);

    // Auf den dunklen Untergrund (--bg-card #1e293b) abgestimmte Serienfarben.
    const INCOME_COLOR = '#3987e5';
    const EXPENSE_COLOR = '#d95926';
    const TEXT_COLOR = '#cbd5e1';
    const GRID_COLOR = 'rgba(203, 213, 225, 0.15)';

    const currency = new Intl.NumberFormat('de-DE', {
        style: 'currency',
        currency: 'EUR',
    });
    const axisCurrency = new Intl.NumberFormat('de-DE', {
        style: 'currency',
        currency: 'EUR',
        maximumFractionDigits: 0,
    });

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Einnahmen',
                    data: data.income,
                    borderColor: INCOME_COLOR,
                    backgroundColor: INCOME_COLOR,
                    borderWidth: 2,
                    pointStyle: 'circle',
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.2,
                },
                {
                    label: 'Ausgaben',
                    data: data.expenses,
                    borderColor: EXPENSE_COLOR,
                    backgroundColor: EXPENSE_COLOR,
                    borderWidth: 2,
                    borderDash: [6, 4],
                    pointStyle: 'triangle',
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    tension: 0.2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                // Beide Werte eines Monats gemeinsam im Tooltip zeigen.
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: {
                        color: TEXT_COLOR,
                        usePointStyle: true,
                    },
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return context.dataset.label + ': ' + currency.format(context.parsed.y);
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: TEXT_COLOR },
                    grid: { color: GRID_COLOR },
                },
                y: {
                    ticks: {
                        color: TEXT_COLOR,
                        callback: function (value) {
                            return axisCurrency.format(value);
                        },
                    },
                    grid: { color: GRID_COLOR },
                },
            },
        },
    });
})();
