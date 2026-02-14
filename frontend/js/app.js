/**
 * DeepRead AI - Main Application
 *
 * Coordinates the PDF viewer, AI chat panel, and note editor.
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

        // Initialize components
        this.pdfViewer = new PDFViewer('pdf-panel-root');
        this.aiPanel = new AIChatPanel('panel-content');
        this.notesPanel = new NotesPanel('panel-content');
        this.setupResizableLayout();

        // Show initial panel
        this.switchPanel('ai');

        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();

        // Load app info
        this.loadAppInfo();

        console.log('DeepRead AI initialized');
    }

    createToastContainer() {
        this.toastContainer = document.createElement('div');
        this.toastContainer.className = 'toast-container';
        this.toastContainer.id = 'toast-container';
        document.body.appendChild(this.toastContainer);
    }

    setupSidebar() {
        const buttons = document.querySelectorAll('.sidebar-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const panel = btn.dataset.panel;
                if (panel) {
                    this.switchPanel(panel);
                }

                // Update active state
                buttons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });
    }

    setupHeader() {
        // Open PDF button
        document.getElementById('open-pdf-btn')?.addEventListener('click', () => {
            this.openPdf();
        });

        // Save button
        document.getElementById('save-btn')?.addEventListener('click', () => {
            this.saveCurrentNote();
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
        this.currentPanel = panel;

        // Update sidebar buttons
        document.querySelectorAll('.sidebar-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.panel === panel);
        });

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
                this.notesPanel.render(content);
            }
        }
    }

    // ==================== File Operations ====================

    async openPdf() {
        try {
            const result = await API.selectPdfFile();

            if (result.success && result.file_path) {
                await this.pdfViewer.loadDocument(result.file_path);
                this.showToast('PDF opened successfully', 'success');
            } else if (result.cancelled) {
                // User cancelled, do nothing
            } else {
                this.showToast(result.error || 'Failed to open PDF', 'error');
            }
        } catch (error) {
            console.error('Failed to open PDF:', error);
            this.showToast('Failed to open PDF', 'error');
        }
    }

    async saveCurrentNote() {
        if (this.currentPanel === 'notes' && this.notesPanel) {
            await this.notesPanel.saveNote();
        } else {
            // Switch to notes panel and save
            this.switchPanel('notes');
        }
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
    }

    render(container) {
        container.innerHTML = `
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
    }

    bindEvents() {
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
        this.noteId = '';
        this.title = '';
        this.content = '';
        this.viewMode = 'edit'; // 'edit' or 'preview'
    }

    render(container) {
        container.innerHTML = `
            <div class="notes-container">
                <div class="notes-toolbar">
                    <button class="btn btn-secondary btn-sm" id="new-note-btn">New Note</button>
                    <button class="btn btn-primary btn-sm" id="save-note-btn">Save</button>
                </div>
                <input type="text" class="note-title-input" id="note-title" placeholder="Note Title..." value="${this.title}">
                <div class="editor-tabs">
                    <button class="editor-tab ${this.viewMode === 'edit' ? 'active' : ''}" data-mode="edit">Edit</button>
                    <button class="editor-tab ${this.viewMode === 'preview' ? 'active' : ''}" data-mode="preview">Preview</button>
                </div>
                <div class="editor-toolbar">
                    <button class="toolbar-btn" data-action="bold" title="Bold (Ctrl+B)"><b>B</b></button>
                    <button class="toolbar-btn" data-action="italic" title="Italic (Ctrl+I)"><i>I</i></button>
                    <button class="toolbar-btn" data-action="heading" title="Heading">H</button>
                    <span class="toolbar-divider"></span>
                    <button class="toolbar-btn" data-action="list" title="List">•</button>
                    <button class="toolbar-btn" data-action="link" title="Link">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
                        </svg>
                    </button>
                    <button class="toolbar-btn" data-action="pdf-link" title="PDF Link">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                    </button>
                </div>
                <div class="notes-editor" id="notes-editor-area">
                    ${this.viewMode === 'edit' ? this.renderEditor() : this.renderPreview()}
                </div>
            </div>
        `;

        this.bindEvents();
    }

    renderEditor() {
        return `<textarea class="note-content-editor" id="note-content" placeholder="Start writing your notes...">${this.content}</textarea>`;
    }

    renderPreview() {
        return `<div class="note-preview" id="note-preview">${this.formatMarkdown(this.content)}</div>`;
    }

    bindEvents() {
        // View mode tabs
        document.querySelectorAll('.editor-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.viewMode = tab.dataset.mode;
                this.saveCurrentContent();
                this.render(document.getElementById('panel-content'));
            });
        });

        // Toolbar buttons
        document.querySelectorAll('.toolbar-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.handleToolbarAction(btn.dataset.action);
            });
        });

        // New note button
        document.getElementById('new-note-btn')?.addEventListener('click', () => {
            this.newNote();
        });

        // Save button
        document.getElementById('save-note-btn')?.addEventListener('click', () => {
            this.saveNote();
        });

        // Auto-save title
        document.getElementById('note-title')?.addEventListener('change', (e) => {
            this.title = e.target.value;
        });
    }

    handleToolbarAction(action) {
        const editor = document.getElementById('note-content');
        if (!editor) return;

        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        const text = editor.value;
        const selected = text.substring(start, end);

        let replacement = '';
        let cursorOffset = 0;

        switch (action) {
            case 'bold':
                replacement = `**${selected || 'bold text'}**`;
                cursorOffset = selected ? 0 : -2;
                break;
            case 'italic':
                replacement = `*${selected || 'italic text'}*`;
                cursorOffset = selected ? 0 : 1;
                break;
            case 'heading':
                replacement = `\n## ${selected || 'Heading'}\n`;
                break;
            case 'list':
                replacement = selected
                    ? selected.split('\n').map(line => `- ${line}`).join('\n')
                    : '- List item';
                break;
            case 'link':
                replacement = `[${selected || 'link text'}](url)`;
                cursorOffset = selected ? 0 : -1;
                break;
            case 'pdf-link':
                const page = window.app?.pdfViewer?.getCurrentPage() || 1;
                replacement = `[[pdf:doc#page=${page}]]`;
                break;
        }

        editor.value = text.substring(0, start) + replacement + text.substring(end);
        editor.focus();
        editor.setSelectionRange(start + replacement.length + cursorOffset, start + replacement.length + cursorOffset);

        this.content = editor.value;
    }

    saveCurrentContent() {
        const titleInput = document.getElementById('note-title');
        const contentInput = document.getElementById('note-content');

        if (titleInput) this.title = titleInput.value;
        if (contentInput) this.content = contentInput.value;
    }

    newNote() {
        this.noteId = '';
        this.title = '';
        this.content = '';
        this.viewMode = 'edit';
        this.render(document.getElementById('panel-content'));
    }

    async saveNote() {
        this.saveCurrentContent();

        try {
            const result = await API.saveNote(this.noteId, this.title, this.content);

            if (result.success) {
                this.noteId = result.note_id;
                window.app?.showToast('Note saved successfully', 'success');
            } else {
                window.app?.showToast(result.error || 'Failed to save note', 'error');
            }
        } catch (error) {
            window.app?.showToast('Failed to save note', 'error');
        }
    }

    formatMarkdown(text) {
        if (!text) return '<p><em>Start typing to see preview...</em></p>';

        return text
            // PDF links: [[pdf:doc_id#page=N]]
            .replace(/\[\[pdf:(.+?)#page=(\d+)\]\]/g, '<a href="#" class="pdf-link" data-page="$2">Page $2</a>')
            // Headers
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            // Bold
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            // Code
            .replace(/`(.+?)`/g, '<code>$1</code>')
            // Links
            .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>')
            // Lists
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            // Blockquotes
            .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
            // Paragraphs (must be last)
            .split('\n\n')
            .map(p => p.trim() ? `<p>${p}</p>` : '')
            .join('');
    }
}

// Initialize app
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new DeepReadApp();
    window.app = app; // Expose for debugging
});
