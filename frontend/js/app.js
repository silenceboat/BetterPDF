/**
 * DeepRead AI - Main Application
 *
 * Coordinates the PDF viewer, AI chat panel, and page-linked notes.
 */

class DeepReadApp {
    constructor() {
        this.currentPanel = 'ai'; // 'ai' or 'notes' or 'settings'
        this.pdfViewer = null;
        this.aiPanel = null;
        this.notesPanel = null;
        this.settingsPanel = null;
        this.toastContainer = null;
        this.topToastContainer = null;
        this.isResizingPanels = false;
        this.leftPanelStorageKey = 'deepread_left_panel_width';
        this.pageNotes = new Map(); // page number -> note cards
        this.currentFilePath = '';
        this.recentFiles = [];
        this.sessionStateSaveTimer = null;
        this.notesSaveTimer = null;
        this.recentMenuOpen = false;
        this.recentMenuHideHandler = null;
        this.recentMenuToggleBtn = null;
        this.recentMenuEl = null;
        this.recentFilesRequestSeq = 0;
        this.isPdfFocusMode = false;

        this.init();
    }

    async init() {
        // Wait for DOM
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }

    setup() {
        this.createToastContainer();
        this.setupSidebar();
        this.setupHeader();
        this.setupPanelTabs();

        // Initialize components
        this.pdfViewer = new PDFViewer('pdf-panel-root');
        this.aiPanel = new AIChatPanel('panel-content');
        this.notesPanel = new NotesPanel('panel-content');
        this.settingsPanel = new SettingsPanel('panel-content');
        this.setupPageSync();
        this.setupStatePersistenceSync();
        this.setupResizableLayout();

        // Show initial panel
        this.switchPanel('ai');

        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();

        // Load app info
        this.loadAppInfo();
        this.refreshRecentFiles();

        console.log('DeepRead AI initialized');
    }

    createToastContainer() {
        this.toastContainer = document.createElement('div');
        this.toastContainer.className = 'toast-container';
        this.toastContainer.id = 'toast-container';
        document.body.appendChild(this.toastContainer);

        this.topToastContainer = document.createElement('div');
        this.topToastContainer.className = 'toast-container toast-container-top';
        this.topToastContainer.id = 'toast-container-top';
        document.body.appendChild(this.topToastContainer);
    }

    setupSidebar() {
        const panelButtons = document.querySelectorAll('.sidebar-btn[data-panel]');
        panelButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const panel = btn.dataset.panel;
                if (panel) {
                    this.switchPanel(panel);
                }
            });
        });

        document.querySelector('.sidebar-btn[data-action="toggle-pdf-focus"]')?.addEventListener('click', () => {
            this.togglePdfFocusMode();
        });
    }

    setupHeader() {
        document.getElementById('open-pdf-btn')?.addEventListener('click', () => this.openPdf());
        this.recentMenuToggleBtn = document.getElementById('open-pdf-menu-btn');
        this.recentMenuEl = document.getElementById('recent-files-menu');
        this.recentMenuToggleBtn?.addEventListener('click', (event) => {
            event.stopPropagation();
            this.toggleRecentFilesMenu();
        });

        // Save button
        document.getElementById('save-btn')?.addEventListener('click', () => {
            this.saveCurrentNote();
        });
    }

    setupPanelTabs() {
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const panel = tab.dataset.tab;
                if (panel) {
                    this.switchPanel(panel);
                }
            });
        });
    }

    setupPageSync() {
        window.addEventListener('deepread:page-changed', (event) => {
            const page = Number(event?.detail?.page);
            this.onPageChanged(page);
        });
    }

    setupStatePersistenceSync() {
        window.addEventListener('deepread:view-state-changed', () => {
            this.scheduleSaveSessionState();
        });
        window.addEventListener('deepread:page-changed', () => {
            this.scheduleSaveSessionState();
        });
    }

    setupResizableLayout() {
        const content = document.getElementById('main-content');
        const splitter = document.getElementById('panel-splitter');
        if (!content || !splitter) return;

        const minLeft = 460;
        const minRight = 340;

        const applyLeftWidth = (leftWidth) => {
            const total = content.clientWidth;
            const splitterWidth = splitter.offsetWidth || 10;
            const maxLeft = Math.max(minLeft, total - minRight - splitterWidth);
            const clamped = Math.max(minLeft, Math.min(leftWidth, maxLeft));
            document.documentElement.style.setProperty('--left-panel-width', `${clamped}px`);
            window.dispatchEvent(new Event('deepread:layout-resized'));
            return clamped;
        };

        const savedWidth = parseInt(localStorage.getItem(this.leftPanelStorageKey) || '', 10);
        if (Number.isFinite(savedWidth)) {
            applyLeftWidth(savedWidth);
        }

        const onPointerMove = (e) => {
            if (!this.isResizingPanels) return;
            const rect = content.getBoundingClientRect();
            const splitterWidth = splitter.offsetWidth || 10;
            const nextLeft = e.clientX - rect.left - splitterWidth / 2;
            applyLeftWidth(nextLeft);
        };

        const stopResize = () => {
            if (!this.isResizingPanels) return;
            this.isResizingPanels = false;
            document.body.classList.remove('is-resizing-panels');
            const current = getComputedStyle(document.documentElement)
                .getPropertyValue('--left-panel-width')
                .trim();
            localStorage.setItem(this.leftPanelStorageKey, current.replace('px', ''));
        };

        splitter.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            this.isResizingPanels = true;
            document.body.classList.add('is-resizing-panels');
            splitter.setPointerCapture(e.pointerId);
        });

        splitter.addEventListener('pointermove', onPointerMove);
        splitter.addEventListener('pointerup', stopResize);
        splitter.addEventListener('pointercancel', stopResize);
        splitter.addEventListener('dblclick', () => {
            document.documentElement.style.setProperty('--left-panel-width', '60%');
            localStorage.removeItem(this.leftPanelStorageKey);
            window.dispatchEvent(new Event('deepread:layout-resized'));
        });

        window.addEventListener('resize', () => {
            const value = getComputedStyle(document.documentElement)
                .getPropertyValue('--left-panel-width')
                .trim();
            if (!value.endsWith('px')) return;
            const px = parseFloat(value);
            if (!Number.isFinite(px)) return;
            applyLeftWidth(px);
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key.toLowerCase()) {
                    case 'o':
                        e.preventDefault();
                        this.openPdf();
                        break;
                    case 's':
                        e.preventDefault();
                        this.saveCurrentNote();
                        break;
                    case 'f':
                        e.preventDefault();
                        document.getElementById('search-input')?.focus();
                        break;
                }
            }

            if (e.key === 'Escape' && this.isPdfFocusMode) {
                e.preventDefault();
                this.togglePdfFocusMode(false);
            }
        });
    }

    async loadAppInfo() {
        try {
            const info = await API.getAppInfo();
            document.title = `${info.name} v${info.version}`;
        } catch (error) {
            console.error('Failed to load app info:', error);
        }
    }

    // ==================== Panel Management ====================

    switchPanel(panel) {
        if (panel !== 'ai' && panel !== 'notes' && panel !== 'settings') {
            return;
        }
        this.currentPanel = panel;

        // Update sidebar buttons
        document.querySelectorAll('.sidebar-btn[data-panel]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.panel === panel);
        });
        this.updateSidebarContext(panel);

        // Update panel tabs
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === panel);
        });

        // Show/hide panel content
        const content = document.getElementById('panel-content');
        if (content) {
            if (panel === 'ai') {
                this.aiPanel.render(content);
            } else if (panel === 'notes') {
                const currentPage = this.pdfViewer?.getCurrentPage() || 1;
                this.notesPanel.setActivePage(currentPage, { render: false, preserveActive: true });
                this.notesPanel.render(content);
            } else if (panel === 'settings') {
                this.settingsPanel.render(content);
            }
        }
    }

    updateSidebarContext(panel = this.currentPanel) {
        document.querySelectorAll('.sidebar-panel-btn').forEach((btn) => {
            const visible = btn.dataset.panel === panel;
            btn.classList.toggle('is-context-visible', visible);
            btn.setAttribute('aria-hidden', visible ? 'false' : 'true');
            btn.tabIndex = visible ? 0 : -1;
        });
    }

    togglePdfFocusMode(forceState = null) {
        const nextState = typeof forceState === 'boolean'
            ? forceState
            : !this.isPdfFocusMode;
        this.isPdfFocusMode = nextState;
        document.body.classList.toggle('pdf-focus-mode', nextState);
        const focusBtn = document.querySelector('.sidebar-btn[data-action="toggle-pdf-focus"]');
        if (focusBtn) {
            focusBtn.classList.toggle('active', nextState);
            focusBtn.setAttribute('aria-pressed', nextState ? 'true' : 'false');
        }
        window.dispatchEvent(new Event('deepread:layout-resized'));
    }

    // ==================== File Operations ====================

    async openPdf(filePath = '') {
        try {
            if (this.currentFilePath) {
                await this.flushPendingPersistence();
            }

            let targetPath = filePath;
            if (!targetPath) {
                const result = await API.selectPdfFile();
                if (result.cancelled) {
                    return;
                }
                if (!result.success || !result.file_path) {
                    this.showToast(result.error || 'Failed to open PDF', 'error');
                    return;
                }
                targetPath = result.file_path;
            }

            const openResult = await this.pdfViewer.loadDocument(targetPath);
            this.currentFilePath = openResult?.file_path || targetPath;
            this.hydratePageNotes(openResult?.page_notes || []);
            this.notesPanel?.setActivePage(this.pdfViewer?.getCurrentPage() || 1, {
                render: false,
                preserveActive: false
            });
            if (this.currentPanel === 'notes') {
                this.notesPanel?.render(document.getElementById('panel-content'));
            }

            this.pdfViewer.setOcrAvailable(openResult?.supports_ocr !== false);

            await this.refreshRecentFiles();
            this.hideRecentFilesMenu();
            this.showToast('Document opened successfully', 'success');
        } catch (error) {
            console.error('Failed to open PDF:', error);
            this.showToast('Failed to open PDF', 'error');
        }
    }

    async refreshRecentFiles() {
        const requestSeq = ++this.recentFilesRequestSeq;
        try {
            const result = await API.getRecentFiles(20);
            // Keep UI deterministic when multiple refreshes overlap.
            if (requestSeq !== this.recentFilesRequestSeq) {
                return;
            }
            if (result.success) {
                this.recentFiles = Array.isArray(result.files) ? result.files : [];
                this.renderRecentFilesMenu();
            } else {
                console.error('Failed to load recent files:', result.error || 'Unknown error');
            }
        } catch (error) {
            if (requestSeq !== this.recentFilesRequestSeq) {
                return;
            }
            console.error('Failed to load recent files:', error);
        }
    }

    toggleRecentFilesMenu() {
        if (this.recentMenuOpen) {
            this.hideRecentFilesMenu();
            return;
        }
        this.showRecentFilesMenu();
    }

    showRecentFilesMenu() {
        if (!this.recentMenuEl) return;
        this.renderRecentFilesMenu();
        this.recentMenuEl.hidden = false;
        this.recentMenuOpen = true;
        if (this.recentMenuToggleBtn) {
            this.recentMenuToggleBtn.setAttribute('aria-expanded', 'true');
        }
        document.querySelector('.open-pdf-group')?.classList.add('menu-open');
        this.recentMenuHideHandler = (event) => {
            if (!event.target.closest('.open-pdf-group')) {
                this.hideRecentFilesMenu();
            }
        };
        setTimeout(() => {
            document.addEventListener('click', this.recentMenuHideHandler);
        }, 0);
    }

    hideRecentFilesMenu() {
        if (!this.recentMenuEl) return;
        this.recentMenuEl.hidden = true;
        this.recentMenuOpen = false;
        if (this.recentMenuToggleBtn) {
            this.recentMenuToggleBtn.setAttribute('aria-expanded', 'false');
        }
        document.querySelector('.open-pdf-group')?.classList.remove('menu-open');
        if (this.recentMenuHideHandler) {
            document.removeEventListener('click', this.recentMenuHideHandler);
            this.recentMenuHideHandler = null;
        }
    }

    renderRecentFilesMenu() {
        if (!this.recentMenuEl) return;

        if (!this.recentFiles.length) {
            this.recentMenuEl.innerHTML = '<button class="recent-files-item empty" disabled>No recent files yet</button>';
            return;
        }

        this.recentMenuEl.innerHTML = this.recentFiles.map((item) => {
            const filePath = this.escapeHtml(item.file_path || '');
            const fileName = this.escapeHtml(item.file_name || 'Unknown file');
            const meta = this.escapeHtml(
                `${item.last_page ? `Page ${item.last_page}` : 'Page 1'} · ${this.formatRecentTime(item.last_opened_at)} · ${item.file_path || ''}`
            );
            return `
                <button class="recent-files-item" data-file-path="${filePath}" title="${filePath}">
                    <span class="recent-files-name">${fileName}</span>
                    <span class="recent-files-meta">${meta}</span>
                </button>
            `;
        }).join('');

        this.recentMenuEl.querySelectorAll('.recent-files-item[data-file-path]').forEach((itemEl) => {
            itemEl.addEventListener('click', async (event) => {
                event.preventDefault();
                const path = itemEl.dataset.filePath;
                this.hideRecentFilesMenu();
                await this.openPdf(path);
            });
        });
    }

    formatRecentTime(timestamp) {
        const date = new Date(timestamp || '');
        if (Number.isNaN(date.getTime())) return 'Unknown time';
        const now = new Date();
        const sameDay = date.toDateString() === now.toDateString();
        if (sameDay) {
            return `Today ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        }
        return date.toLocaleString([], {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    hydratePageNotes(notes) {
        this.pageNotes = new Map();
        for (const raw of (Array.isArray(notes) ? notes : [])) {
            const page = Number(raw?.page);
            const id = String(raw?.id || '').trim();
            const rectPdf = this.normalizeRect(raw?.rectPdf);
            if (!Number.isFinite(page) || page < 1 || !id || !rectPdf) {
                continue;
            }
            const note = {
                id,
                page,
                quote: String(raw?.quote || ''),
                note: String(raw?.note || ''),
                rectPdf,
                createdAt: raw?.createdAt || new Date().toISOString(),
                updatedAt: raw?.updatedAt || raw?.createdAt || new Date().toISOString()
            };
            const existing = this.pageNotes.get(page) || [];
            existing.push(note);
            this.pageNotes.set(page, existing);
        }

        this.pageNotes.forEach((notesForPage, page) => {
            const sorted = [...notesForPage].sort((a, b) => {
                return String(b.updatedAt || '').localeCompare(String(a.updatedAt || ''));
            });
            this.pageNotes.set(page, sorted);
        });
    }

    serializePageNotes() {
        const flattened = [];
        this.pageNotes.forEach((notesForPage, page) => {
            notesForPage.forEach((note) => {
                flattened.push({
                    id: note.id,
                    page,
                    quote: note.quote || '',
                    note: note.note || '',
                    rectPdf: this.normalizeRect(note.rectPdf) || note.rectPdf || {},
                    createdAt: note.createdAt || new Date().toISOString(),
                    updatedAt: note.updatedAt || note.createdAt || new Date().toISOString()
                });
            });
        });
        return flattened;
    }

    schedulePersistPageNotes() {
        if (!this.currentFilePath) return;
        const pathSnapshot = this.currentFilePath;
        const notesSnapshot = this.serializePageNotes();
        if (this.notesSaveTimer) {
            clearTimeout(this.notesSaveTimer);
        }
        this.notesSaveTimer = setTimeout(() => {
            this.notesSaveTimer = null;
            this.persistPageNotesForPath(pathSnapshot, notesSnapshot);
        }, 450);
    }

    async persistPageNotes(options = {}) {
        const { silent = true } = options;
        if (!this.currentFilePath) return { success: false, error: 'No active file path' };
        return this.persistPageNotesForPath(this.currentFilePath, this.serializePageNotes(), { silent });
    }

    async persistPageNotesForPath(filePath, notes, options = {}) {
        const { silent = true } = options;
        if (!filePath) return { success: false, error: 'No active file path' };
        try {
            const result = await API.savePageNotes(filePath, notes);
            if (!result.success && !silent) {
                this.showToast(result.error || 'Failed to save notes', 'error');
            }
            return result;
        } catch (error) {
            if (!silent) {
                this.showToast('Failed to save notes', 'error');
            }
            return { success: false, error: error.message };
        }
    }

    async persistNoteDeletion(noteId) {
        if (!this.currentFilePath || !noteId) return;
        try {
            await API.deletePageNote(this.currentFilePath, noteId);
        } catch (error) {
            console.error('Failed to delete note in storage:', error);
        }
    }

    scheduleSaveSessionState() {
        if (!this.currentFilePath) return;
        const pathSnapshot = this.currentFilePath;
        const stateSnapshot = this.pdfViewer?.getViewState();
        if (this.sessionStateSaveTimer) {
            clearTimeout(this.sessionStateSaveTimer);
        }
        this.sessionStateSaveTimer = setTimeout(() => {
            this.sessionStateSaveTimer = null;
            this.saveSessionState(pathSnapshot, stateSnapshot);
        }, 350);
    }

    async saveSessionState(filePath = this.currentFilePath, state = null) {
        if (!filePath || !this.pdfViewer) return;
        try {
            const payload = state || this.pdfViewer.getViewState();
            await API.saveSessionState(filePath, payload);
        } catch (error) {
            console.error('Failed to save session state:', error);
        }
    }

    async flushPendingPersistence() {
        const pathSnapshot = this.currentFilePath;
        if (!pathSnapshot) return;

        if (this.notesSaveTimer) {
            clearTimeout(this.notesSaveTimer);
            this.notesSaveTimer = null;
        }
        if (this.sessionStateSaveTimer) {
            clearTimeout(this.sessionStateSaveTimer);
            this.sessionStateSaveTimer = null;
        }

        const notesSnapshot = this.serializePageNotes();
        await this.persistPageNotesForPath(pathSnapshot, notesSnapshot, { silent: true });
        await this.saveSessionState(pathSnapshot, this.pdfViewer?.getViewState());
    }

    async saveCurrentNote() {
        if (this.currentPanel !== 'notes') {
            this.switchPanel('notes');
        }
        await this.notesPanel?.saveNote();
    }

    normalizeRect(rect) {
        if (!rect) return null;
        const x1 = Number(rect.x1);
        const y1 = Number(rect.y1);
        const x2 = Number(rect.x2);
        const y2 = Number(rect.y2);
        if (![x1, y1, x2, y2].every(Number.isFinite)) return null;

        return {
            x1: Math.min(x1, x2),
            y1: Math.min(y1, y2),
            x2: Math.max(x1, x2),
            y2: Math.max(y1, y2)
        };
    }

    createPageNoteId() {
        return `pn_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    }

    createNoteFromSelection(payload) {
        const page = Number(payload?.page);
        const selectedText = payload?.selectedText?.trim() || '';
        const rectPdf = this.normalizeRect(payload?.rectPdf);
        if (!Number.isFinite(page) || page < 1 || !selectedText || !rectPdf) {
            return;
        }

        const now = new Date().toISOString();
        const note = {
            id: this.createPageNoteId(),
            page,
            quote: selectedText,
            note: '',
            rectPdf,
            createdAt: payload?.createdAt || now,
            updatedAt: now
        };

        const pageNotes = this.pageNotes.get(page) || [];
        pageNotes.unshift(note);
        this.pageNotes.set(page, pageNotes);

        this.notesPanel.setActivePage(page, { render: false, preserveActive: false });
        this.switchPanel('notes');
        this.notesPanel.setActiveNote(note.id, { focusPdf: true });
        this.schedulePersistPageNotes();
        this.showToast(`Added note to page ${page}`, 'success', 1800);
    }

    startAskAiFromSelection(payload) {
        const page = Number(payload?.page);
        const selectedText = payload?.selectedText?.trim() || '';
        const rectPdf = this.normalizeRect(payload?.rectPdf);
        if (!Number.isFinite(page) || page < 1 || !selectedText || !rectPdf) {
            return;
        }

        this.switchPanel('ai');
        this.aiPanel?.setPendingSelectionContext({
            page,
            selectedText,
            rectPdf,
            createdAt: payload?.createdAt || new Date().toISOString()
        });
        this.showToast(
            `Selection from page ${page} is attached. Ask your question in AI Chat.`,
            'info',
            1800,
            { position: 'top-right' }
        );
    }

    onPageChanged(page) {
        if (!Number.isFinite(page) || page < 1) return;
        this.notesPanel?.setActivePage(page);
        this.pdfViewer?.clearNoteFocus();
    }

    focusPageNote(note) {
        if (!note) return;
        const currentPage = this.pdfViewer?.getCurrentPage();
        if (!currentPage || note.page !== currentPage) return;
        this.pdfViewer?.focusNoteRect(note.rectPdf);
    }

    getPageNotesForPage(page) {
        return this.pageNotes.get(page) || [];
    }

    getTotalPageNotes() {
        let total = 0;
        this.pageNotes.forEach((notes) => {
            total += notes.length;
        });
        return total;
    }

    escapeHtml(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ==================== Toast Notifications ====================

    showToast(message, type = 'info', duration = 3000, options = {}) {
        const position = options?.position === 'top-right' ? 'top-right' : 'bottom-right';
        const mountNode = position === 'top-right'
            ? (this.topToastContainer || this.toastContainer)
            : this.toastContainer;
        if (!mountNode) return null;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
            error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>',
            warning: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
            info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>'
        };

        toast.innerHTML = `
            <span style="display:flex;align-items:center;color:var(--${type === 'success' ? 'success' : type === 'error' ? 'error' : type === 'warning' ? 'warning' : 'info'})">${icons[type] || icons.info}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
        `;

        // Close button
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.remove();
        });

        mountNode.appendChild(toast);

        // Auto remove
        if (duration > 0) {
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }

        return toast;
    }
}

/**
 * AI Chat Panel
 */
class AIChatPanel {
    constructor(containerId) {
        this.containerId = containerId;
        this.messages = [];
        this.isProcessing = false;
        this.pendingSelectionContext = null;
    }

    render(container) {
        container.innerHTML = `
            <div class="ai-chat-head">
                <div class="ai-chat-head-copy">
                    <div class="ai-chat-eyebrow">Reading Copilot</div>
                    <div class="ai-chat-title">AI Chat</div>
                </div>
                <div class="ai-chat-head-actions">
                    <span class="ai-config-pill" id="ai-chat-config-pill">Checking provider...</span>
                    <button class="btn btn-secondary btn-sm ai-chat-settings-link" id="open-ai-settings-btn">Open Settings</button>
                </div>
            </div>
            <div class="quick-actions">
                <button class="quick-action" data-action="full_summary">Full Summary</button>
                <button class="quick-action" data-action="key_points">Key Points</button>
                <button class="quick-action" data-action="questions">Questions</button>
            </div>
            <div class="chat-container">
                <div class="chat-messages" id="chat-messages">
                    <div class="message ai">
                        Hello! I'm your AI reading assistant. Select text from the PDF to analyze it, or ask me anything about the document.
                    </div>
                </div>
                <div class="chat-input-area">
                    <div class="chat-selection-context" id="chat-selection-context" hidden>
                        <div class="chat-selection-context-head">
                            <span class="chat-selection-context-label" id="chat-selection-context-label">Selected excerpt</span>
                            <button type="button" class="chat-selection-context-clear" id="chat-selection-context-clear">Clear</button>
                        </div>
                        <div class="chat-selection-context-body" id="chat-selection-context-body"></div>
                    </div>
                    <div class="chat-input">
                        <textarea id="chat-input" placeholder="Ask about this document..."></textarea>
                        <button id="send-btn">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="m22 2-7 20-4-9-9-4 20-7z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `;

        this.bindEvents();
        this.syncPendingSelectionContext();
        this.refreshProviderStatus();
    }

    bindEvents() {
        document.getElementById('open-ai-settings-btn')?.addEventListener('click', () => {
            window.app?.switchPanel('settings');
        });

        // Quick actions
        document.querySelectorAll('.quick-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                this.handleQuickAction(action);
            });
        });

        // Send button
        document.getElementById('send-btn')?.addEventListener('click', () => {
            this.sendMessage();
        });
        document.getElementById('chat-selection-context-clear')?.addEventListener('click', () => {
            this.clearPendingSelectionContext({ focusInput: true });
        });

        // Input textarea
        const input = document.getElementById('chat-input');
        input?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize
        input?.addEventListener('input', () => {
            input.style.height = '44px';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        });
    }

    setProviderStatus(message, state = 'warning') {
        const statusEl = document.getElementById('ai-chat-config-pill');
        if (!statusEl) return;
        statusEl.textContent = message;
        statusEl.classList.remove('configured', 'warning', 'error');
        statusEl.classList.add(state);
    }

    getProviderLabel(provider) {
        const key = String(provider || '').toLowerCase();
        if (key === 'anthropic') return 'Anthropic';
        if (key === 'ollama') return 'Ollama';
        return 'OpenAI Compatible';
    }

    async refreshProviderStatus() {
        try {
            const result = await API.getAiSettings();
            if (!result.success) {
                this.setProviderStatus('Provider status unavailable', 'error');
                return;
            }

            const provider = String(result.settings?.provider || 'openai').toLowerCase();
            const providerLabel = this.getProviderLabel(provider);
            const hasKey = !!result.settings?.has_api_key;
            if (provider === 'ollama') {
                this.setProviderStatus(`${providerLabel} connected`, 'configured');
            } else if (hasKey) {
                this.setProviderStatus(`${providerLabel} ready`, 'configured');
            } else {
                this.setProviderStatus(`${providerLabel} key missing`, 'warning');
            }
        } catch (error) {
            this.setProviderStatus(error?.message || 'Provider status unavailable', 'error');
        }
    }

    async handleQuickAction(action) {
        const actionNames = {
            full_summary: 'Full Summary',
            key_points: 'Key Points',
            questions: 'Questions'
        };

        this.addUserMessage(`[${actionNames[action]}]`);
        await this.processAiQuickAction(action);
    }

    setPendingSelectionContext(payload) {
        const selectedText = payload?.selectedText?.trim() || '';
        if (!selectedText) return;

        const page = Number(payload?.page);
        this.pendingSelectionContext = {
            page: Number.isFinite(page) && page > 0 ? Math.floor(page) : null,
            selectedText
        };
        this.syncPendingSelectionContext();

        const input = document.getElementById('chat-input');
        input?.focus();
    }

    clearPendingSelectionContext(options = {}) {
        const { focusInput = false } = options;
        this.pendingSelectionContext = null;
        this.syncPendingSelectionContext();
        if (focusInput) {
            document.getElementById('chat-input')?.focus();
        }
    }

    syncPendingSelectionContext() {
        const card = document.getElementById('chat-selection-context');
        const label = document.getElementById('chat-selection-context-label');
        const body = document.getElementById('chat-selection-context-body');
        const input = document.getElementById('chat-input');
        if (!card || !label || !body || !input) return;

        const context = this.pendingSelectionContext;
        if (!context?.selectedText) {
            card.hidden = true;
            label.textContent = 'Selected excerpt';
            body.textContent = '';
            input.placeholder = 'Ask about this document...';
            return;
        }

        card.hidden = false;
        label.textContent = context.page ? `Selected excerpt · Page ${context.page}` : 'Selected excerpt';
        body.textContent = context.selectedText;
        input.placeholder = 'Ask about the selected excerpt...';
    }

    buildChatContext() {
        const context = this.pendingSelectionContext;
        if (!context?.selectedText) return '';
        const pageLabel = context.page ? `Page ${context.page}` : 'Page unknown';
        return `${pageLabel}\n<selected_text>\n${context.selectedText}\n</selected_text>`;
    }

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input?.value.trim();

        if (!message || this.isProcessing) return;

        const contextText = this.buildChatContext();
        const hasSelectionContext = !!contextText;
        this.addUserMessage(hasSelectionContext ? `[Selected excerpt] ${message}` : message);
        input.value = '';
        input.style.height = '44px';

        const success = await this.processAiChat(message, contextText);
        if (success && hasSelectionContext) {
            this.clearPendingSelectionContext();
        }
    }

    addUserMessage(text) {
        this.addMessage('user', text);
    }

    addAiMessage(text) {
        this.addMessage('ai', text);
    }

    addMessage(role, text) {
        const container = document.getElementById('chat-messages');
        if (!container) return;

        const message = document.createElement('div');
        message.className = `message ${role}`;

        if (role === 'ai') {
            // Render markdown-like formatting
            message.innerHTML = this.formatMessage(text);
        } else {
            message.textContent = text;
        }

        container.appendChild(message);
        container.scrollTop = container.scrollHeight;

        this.messages.push({ role, text });
    }

    formatMessage(text) {
        // Simple markdown formatting
        return text
            // Bold
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            // Code
            .replace(/`(.+?)`/g, '<code>$1</code>')
            // Links
            .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>')
            // Line breaks
            .replace(/\n/g, '<br>');
    }

    showTypingIndicator() {
        const container = document.getElementById('chat-messages');
        if (!container) return;

        const indicator = document.createElement('div');
        indicator.className = 'message ai typing-indicator';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = '<span></span><span></span><span></span>';

        container.appendChild(indicator);
        container.scrollTop = container.scrollHeight;
    }

    hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }

    async processAiChat(message, context = '') {
        if (this.isProcessing) return false;

        this.isProcessing = true;
        this.showTypingIndicator();

        try {
            const result = await API.aiChat(message, context);

            this.hideTypingIndicator();

            if (result.success) {
                this.addAiMessage(result.response);
                return true;
            } else {
                this.addAiMessage(`Error: ${result.error || 'Failed to get response'}`);
            }
        } catch (error) {
            this.hideTypingIndicator();
            this.addAiMessage(`Error: ${error.message}`);
        } finally {
            this.isProcessing = false;
        }
        return false;
    }

    async processAiAction(action, selectedText) {
        if (this.isProcessing) return;

        this.isProcessing = true;
        this.showTypingIndicator();

        try {
            const result = await API.aiAction(action, selectedText);

            this.hideTypingIndicator();

            if (result.success) {
                this.addAiMessage(result.response);
            } else {
                this.addAiMessage(`Error: ${result.error || 'Failed to process action'}`);
            }
        } catch (error) {
            this.hideTypingIndicator();
            this.addAiMessage(`Error: ${error.message}`);
        } finally {
            this.isProcessing = false;
        }
    }

    async processAiQuickAction(actionType) {
        if (this.isProcessing) return;

        this.isProcessing = true;
        this.showTypingIndicator();

        try {
            const result = await API.aiQuickAction(actionType);

            this.hideTypingIndicator();

            if (result.success) {
                this.addAiMessage(result.response);
            } else {
                this.addAiMessage(`Error: ${result.error || 'Failed to process action'}`);
            }
        } catch (error) {
            this.hideTypingIndicator();
            this.addAiMessage(`Error: ${error.message}`);
        } finally {
            this.isProcessing = false;
        }
    }
}

/**
 * Settings Panel
 */
class SettingsPanel {
    constructor(containerId) {
        this.containerId = containerId;
        this.providerSettings = {
            provider: 'openai',
            model: 'gpt-4o-mini',
            base_url: '',
            api_key: '',
            has_api_key: false
        };
        this.providerMeta = {
            openai: {
                label: 'OpenAI Compatible',
                model: 'gpt-4o-mini',
                endpointPlaceholder: 'https://api.openai.com/v1',
                endpointLabel: 'Base URL',
                keyLabel: 'API Key',
                keyPlaceholder: 'sk-...',
                hint: 'Use this for OpenAI and OpenAI-compatible services like OpenRouter, Azure proxy, or self-hosted gateways.',
            },
            anthropic: {
                label: 'Anthropic',
                model: 'claude-3-5-haiku-latest',
                endpointPlaceholder: 'https://api.anthropic.com',
                endpointLabel: 'API Origin',
                keyLabel: 'Anthropic API Key',
                keyPlaceholder: 'sk-ant-...',
                hint: 'Uses Anthropic Messages API. If API Origin is empty, the app uses https://api.anthropic.com.',
            },
            ollama: {
                label: 'Ollama',
                model: 'llama3.2',
                endpointPlaceholder: 'http://localhost:11434',
                endpointLabel: 'Ollama URL',
                keyLabel: 'Authorization (Optional)',
                keyPlaceholder: 'Bearer token (optional)',
                hint: 'Local inference mode. API key is optional and only used if your Ollama endpoint requires auth.',
            },
        };
    }

    render(container) {
        container.innerHTML = `
            <div class="settings-shell">
                <section class="settings-hero">
                    <div class="settings-eyebrow">Settings</div>
                    <h2 class="settings-title">AI Connection</h2>
                    <p class="settings-subtitle">Configure which provider handles chat and quick actions.</p>
                </section>

                <section class="settings-card">
                    <div class="settings-card-head">
                        <div>
                            <h3 class="settings-card-title">Provider Profile</h3>
                            <p class="settings-card-desc">These values are saved locally and applied immediately.</p>
                        </div>
                        <span class="settings-status-pill" id="settings-ai-status-pill">Loading...</span>
                    </div>

                    <div class="settings-fields">
                        <label class="settings-field">
                            <span class="settings-field-label">Provider</span>
                            <select id="settings-ai-provider">
                                <option value="openai">OpenAI Compatible</option>
                                <option value="anthropic">Anthropic</option>
                                <option value="ollama">Ollama</option>
                            </select>
                        </label>

                        <label class="settings-field">
                            <span class="settings-field-label">Model</span>
                            <input type="text" id="settings-ai-model" placeholder="gpt-4o-mini" spellcheck="false">
                        </label>

                        <label class="settings-field">
                            <span class="settings-field-label" id="settings-ai-base-url-label">Base URL</span>
                            <input type="url" id="settings-ai-base-url" placeholder="https://api.openai.com/v1" spellcheck="false">
                        </label>

                        <label class="settings-field">
                            <span class="settings-field-label" id="settings-ai-key-label">API Key</span>
                            <div class="settings-input-wrap">
                                <input type="password" id="settings-ai-api-key" placeholder="sk-..." spellcheck="false">
                                <button type="button" class="settings-input-toggle" id="settings-ai-toggle-key">Show</button>
                            </div>
                        </label>
                    </div>

                    <p class="settings-provider-hint" id="settings-provider-hint"></p>

                    <div class="settings-actions">
                        <button class="btn btn-primary" id="settings-ai-save-btn">Save Provider</button>
                        <button class="btn btn-secondary" id="settings-ai-reset-btn">Reset Suggested Values</button>
                    </div>
                    <div class="settings-feedback" id="settings-ai-feedback"></div>
                </section>

                <section class="settings-note">
                    <p>Security note: keep API keys private. This app stores settings locally in its internal database.</p>
                </section>
            </div>
        `;

        this.bindEvents();
        this.loadProviderSettings();
    }

    bindEvents() {
        document.getElementById('settings-ai-save-btn')?.addEventListener('click', () => {
            this.saveProviderSettings();
        });

        document.getElementById('settings-ai-reset-btn')?.addEventListener('click', () => {
            const provider = this.getSelectedProvider();
            const profile = this.getProviderProfile(provider);
            const modelInput = document.getElementById('settings-ai-model');
            const urlInput = document.getElementById('settings-ai-base-url');
            const keyInput = document.getElementById('settings-ai-api-key');
            if (modelInput) modelInput.value = profile.model;
            if (urlInput) urlInput.value = '';
            if (keyInput) keyInput.value = '';
            this.applyProviderProfile(provider);
            this.setStatus(`${profile.label}: draft`, 'warning');
            this.setFeedback('Suggested defaults applied. Save to activate.', 'neutral');
        });

        document.getElementById('settings-ai-toggle-key')?.addEventListener('click', () => {
            const keyInput = document.getElementById('settings-ai-api-key');
            const toggle = document.getElementById('settings-ai-toggle-key');
            if (!keyInput || !toggle) return;
            const toText = keyInput.type === 'password';
            keyInput.type = toText ? 'text' : 'password';
            toggle.textContent = toText ? 'Hide' : 'Show';
        });

        document.getElementById('settings-ai-provider')?.addEventListener('change', () => {
            const provider = this.getSelectedProvider();
            this.applyProviderProfile(provider, { forceModel: true });
        });

        const modelInput = document.getElementById('settings-ai-model');
        const urlInput = document.getElementById('settings-ai-base-url');
        const keyInput = document.getElementById('settings-ai-api-key');
        [modelInput, urlInput, keyInput].forEach((input) => {
            input?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.saveProviderSettings();
                }
            });
        });
    }

    getProviderProfile(provider) {
        return this.providerMeta[provider] || this.providerMeta.openai;
    }

    getSelectedProvider() {
        const providerSelect = document.getElementById('settings-ai-provider');
        return String(providerSelect?.value || 'openai').toLowerCase();
    }

    applyProviderProfile(provider, options = {}) {
        const { forceModel = false } = options;
        const profile = this.getProviderProfile(provider);
        const modelInput = document.getElementById('settings-ai-model');
        const baseUrlLabel = document.getElementById('settings-ai-base-url-label');
        const baseUrlInput = document.getElementById('settings-ai-base-url');
        const keyLabel = document.getElementById('settings-ai-key-label');
        const keyInput = document.getElementById('settings-ai-api-key');
        const hint = document.getElementById('settings-provider-hint');

        if (baseUrlLabel) baseUrlLabel.textContent = profile.endpointLabel;
        if (baseUrlInput) baseUrlInput.placeholder = profile.endpointPlaceholder;
        if (keyLabel) keyLabel.textContent = profile.keyLabel;
        if (keyInput) keyInput.placeholder = profile.keyPlaceholder;
        if (hint) hint.textContent = profile.hint;

        if (modelInput && (forceModel || !modelInput.value.trim())) {
            modelInput.value = profile.model;
        }
    }

    getProviderLabel(provider) {
        return this.getProviderProfile(provider).label;
    }

    setStatus(message, state = 'warning') {
        const status = document.getElementById('settings-ai-status-pill');
        if (!status) return;
        status.textContent = message || '';
        status.classList.remove('configured', 'warning', 'error');
        status.classList.add(state);
    }

    setFeedback(message = '', state = 'neutral') {
        const feedback = document.getElementById('settings-ai-feedback');
        if (!feedback) return;
        feedback.textContent = message;
        feedback.classList.remove('error', 'success', 'neutral');
        feedback.classList.add(state);
    }

    async loadProviderSettings() {
        try {
            const result = await API.getAiSettings();
            if (!result.success) {
                this.setStatus('Failed to load', 'error');
                this.setFeedback(result.error || 'Failed to load provider settings.', 'error');
                return;
            }

            this.providerSettings = {
                ...this.providerSettings,
                ...(result.settings || {})
            };

            const provider = String(this.providerSettings.provider || 'openai').toLowerCase();
            const profile = this.getProviderProfile(provider);
            const providerSelect = document.getElementById('settings-ai-provider');
            const modelInput = document.getElementById('settings-ai-model');
            const urlInput = document.getElementById('settings-ai-base-url');
            const keyInput = document.getElementById('settings-ai-api-key');
            if (providerSelect) providerSelect.value = provider;
            if (modelInput) modelInput.value = this.providerSettings.model || profile.model;
            if (urlInput) urlInput.value = this.providerSettings.base_url || '';
            if (keyInput) keyInput.value = this.providerSettings.api_key || '';
            this.applyProviderProfile(provider);

            const hasKey = !!this.providerSettings.has_api_key;
            if (provider === 'ollama' || hasKey) {
                this.setStatus(`${profile.label}: active`, 'configured');
                this.setFeedback(`${profile.label} is ready for chat requests.`, 'success');
            } else {
                this.setStatus(`${profile.label}: key required`, 'warning');
                this.setFeedback(`Add ${profile.keyLabel.toLowerCase()} to start using ${profile.label}.`, 'neutral');
            }
        } catch (error) {
            this.setStatus('Failed to load', 'error');
            this.setFeedback(error?.message || 'Failed to load provider settings.', 'error');
        }
    }

    async saveProviderSettings() {
        const provider = this.getSelectedProvider();
        const profile = this.getProviderProfile(provider);
        const modelInput = document.getElementById('settings-ai-model');
        const urlInput = document.getElementById('settings-ai-base-url');
        const keyInput = document.getElementById('settings-ai-api-key');
        const saveBtn = document.getElementById('settings-ai-save-btn');
        const resetBtn = document.getElementById('settings-ai-reset-btn');

        const payload = {
            provider,
            model: modelInput?.value?.trim() || profile.model,
            base_url: urlInput?.value?.trim() || '',
            api_key: keyInput?.value?.trim() || ''
        };

        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
        }
        if (resetBtn) {
            resetBtn.disabled = true;
        }

        try {
            const result = await API.saveAiSettings(payload);
            if (!result.success) {
                this.setStatus('Save failed', 'error');
                this.setFeedback(result.error || 'Failed to save provider settings.', 'error');
                return;
            }

            this.providerSettings = {
                ...this.providerSettings,
                ...(result.settings || payload)
            };

            const savedProvider = String(this.providerSettings.provider || provider).toLowerCase();
            const savedProfile = this.getProviderProfile(savedProvider);
            const hasKey = !!this.providerSettings.has_api_key;
            if (savedProvider === 'ollama' || hasKey) {
                this.setStatus(`${savedProfile.label}: active`, 'configured');
                this.setFeedback(`${savedProfile.label} settings saved.`, 'success');
            } else {
                this.setStatus(`${savedProfile.label}: key required`, 'warning');
                this.setFeedback(`Saved. Add ${savedProfile.keyLabel.toLowerCase()} to activate requests.`, 'neutral');
            }
            this.applyProviderProfile(savedProvider);
            window.app?.showToast(`${savedProfile.label} settings saved`, 'success', 1600);
        } catch (error) {
            this.setStatus('Save failed', 'error');
            this.setFeedback(error?.message || 'Failed to save provider settings.', 'error');
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Save Provider';
            }
            if (resetBtn) {
                resetBtn.disabled = false;
            }
        }
    }
}

/**
 * Notes Panel
 */
class NotesPanel {
    constructor(containerId) {
        this.containerId = containerId;
        this.activePage = 1;
        this.activeNoteId = '';
    }

    render(container) {
        const notes = this.getActivePageNotes();
        const noteCount = notes.length;
        const countLabel = `${noteCount} ${noteCount === 1 ? 'note' : 'notes'}`;

        container.innerHTML = `
            <div class="notes-container">
                <div class="page-notes-header">
                    <div class="page-notes-title-wrap">
                        <div class="page-notes-eyebrow">Page Workspace</div>
                        <h2 class="page-notes-title">Page ${this.activePage} Notes</h2>
                    </div>
                    <span class="page-notes-meta">${countLabel}</span>
                </div>
                <div class="page-notes-list" id="page-notes-list">
                    ${noteCount ? notes.map((note, index) => this.renderNoteCard(note, index)).join('') : this.renderEmptyState()}
                </div>
            </div>
        `;

        this.bindEvents();
    }

    bindEvents() {
        document.querySelectorAll('.page-note-card').forEach(card => {
            card.addEventListener('click', (event) => {
                if (event.target.closest('.page-note-delete')) return;
                this.setActiveNote(card.dataset.noteId, { focusPdf: true });
            });
        });

        document.querySelectorAll('.page-note-delete').forEach(btn => {
            btn.addEventListener('click', (event) => {
                event.stopPropagation();
                this.deleteNote(btn.dataset.noteId);
            });
        });

        document.querySelectorAll('.page-note-input').forEach(textarea => {
            const noteId = textarea.dataset.noteId;
            textarea.addEventListener('focus', () => {
                this.setActiveNote(noteId, { focusPdf: true });
            });
            textarea.addEventListener('input', (event) => {
                const updatedAt = this.handleNoteInput(noteId, event.target.value);
                const card = event.target.closest('.page-note-card');
                const timeEl = card?.querySelector('.page-note-time');
                if (timeEl && updatedAt) {
                    timeEl.textContent = `Updated ${this.formatTime(updatedAt)}`;
                }
            });
        });

        this.updateActiveCardStyles();
    }

    renderEmptyState() {
        return `
            <div class="page-note-empty">
                <div class="page-note-empty-title">No notes on this page yet</div>
                <div class="page-note-empty-hint">Drag on the PDF and choose "Take a Note" to create one.</div>
            </div>
        `;
    }

    renderNoteCard(note, index) {
        const quote = this.escapeHtml(this.getQuotePreview(note.quote));
        const noteText = this.escapeHtml(note.note || '');
        const isActive = this.activeNoteId === note.id ? ' active' : '';
        const label = `Excerpt ${String(index + 1).padStart(2, '0')}`;
        const updated = this.formatTime(note.updatedAt || note.createdAt);

        return `
            <article class="page-note-card${isActive}" data-note-id="${this.escapeHtml(note.id)}">
                <div class="page-note-card-head">
                    <span class="page-note-chip">${label}</span>
                    <button class="page-note-delete" data-note-id="${this.escapeHtml(note.id)}" title="Delete note" aria-label="Delete note">
                        ×
                    </button>
                </div>
                <blockquote class="page-note-quote">${quote}</blockquote>
                <label class="page-note-label" for="note-input-${this.escapeHtml(note.id)}">Your note</label>
                <textarea id="note-input-${this.escapeHtml(note.id)}" class="page-note-input" data-note-id="${this.escapeHtml(note.id)}" placeholder="Write your observation for this excerpt...">${noteText}</textarea>
                <div class="page-note-time">Updated ${updated}</div>
            </article>
        `;
    }

    setActivePage(page, options = {}) {
        const { render = true, preserveActive = true } = options;
        const nextPage = Number(page);
        if (!Number.isFinite(nextPage) || nextPage < 1) return;

        this.activePage = nextPage;
        const notes = this.getActivePageNotes();
        if (!preserveActive || !notes.some(note => note.id === this.activeNoteId)) {
            this.activeNoteId = notes[0]?.id || '';
        }

        if (render && window.app?.currentPanel === 'notes') {
            this.render(document.getElementById('panel-content'));
        }
    }

    setActiveNote(noteId, options = {}) {
        const { focusPdf = true } = options;
        if (!noteId) return;

        const note = this.findActivePageNote(noteId);
        if (!note) return;

        this.activeNoteId = noteId;
        this.updateActiveCardStyles();

        if (focusPdf) {
            window.app?.focusPageNote(note);
        }
    }

    updateActiveCardStyles() {
        document.querySelectorAll('.page-note-card').forEach(card => {
            card.classList.toggle('active', card.dataset.noteId === this.activeNoteId);
        });
    }

    getQuotePreview(text) {
        const condensed = String(text || '').replace(/\s+/g, ' ').trim();
        if (condensed.length <= 260) return condensed;
        return `${condensed.slice(0, 260)}...`;
    }

    findActivePageNote(noteId) {
        return this.getActivePageNotes().find(note => note.id === noteId);
    }

    getActivePageNotes() {
        return window.app?.getPageNotesForPage(this.activePage) || [];
    }

    handleNoteInput(noteId, text) {
        const note = this.findActivePageNote(noteId);
        if (!note) return '';
        const updatedAt = new Date().toISOString();
        note.note = text;
        note.updatedAt = updatedAt;
        window.app?.schedulePersistPageNotes();
        return updatedAt;
    }

    deleteNote(noteId) {
        const app = window.app;
        if (!app || !noteId) return;

        const notes = app.getPageNotesForPage(this.activePage);
        const nextNotes = notes.filter(note => note.id !== noteId);
        if (nextNotes.length) {
            app.pageNotes.set(this.activePage, nextNotes);
        } else {
            app.pageNotes.delete(this.activePage);
        }

        if (this.activeNoteId === noteId) {
            this.activeNoteId = nextNotes[0]?.id || '';
        }

        app.persistNoteDeletion(noteId);
        app.schedulePersistPageNotes();
        app.pdfViewer?.clearNoteFocus();
        if (app.currentPanel === 'notes') {
            this.render(document.getElementById('panel-content'));
        }
    }

    async saveNote() {
        const total = window.app?.getTotalPageNotes() || 0;
        if (!total) {
            window.app?.showToast('No page notes yet. Use "Take a Note" first.', 'warning');
            return;
        }
        const result = await window.app?.persistPageNotes({ silent: false });
        if (result?.success) {
            window.app?.showToast(`Saved ${total} notes locally.`, 'success');
        }
    }

    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    escapeHtml(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}

// Initialize app
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new DeepReadApp();
    window.app = app; // Expose for debugging
});
