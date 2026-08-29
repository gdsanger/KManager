/*
 * sidebar.js — Modul-Sidebar der Base-Templates (Gebäude, Auftragsverwaltung,
 * Verwaltung).
 *
 * Enthält:
 *   - Mobile Off-Canvas-Sidebar (Toggle, Backdrop, ESC, Auto-Close beim
 *     Navigieren, Resize-Handling, aria-Pflege, Fokus-Steuerung)
 *   - Desktop-Collapse auf Icon-Breite inkl. Tooltips und Persistenz
 *     (Key: nav.sidebarCollapsed)
 *   - Persistenz der aufgeklappten Menügruppen über localStorage
 *     (Key: nav.expandedMenuGroupIds)
 *
 * Erwartete DOM-Elemente: #sidebarMenu, #sidebarToggle, #sidebarToggleIcon,
 * #mobileMenuToggle, #sidebarBackdrop. Fehlen sie, bleibt das Skript
 * wirkungslos.
 *
 * Einbindung am Ende des <body> via:
 *   <script src="{% static 'js/sidebar.js' %}" defer></script>
 * (nach dem Bootstrap-Bundle, da bootstrap.Collapse verwendet wird).
 *
 * Die Klasse `sidebar-collapsed` wird bereits vor dem ersten Paint durch das
 * Inline-Snippet in templates/includes/_sidebar_boot.html gesetzt (Anti-
 * Flicker); dieses Skript übernimmt danach nur noch den laufenden Betrieb.
 */
(function () {
    'use strict';

    const NAV_EXPANDED_MENU_GROUP_IDS_KEY = 'nav.expandedMenuGroupIds';
    const NAV_SIDEBAR_COLLAPSED_KEY = 'nav.sidebarCollapsed';
    const SIDEBAR_COLLAPSED_CLASS = 'sidebar-collapsed';
    const MOBILE_BREAKPOINT_PX = 768;
    const RESIZE_DEBOUNCE_MS = 250;
    const PROGRAMMATIC_GROUP_TIMEOUT_MS = 1000;

    /**
     * Menügruppen, die gerade programmatisch (durch das Ein-/Ausklappen der
     * Sidebar) umgeschaltet werden. Deren Collapse-Events dürfen den
     * gespeicherten Gruppen-Zustand nicht verändern.
     */
    const programmaticGroups = new Set();

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
     * @returns {boolean} true unterhalb des Desktop-Breakpoints
     */
    function isMobile() {
        return window.innerWidth < MOBILE_BREAKPOINT_PX;
    }

    /* ---------------------------------------------------------------------
     * localStorage-Helfer (defensiv: Private Mode, Quota, Policy)
     * ------------------------------------------------------------------ */

    /**
     * Prüft, ob localStorage nutzbar ist.
     * @returns {boolean}
     */
    function isLocalStorageAvailable() {
        try {
            const test = '__localStorage_test__';
            localStorage.setItem(test, test);
            localStorage.removeItem(test);
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Liest die gespeicherten Gruppen-IDs aus localStorage.
     * @returns {Array} IDs der aufgeklappten Gruppen, sonst leeres Array
     */
    function readExpandedGroupIds() {
        if (!isLocalStorageAvailable()) {
            return [];
        }

        try {
            const stored = localStorage.getItem(NAV_EXPANDED_MENU_GROUP_IDS_KEY);
            if (!stored) {
                return [];
            }
            const parsed = JSON.parse(stored);
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            console.warn('Failed to read expanded menu groups from localStorage:', e);
            return [];
        }
    }

    /**
     * Schreibt die Gruppen-IDs nach localStorage.
     * @param {Array} ids - Zu speichernde Gruppen-IDs
     */
    function writeExpandedGroupIds(ids) {
        if (!isLocalStorageAvailable()) {
            return;
        }

        try {
            if (ids.length === 0) {
                // Key bei leerer Liste entfernen (saubere Storage-Haltung)
                localStorage.removeItem(NAV_EXPANDED_MENU_GROUP_IDS_KEY);
            } else {
                localStorage.setItem(NAV_EXPANDED_MENU_GROUP_IDS_KEY, JSON.stringify(ids));
            }
        } catch (e) {
            console.warn('Failed to write expanded menu groups to localStorage:', e);
        }
    }

    /**
     * Liest den gespeicherten Collapse-Zustand der Sidebar.
     * @returns {boolean} true = eingeklappt; Fallback ausgeklappt
     */
    function readSidebarCollapsed() {
        if (!isLocalStorageAvailable()) {
            return false;
        }

        try {
            return localStorage.getItem(NAV_SIDEBAR_COLLAPSED_KEY) === '1';
        } catch (e) {
            console.warn('Failed to read sidebar state from localStorage:', e);
            return false;
        }
    }

    /**
     * Persistiert den Collapse-Zustand der Sidebar.
     * @param {boolean} collapsed
     */
    function writeSidebarCollapsed(collapsed) {
        if (!isLocalStorageAvailable()) {
            return;
        }

        try {
            localStorage.setItem(NAV_SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0');
        } catch (e) {
            console.warn('Failed to write sidebar state to localStorage:', e);
        }
    }

    /* ---------------------------------------------------------------------
     * Menügruppen
     * ------------------------------------------------------------------ */

    /**
     * @returns {Array<HTMLElement>} Alle Collapse-Gruppen der Sidebar
     */
    function getMenuGroups() {
        return Array.from(document.querySelectorAll('.sidebar .collapse'));
    }

    /**
     * Prüft, ob eine Menügruppe einen aktiven Navigationspunkt enthält.
     * @param {HTMLElement} menuGroup - Das Collapse-Element
     * @returns {boolean}
     */
    function hasActiveChild(menuGroup) {
        return menuGroup.querySelector('.nav-link.active') !== null;
    }

    /**
     * Ermittelt die aufzuklappenden Gruppen: gespeicherter Zustand vereinigt
     * mit allen Gruppen, die einen aktiven Menüpunkt enthalten.
     * @param {Array<HTMLElement>} menuGroups
     * @returns {Array} gültige Gruppen-IDs
     */
    function getGroupIdsToExpand(menuGroups) {
        const validIds = menuGroups.map(group => group.id).filter(id => id);
        const storedIds = readExpandedGroupIds().filter(id => validIds.includes(id));
        const activeIds = menuGroups
            .filter(group => group.id && hasActiveChild(group))
            .map(group => group.id);

        return [...new Set([...storedIds, ...activeIds])];
    }

    /**
     * Klappt eine Gruppe programmatisch auf/zu, ohne den gespeicherten
     * Gruppen-Zustand zu verändern.
     * @param {HTMLElement} menuGroup
     * @param {boolean} show
     */
    function toggleGroupSilently(menuGroup, show) {
        const isShown = menuGroup.classList.contains('show');
        if (isShown === show) {
            return; // kein Event zu erwarten - Markierung würde hängenbleiben
        }

        programmaticGroups.add(menuGroup);
        // Sicherheitsnetz, falls das Collapse-Event ausbleibt
        setTimeout(function () {
            programmaticGroups.delete(menuGroup);
        }, PROGRAMMATIC_GROUP_TIMEOUT_MS);

        const instance = bootstrap.Collapse.getOrCreateInstance(menuGroup, { toggle: false });
        if (show) {
            instance.show();
        } else {
            instance.hide();
        }
    }

    /**
     * Schließt alle offenen Menügruppen (beim Einklappen der Sidebar).
     */
    function collapseAllGroups() {
        getMenuGroups().forEach(function (menuGroup) {
            toggleGroupSilently(menuGroup, false);
        });
    }

    /**
     * Stellt den gespeicherten Gruppen-Zustand wieder her (beim Ausklappen der
     * Sidebar). Schreibt bewusst nicht nach localStorage.
     */
    function restoreExpandedGroups() {
        const menuGroups = getMenuGroups();
        const idsToExpand = getGroupIdsToExpand(menuGroups);

        menuGroups.forEach(function (menuGroup) {
            if (menuGroup.id && idsToExpand.includes(menuGroup.id)) {
                toggleGroupSilently(menuGroup, true);
            }
        });
    }

    /* ---------------------------------------------------------------------
     * Mobile Off-Canvas-Sidebar
     * ------------------------------------------------------------------ */

    /**
     * Mobile Off-Canvas-Sidebar inkl. ARIA- und Fokus-Handling.
     */
    function initMobileSidebar() {
        const sidebar = document.getElementById('sidebarMenu');
        const sidebarToggle = document.getElementById('sidebarToggle');
        const mobileMenuToggle = document.getElementById('mobileMenuToggle');
        const sidebarBackdrop = document.getElementById('sidebarBackdrop');

        /**
         * Setzt aria-hidden passend zur Viewport-Breite: auf Mobile startet die
         * Sidebar verborgen, auf Desktop ist sie immer sichtbar.
         */
        function initializeAriaHidden() {
            if (sidebar) {
                sidebar.setAttribute('aria-hidden', isMobile() ? 'true' : 'false');
            }
        }

        initializeAriaHidden();

        /**
         * Öffnet bzw. schließt die mobile Sidebar.
         * @param {boolean} show
         */
        function toggleMobileSidebar(show) {
            if (!sidebar || !sidebarBackdrop) return;

            if (show) {
                sidebar.classList.add('show');
                sidebar.setAttribute('aria-hidden', 'false');
                sidebarBackdrop.classList.add('show');
                document.body.style.overflow = 'hidden'; // Body-Scroll unterbinden

                if (mobileMenuToggle) {
                    mobileMenuToggle.setAttribute('aria-expanded', 'true');
                    mobileMenuToggle.setAttribute('aria-label', 'Menü schließen');
                }

                // Fokus auf den ersten Menüpunkt für Tastaturnavigation
                const firstLink = sidebar.querySelector('.nav-link');
                if (firstLink) {
                    firstLink.focus();
                }
            } else {
                sidebar.classList.remove('show');
                sidebar.setAttribute('aria-hidden', 'true');
                sidebarBackdrop.classList.remove('show');
                document.body.style.overflow = '';

                if (mobileMenuToggle) {
                    mobileMenuToggle.setAttribute('aria-expanded', 'false');
                    mobileMenuToggle.setAttribute('aria-label', 'Menü öffnen');

                    // Fokus zurück auf den Menü-Button
                    mobileMenuToggle.focus();
                }
            }
        }

        if (mobileMenuToggle) {
            mobileMenuToggle.addEventListener('click', function (e) {
                e.preventDefault();
                const isOpen = sidebar && sidebar.classList.contains('show');
                toggleMobileSidebar(!isOpen);
            });
        }

        // Schließen-Button in der Sidebar (nur mobil aktiv; auf Desktop
        // übernimmt initDesktopCollapse denselben Button)
        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', function (e) {
                e.preventDefault();
                if (isMobile()) {
                    toggleMobileSidebar(false);
                }
            });
        }

        // Klick auf das Backdrop schließt die Sidebar
        if (sidebarBackdrop) {
            sidebarBackdrop.addEventListener('click', function () {
                toggleMobileSidebar(false);
            });
        }

        // Auto-Close beim Navigieren über einen Menüpunkt (nur mobil)
        const navLinks = sidebar ? sidebar.querySelectorAll('.nav-link') : [];
        navLinks.forEach(function (link) {
            link.addEventListener('click', function () {
                if (isMobile()) {
                    toggleMobileSidebar(false);
                }
            });
        });

        // Resize: offenes Mobile-Menü beim Wechsel auf Desktop schließen
        let resizeTimer;
        window.addEventListener('resize', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function () {
                if (!isMobile() && sidebar && sidebar.classList.contains('show')) {
                    toggleMobileSidebar(false);
                }
                // aria-hidden immer am aktuellen Viewport ausrichten
                initializeAriaHidden();
            }, RESIZE_DEBOUNCE_MS);
        });

        // ESC schließt die mobile Sidebar
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && isMobile() && sidebar && sidebar.classList.contains('show')) {
                toggleMobileSidebar(false);
            }
        });
    }

    /* ---------------------------------------------------------------------
     * Desktop-Collapse (Icon-Breite)
     * ------------------------------------------------------------------ */

    /**
     * Ein-/Ausklappen der Sidebar ab 768px inkl. Tooltips und Persistenz.
     * Breite von Sidebar, Main und Footer folgt automatisch über die
     * CSS-Variable --sidebar-width (siehe site.css).
     */
    function initDesktopCollapse() {
        const sidebar = document.getElementById('sidebarMenu');
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (!sidebar || !sidebarToggle) return;

        const toggleIcon = document.getElementById('sidebarToggleIcon');
        const tooltips = new Map();

        function isCollapsed() {
            return document.body.classList.contains(SIDEBAR_COLLAPSED_CLASS);
        }

        /**
         * Hält Beschriftung, aria-Zustand und Icon des Buttons synchron.
         * @param {boolean} collapsed
         */
        function syncToggleButton(collapsed) {
            sidebarToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            sidebarToggle.setAttribute(
                'aria-label',
                collapsed ? 'Seitenleiste ausklappen' : 'Seitenleiste einklappen'
            );

            if (toggleIcon) {
                toggleIcon.classList.toggle('bi-list', !collapsed);
                toggleIcon.classList.toggle('bi-chevron-right', collapsed);
            }
        }

        /**
         * Blendet für jeden Icon-Link einen Tooltip mit dem Menütext ein,
         * damit die Navigation im eingeklappten Zustand bedienbar bleibt.
         */
        function enableTooltips() {
            sidebar.querySelectorAll('.nav-link').forEach(function (link) {
                if (tooltips.has(link)) return;

                const labelElement = link.querySelector('.sidebar-text');
                const label = (labelElement ? labelElement.textContent : link.textContent).trim();
                if (!label) return;

                tooltips.set(link, new bootstrap.Tooltip(link, {
                    title: label,
                    placement: 'right',
                    trigger: 'hover focus',
                    container: 'body'
                }));
            });
        }

        function disableTooltips() {
            tooltips.forEach(function (tooltip) {
                tooltip.dispose();
            });
            tooltips.clear();
        }

        /**
         * Wendet den Zustand auf das DOM an (ohne Persistenz).
         * @param {boolean} collapsed
         */
        function applyCollapsed(collapsed) {
            document.body.classList.toggle(SIDEBAR_COLLAPSED_CLASS, collapsed);
            syncToggleButton(collapsed);

            if (collapsed) {
                collapseAllGroups();
                enableTooltips();
            } else {
                disableTooltips();
                restoreExpandedGroups();
            }
        }

        /**
         * Zustand setzen und persistieren.
         * @param {boolean} collapsed
         */
        function setCollapsed(collapsed) {
            applyCollapsed(collapsed);
            writeSidebarCollapsed(collapsed);
        }

        // Ausgangszustand: Die Klasse hat das Inline-Snippet gesetzt, hier nur
        // Button, Tooltips und Menügruppen nachziehen. Auf Mobile gilt der
        // Collapse-Zustand nicht - dort ist der Button der Schließen-Button.
        if (isMobile()) {
            document.body.classList.remove(SIDEBAR_COLLAPSED_CLASS);
            syncToggleButton(false);
        } else if (isCollapsed()) {
            applyCollapsed(true);
        } else {
            syncToggleButton(false);
        }

        sidebarToggle.addEventListener('click', function (e) {
            e.preventDefault();
            if (isMobile()) {
                return; // mobil schließt initMobileSidebar das Off-Canvas-Menü
            }
            setCollapsed(!isCollapsed());
        });

        // Klick auf eine Menügruppe im eingeklappten Zustand: erst die Sidebar
        // aufklappen, dann die Gruppe öffnen (kein Flyout-Menü).
        sidebar.querySelectorAll('.nav-category[data-bs-toggle="collapse"]').forEach(function (category) {
            category.addEventListener('click', function (e) {
                if (isMobile() || !isCollapsed()) return;

                // Bootstrap-Handler (delegiert, Bubbling) unterbinden
                e.preventDefault();
                e.stopPropagation();

                const selector = category.getAttribute('data-bs-target') || category.getAttribute('href') || '';
                setCollapsed(false);

                const target = document.querySelector(selector);
                if (target) {
                    // Nicht "silent": das bewusste Öffnen soll persistiert werden
                    bootstrap.Collapse.getOrCreateInstance(target, { toggle: false }).show();
                }
            }, true);
        });

        // Resize: mobil darf der Collapse-Zustand das Off-Canvas nicht
        // blockieren; zurück auf Desktop gilt wieder der gespeicherte Zustand.
        let resizeTimer;
        window.addEventListener('resize', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function () {
                if (isMobile()) {
                    if (isCollapsed()) {
                        // Gespeicherten Zustand bewusst nicht überschreiben
                        document.body.classList.remove(SIDEBAR_COLLAPSED_CLASS);
                        disableTooltips();
                        syncToggleButton(false);
                    }
                } else {
                    const storedCollapsed = readSidebarCollapsed();
                    if (storedCollapsed !== isCollapsed()) {
                        applyCollapsed(storedCollapsed);
                    }
                }
            }, RESIZE_DEBOUNCE_MS);
        });
    }

    /* ---------------------------------------------------------------------
     * Persistenz der Menügruppen
     * ------------------------------------------------------------------ */

    /**
     * Persistenz der aufgeklappten Menügruppen über localStorage.
     */
    function initMenuGroupPersistence() {
        const menuGroups = getMenuGroups();
        const validMenuGroupIds = menuGroups.map(group => group.id).filter(id => id);

        if (validMenuGroupIds.length > 0) {
            const storedExpandedIds = readExpandedGroupIds();
            const validExpandedIds = getGroupIdsToExpand(menuGroups);

            // localStorage bereinigen, falls ungültige IDs enthalten waren
            const sanitizedStoredIds = storedExpandedIds.filter(id => validMenuGroupIds.includes(id));
            if (sanitizedStoredIds.length !== storedExpandedIds.length) {
                writeExpandedGroupIds(sanitizedStoredIds);
            }

            // Bei eingeklappter Sidebar bleiben alle Gruppen zu; der Zustand
            // wird beim Ausklappen aus localStorage wiederhergestellt.
            if (!document.body.classList.contains(SIDEBAR_COLLAPSED_CLASS)) {
                validExpandedIds.forEach(function (menuId) {
                    const menuElement = document.getElementById(menuId);
                    if (menuElement) {
                        // Bootstrap-Collapse-API zum Aufklappen nutzen
                        const bsCollapse = new bootstrap.Collapse(menuElement, {
                            toggle: false
                        });
                        bsCollapse.show();
                    }
                });
            }
        }

        // Zustandsänderungen persistieren
        menuGroups.forEach(function (menuGroup) {
            if (!menuGroup.id) return;

            menuGroup.addEventListener('shown.bs.collapse', function () {
                if (programmaticGroups.delete(menuGroup)) {
                    return; // Sidebar-Collapse, kein Nutzerwunsch
                }

                const currentExpanded = readExpandedGroupIds();
                if (!currentExpanded.includes(menuGroup.id)) {
                    currentExpanded.push(menuGroup.id);
                    writeExpandedGroupIds(currentExpanded);
                }
            });

            menuGroup.addEventListener('hide.bs.collapse', function (e) {
                // Gruppen mit aktivem Kind dürfen nicht zugeklappt werden -
                // außer die Sidebar selbst klappt gerade ein.
                if (hasActiveChild(menuGroup) && !programmaticGroups.has(menuGroup)) {
                    e.preventDefault();
                    return; // localStorage unverändert lassen
                }
            });

            menuGroup.addEventListener('hidden.bs.collapse', function () {
                if (programmaticGroups.delete(menuGroup)) {
                    return; // Sidebar-Collapse, gespeicherter Zustand bleibt
                }

                // Nach abgeschlossenem Zuklappen localStorage aktualisieren
                const currentExpanded = readExpandedGroupIds();
                const filtered = currentExpanded.filter(id => id !== menuGroup.id);
                writeExpandedGroupIds(filtered);
            });
        });
    }

    onReady(function () {
        initMobileSidebar();
        // Vor der Gruppen-Persistenz: bei eingeklappter Sidebar wird der
        // gespeicherte Gruppen-Zustand nicht angewendet.
        initDesktopCollapse();
        initMenuGroupPersistence();
    });
})();
