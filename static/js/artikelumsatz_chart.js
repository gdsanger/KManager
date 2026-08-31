/*
 * Auswertung Artikelumsatz: Balkendiagramm des Monatsverlaufs je Artikel.
 *
 * Der Monatsverlauf wird beim Aufklappen einer Ranglistenzeile per HTMX
 * nachgeladen. Das Diagramm kann deshalb nicht beim Laden der Seite gezeichnet
 * werden, sondern erst, wenn der Ausschnitt im DOM steht – dafür hört dieses
 * Skript auf `htmx:afterSwap`.
 *
 * Die Werte kommen über das data-Attribut des Canvas aus dem Template, damit
 * hier kein Server-Wert in JavaScript-Code interpoliert wird. Verwendet
 * dieselbe Chart.js-Version wie das Finanzen-Dashboard und die
 * Partnerauswertung.
 */
(function () {
    'use strict';

    // Auf den dunklen Untergrund (--bg-card #1e293b) abgestimmte Farben,
    // identisch zur Partnerauswertung.
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

    function renderChart(canvas) {
        // Ein Ausschnitt wird nur einmal geladen; die Bremse schützt trotzdem
        // davor, dasselbe Canvas doppelt zu bespielen.
        if (canvas.dataset.chartRendered === 'true' || typeof Chart === 'undefined') {
            return;
        }

        let data;
        try {
            data = JSON.parse(canvas.dataset.chart);
        } catch (error) {
            return;
        }
        canvas.dataset.chartRendered = 'true';

        new Chart(canvas, {
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
    }

    function renderIn(root) {
        if (!root || typeof root.querySelectorAll !== 'function') {
            return;
        }
        root.querySelectorAll('canvas.artikelumsatz-chart').forEach(renderChart);
    }

    document.addEventListener('htmx:afterSwap', function (event) {
        renderIn(event.target);
    });
})();
