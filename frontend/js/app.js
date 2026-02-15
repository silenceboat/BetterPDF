/**
 * DeepRead AI - Main Application
 *
 * Coordinates the PDF viewer, AI chat panel, and page-linked notes.
 */

class DeepReadApp {
    constructor() {
        this.currentPanel = 'ai'; // 'ai' or 'notes'
        this.pdfViewer = null;
        this.aiPanel = null;
        this.notesPanel = null;
        this.toastContainer = null;
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
        if (panel !== 'ai' && panel !== 'notes') {
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

            await this.refreshRecentFiles();
            this.hideRecentFilesMenu();
            this.showToast('PDF opened successfully', 'success');
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

    showToast(message, type = 'info', duration = 3000) {
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

        this.toastContainer.appendChild(toast);

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
        this.providerSettings = {
            provider: 'openai',
            model: 'gpt-4o-mini',
            base_url: '',
            api_key: ''
        };
    }

    render(container) {
        container.innerHTML = `
            <div class="ai-provider-settings" id="ai-provider-settings">
                <div class="ai-provider-head">
                    <div class="ai-provider-title">AI Provider</div>
                    <div class="ai-provider-subtitle">Use your own OpenAI-compatible URL and API Key.</div>
                </div>
                <div class="ai-provider-grid">
                    <label class="ai-provider-field">
                        <span>Provider URL</span>
                        <input type="url" id="ai-provider-base-url" placeholder="https://api.openai.com/v1">
                    </label>
                    <label class="ai-provider-field">
                        <span>API Key</span>
                        <input type="password" id="ai-provider-api-key" placeholder="sk-...">
                    </label>
                    <button class="btn btn-sm btn-primary ai-provider-save" id="ai-provider-save-btn">Save Provider</button>
                </div>
                <div class="ai-provider-feedback" id="ai-provider-feedback"></div>
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
        this.loadProviderSettings();
    }

    bindEvents() {
        document.getElementById('ai-provider-save-btn')?.addEventListener('click', () => {
            this.saveProviderSettings();
        });
        const providerUrlInput = document.getElementById('ai-provider-base-url');
        const providerKeyInput = document.getElementById('ai-provider-api-key');
        [providerUrlInput, providerKeyInput].forEach((input) => {
            input?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.saveProviderSettings();
                }
            });
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

    async loadProviderSettings() {
        const result = await API.getAiSettings();
        if (!result.success) {
            this.setProviderFeedback('Failed to load provider settings', true);
            return;
        }

        this.providerSettings = {
            ...this.providerSettings,
            ...(result.settings || {})
        };
        const providerUrlInput = document.getElementById('ai-provider-base-url');
        const providerKeyInput = document.getElementById('ai-provider-api-key');
        if (providerUrlInput) {
            providerUrlInput.value = this.providerSettings.base_url || '';
        }
        if (providerKeyInput) {
            providerKeyInput.value = this.providerSettings.api_key || '';
        }
        this.setProviderFeedback(this.providerSettings.has_api_key ? 'Provider is configured.' : '', false);
    }

    setProviderFeedback(message = '', isError = false) {
        const feedback = document.getElementById('ai-provider-feedback');
        if (!feedback) return;
        feedback.textContent = message || '';
        feedback.classList.toggle('error', !!(message && isError));
        feedback.classList.toggle('success', !!(message && !isError));
    }

    async saveProviderSettings() {
        const providerUrlInput = document.getElementById('ai-provider-base-url');
        const providerKeyInput = document.getElementById('ai-provider-api-key');
        const saveBtn = document.getElementById('ai-provider-save-btn');

        const payload = {
            provider: 'openai',
            base_url: providerUrlInput?.value?.trim() || '',
            api_key: providerKeyInput?.value?.trim() || '',
            model: this.providerSettings?.model || 'gpt-4o-mini'
        };

        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
        }

        try {
            const result = await API.saveAiSettings(payload);
            if (!result.success) {
                this.setProviderFeedback(result.error || 'Failed to save provider settings', true);
                return;
            }
            this.providerSettings = {
                ...this.providerSettings,
                ...(result.settings || payload)
            };
            this.setProviderFeedback('Provider settings saved. AI now uses your URL and API Key.', false);
        } catch (error) {
            this.setProviderFeedback(error?.message || 'Failed to save provider settings', true);
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Save Provider';
            }
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

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input?.value.trim();

        if (!message || this.isProcessing) return;

        this.addUserMessage(message);
        input.value = '';
        input.style.height = '44px';

        await this.processAiChat(message);
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

    async processAiChat(message) {
        if (this.isProcessing) return;

        this.isProcessing = true;
        this.showTypingIndicator();

        try {
            const result = await API.aiChat(message);

            this.hideTypingIndicator();

            if (result.success) {
                this.addAiMessage(result.response);
            } else {
                this.addAiMessage(`Error: ${result.error || 'Failed to get response'}`);
            }
        } catch (error) {
            this.hideTypingIndicator();
            this.addAiMessage(`Error: ${error.message}`);
        } finally {
            this.isProcessing = false;
        }
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
