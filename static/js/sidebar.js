/*
 * sidebar.js — Modul-Sidebar der Base-Templates (Gebäude, Auftragsverwaltung,
 * Verwaltung).
 *
 * Enthält:
 *   - Mobile Off-Canvas-Sidebar (Toggle, Backdrop, ESC, Auto-Close beim
 *     Navigieren, Resize-Handling, aria-Pflege, Fokus-Steuerung)
 *   - Persistenz der aufgeklappten Menügruppen über localStorage
 *     (Key: nav.expandedMenuGroupIds)
 *
 * Erwartete DOM-Elemente: #sidebarMenu, #sidebarToggle, #mobileMenuToggle,
 * #sidebarBackdrop. Fehlen sie, bleibt das Skript wirkungslos.
 *
 * Einbindung am Ende des <body> via:
 *   <script src="{% static 'js/sidebar.js' %}" defer></script>
 * (nach dem Bootstrap-Bundle, da bootstrap.Collapse verwendet wird).
 */
(function () {
    'use strict';

    const NAV_EXPANDED_MENU_GROUP_IDS_KEY = 'nav.expandedMenuGroupIds';
    const MOBILE_BREAKPOINT_PX = 768;
    const RESIZE_DEBOUNCE_MS = 250;

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
     * Mobile Off-Canvas-Sidebar inkl. ARIA- und Fokus-Handling.
     */
    function initMobileSidebar() {
        const sidebar = document.getElementById('sidebarMenu');
        const sidebarToggle = document.getElementById('sidebarToggle');
        const mobileMenuToggle = document.getElementById('mobileMenuToggle');
        const sidebarBackdrop = document.getElementById('sidebarBackdrop');

        function isMobile() {
            return window.innerWidth < MOBILE_BREAKPOINT_PX;
        }

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

        // Schließen-Button in der Sidebar (nur mobil aktiv)
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

    /**
     * Persistenz der aufgeklappten Menügruppen über localStorage.
     */
    function initMenuGroupPersistence() {
        /**
         * Prüft, ob localStorage nutzbar ist (Private Mode, Quota, Policy).
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
         * Filtert gespeicherte IDs gegen die auf der Seite vorhandenen Gruppen.
         * @param {Array} storedIds - IDs aus localStorage
         * @param {Array} validIds - Gültige Menügruppen-IDs der aktuellen Seite
         * @returns {Array} Bereinigte Liste gültiger IDs
         */
        function sanitizeExpandedGroupIds(storedIds, validIds) {
            return storedIds.filter(id => validIds.includes(id));
        }

        const menuGroups = document.querySelectorAll('.sidebar .collapse');
        const validMenuGroupIds = Array.from(menuGroups).map(group => group.id).filter(id => id);

        /**
         * Prüft, ob eine Menügruppe einen aktiven Navigationspunkt enthält.
         * @param {HTMLElement} menuGroup - Das Collapse-Element
         * @returns {boolean}
         */
        function hasActiveChild(menuGroup) {
            return menuGroup.querySelector('.nav-link.active') !== null;
        }

        /**
         * Liefert die IDs aller Gruppen mit aktivem Kindelement.
         * @returns {Array}
         */
        function getGroupsWithActiveChildren() {
            const groupsWithActive = [];
            menuGroups.forEach(function (menuGroup) {
                if (menuGroup.id && hasActiveChild(menuGroup)) {
                    groupsWithActive.push(menuGroup.id);
                }
            });
            return groupsWithActive;
        }

        // Zustand aus localStorage wiederherstellen; Gruppen mit aktivem Kind
        // werden immer aufgeklappt.
        if (validMenuGroupIds.length > 0) {
            const storedExpandedIds = readExpandedGroupIds();
            const groupsWithActiveChildren = getGroupsWithActiveChildren();

            // Gespeicherte IDs mit aktiven Gruppen zusammenführen
            const combinedIds = [...new Set([...storedExpandedIds, ...groupsWithActiveChildren])];
            const validExpandedIds = sanitizeExpandedGroupIds(combinedIds, validMenuGroupIds);

            // localStorage bereinigen, falls ungültige IDs enthalten waren
            if (storedExpandedIds.length !== validExpandedIds.length) {
                writeExpandedGroupIds(validExpandedIds);
            }

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

        // Zustandsänderungen persistieren
        menuGroups.forEach(function (menuGroup) {
            if (!menuGroup.id) return;

            menuGroup.addEventListener('shown.bs.collapse', function () {
                const currentExpanded = readExpandedGroupIds();
                if (!currentExpanded.includes(menuGroup.id)) {
                    currentExpanded.push(menuGroup.id);
                    writeExpandedGroupIds(currentExpanded);
                }
            });

            menuGroup.addEventListener('hide.bs.collapse', function (e) {
                // Gruppen mit aktivem Kind dürfen nicht zugeklappt werden
                if (hasActiveChild(menuGroup)) {
                    e.preventDefault();
                    return; // localStorage unverändert lassen
                }
            });

            menuGroup.addEventListener('hidden.bs.collapse', function () {
                // Nach abgeschlossenem Zuklappen localStorage aktualisieren
                const currentExpanded = readExpandedGroupIds();
                const filtered = currentExpanded.filter(id => id !== menuGroup.id);
                writeExpandedGroupIds(filtered);
            });
        });
    }

    onReady(function () {
        initMobileSidebar();
        initMenuGroupPersistence();
    });
})();
