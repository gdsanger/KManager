/*
 * Balkendiagramm der Partnerauswertung (Umsatz beim Kunden, Einkauf beim
 * Lieferanten) über zwölf rollierende Monate.
 *
 * Die Daten kommen über ein <script type="application/json">-Element aus dem
 * Template (json_script), damit hier kein Server-Wert in JavaScript-Code
 * interpoliert wird. Verwendet dieselbe Chart.js-Version wie das
 * Finanzen-Dashboard.
 */
(function () {
    'use strict';

    const dataElement = document.getElementById('partner-stats-data');
    const canvas = document.getElementById('partner-stats-chart');
    if (!dataElement || !canvas || typeof Chart === 'undefined') {
        return;
    }

    const data = JSON.parse(dataElement.textContent);

    // Auf den dunklen Untergrund (--bg-card #1e293b) abgestimmte Farben.
    const BAR_COLOR = '#3987e5';
    // Negative Monatswerte (Gutschriften über dem Monatsumsatz) heben sich
    // zusätzlich zum Vorzeichen farblich ab.
    const NEGATIVE_COLOR = '#d95926';
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

    const chart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: data.series,
                    data: data.values,
                    backgroundColor: data.values.map(function (value) {
                        return value < 0 ? NEGATIVE_COLOR : BAR_COLOR;
                    }),
                    borderWidth: 0,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
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
                    // Nulllinie erzwingen, damit negative Monatswerte nach
                    // unten gezeichnet und nicht abgeschnitten werden.
                    beginAtZero: true,
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

    // Der Tab ist beim Laden meist ausgeblendet – dort misst Chart.js eine
    // Größe von 0. Beim Einblenden eines Tabs neu vermessen, sonst bleibt das
    // Diagramm winzig oder unsichtbar.
    document.querySelectorAll('[data-bs-toggle="tab"]').forEach(function (button) {
        button.addEventListener('shown.bs.tab', function () {
            chart.resize();
        });
    });
})();
