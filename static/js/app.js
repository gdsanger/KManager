/*
 * app.js — Globale Basis-Funktionalität für alle Base-Templates.
 *
 * Enthält:
 *   - getCookie()                Cookie-Auslesen (u. a. csrftoken)
 *   - htmx:configRequest-Hook    X-CSRFToken an jeden HTMX-Request
 *   - Bootstrap-Tooltip-Init
 *   - Upload-Formular-Ladeindikator (Spinner + Fallback-Timeout)
 *
 * Einbindung am Ende des <body> via:
 *   <script src="{% static 'js/app.js' %}" defer></script>
 * (nach dem Bootstrap-Bundle und nach HTMX).
 */
(function () {
    'use strict';

    // Konfiguration Upload-Indikator
    const UPLOAD_TIMEOUT_MS = 30000; // 30 Sekunden
    const UPLOAD_TEXT = 'Wird hochgeladen...';

    /**
     * Liest den Wert eines Cookies aus.
     * @param {string} name - Name des Cookies
     * @returns {string|null} Wert oder null, wenn nicht vorhanden
     */
    function getCookie(name) {
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (const cookie of cookies) {
                const trimmedCookie = cookie.trim();
                if (trimmedCookie.startsWith(name + '=')) {
                    return decodeURIComponent(trimmedCookie.substring(name.length + 1));
                }
            }
        }
        return null;
    }

    // Global verfügbar halten (wie bisher in base.html deklariert)
    window.getCookie = getCookie;

    /**
     * Führt einen Callback aus, sobald das DOM bereit ist.
     * @param {Function} callback
     */
    function onReady(callback) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', callback);
        } else {
            callback();
        }
    }

    /**
     * Konfiguriert HTMX so, dass jeder Request den CSRF-Token mitsendet.
     * Ersetzt per-Element `hx-headers`-Workarounds.
     */
    function initHtmxCsrf() {
        document.body.addEventListener('htmx:configRequest', (event) => {
            event.detail.headers['X-CSRFToken'] = getCookie('csrftoken');
        });
    }

    /**
     * Initialisiert alle Bootstrap-Tooltips auf der Seite.
     */
    function initTooltips() {
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }

    /**
     * Hängt an alle Upload-Formulare einen Ladeindikator: Submit-Button wird
     * deaktiviert und zeigt einen Spinner. Ein Fallback-Timeout gibt den Button
     * wieder frei, falls der Submit nicht abgeschlossen wird (z. B.
     * Validierungsfehler oder Netzwerkprobleme).
     */
    function initUploadIndicators() {
        const uploadForms = document.querySelectorAll('form[enctype="multipart/form-data"]');

        uploadForms.forEach(function (form) {
            form.addEventListener('submit', function () {
                const submitButton = form.querySelector('button[type="submit"]');

                if (submitButton && !submitButton.disabled) {
                    // Mehrfaches Absenden verhindern
                    submitButton.disabled = true;

                    // Ursprünglichen Button-Inhalt sichern
                    const originalContent = submitButton.innerHTML;

                    // Spinner über DOM-Methoden erzeugen
                    const spinner = document.createElement('span');
                    spinner.className = 'spinner-border spinner-border-sm me-2';
                    spinner.setAttribute('role', 'status');
                    spinner.setAttribute('aria-hidden', 'true');

                    // Button leeren und Spinner + Text setzen
                    submitButton.textContent = '';
                    submitButton.appendChild(spinner);
                    submitButton.appendChild(document.createTextNode(UPLOAD_TEXT));

                    // Fallback-Timeout: Button wieder freigeben
                    setTimeout(function () {
                        if (submitButton.disabled && document.body.contains(submitButton)) {
                            submitButton.disabled = false;
                            submitButton.innerHTML = originalContent;
                        }
                    }, UPLOAD_TIMEOUT_MS);
                }
            });
        });
    }

    onReady(function () {
        initHtmxCsrf();
        initTooltips();
        initUploadIndicators();
    });
})();
