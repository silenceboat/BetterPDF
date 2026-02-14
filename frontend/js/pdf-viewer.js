/**
 * DeepRead AI - PDF Viewer
 *
 * Handles PDF rendering, navigation, zoom, and text selection.
 */

class PDFViewer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentPage = 1;
        this.pageCount = 0;
        this.zoom = 1.0;
        this.minZoom = 0.25;
        this.maxZoom = 4.0;
        this.zoomStep = 0.25;

        this.pageImage = null;
        this.pageContainer = null;
        this.isLoading = false;

        // Selection state
        this.isSelecting = false;
        this.selectionStart = null;
        this.selectionEnd = null;
        this.selectionRect = null;
        this.selectedText = '';

        // OCR state
        this.ocrEnabled = false;
        this.ocrMode = 'page'; // 'page' or 'document'
        this.ocrResults = {};  // page_num -> lines array
        this.ocrLoading = false;
        this.ocrProgressTimer = null;
        this.autoFit = true;
        this._layoutResizeRaf = null;
        this._onDocumentClick = (e) => {
            if (e.target && e.target.closest && e.target.closest('#ocr-entry')) {
                return;
            }
            this.hideOcrModeMenu();
        };

        this.init();
    }

    init() {
        this.renderPlaceholder();
        this.setupKeyboardShortcuts();
        window.addEventListener('resize', () => this.onLayoutResize());
        window.addEventListener('deepread:layout-resized', () => this.onLayoutResize());
        document.addEventListener('click', this._onDocumentClick);
    }

    renderPlaceholder() {
        this.container.innerHTML = `
            <div class="pdf-viewport">
                <div class="pdf-placeholder">
                    <div class="pdf-placeholder-icon">
                        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                            <polyline points="14 2 14 8 20 8"/>
                            <path d="M10 13v-1a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1"/>
                            <path d="M10 13v7"/>
                            <path d="M14 13v7"/>
                        </svg>
                    </div>
                    <div class="pdf-placeholder-text">No PDF Open</div>
                    <div class="pdf-placeholder-hint">Click "Open PDF" to get started</div>
                    <button class="btn btn-primary" id="open-pdf-placeholder-btn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M6 22a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h8l6 6v10a2 2 0 0 1-2 2H6Z"/>
                            <path d="M14 2v6h6"/>
                            <path d="M12 18v-6"/>
                            <path d="M9 15l3 3 3-3"/>
                        </svg>
                        Open PDF
                    </button>
                </div>
            </div>
        `;

        const openBtn = this.container.querySelector('#open-pdf-placeholder-btn');
        if (openBtn) {
            openBtn.addEventListener('click', () => {
                window.app?.openPdf();
            });
        }
    }

    async loadDocument(filePath) {
        const result = await API.openPdf(filePath);

        if (result.success) {
            this.pageCount = result.page_count;
            this.currentPage = 1;
            this.zoom = 1.0;
            this.ocrResults = {};
            this.ocrEnabled = false;
            this.autoFit = true;

            this.renderViewer();
            await this.renderPage();
            this.fitWidth();
            this.updatePageInfo();

            return result;
        } else {
            throw new Error(result.error || 'Failed to open PDF');
        }
    }

    renderViewer() {
        this.container.innerHTML = `
            <div class="pdf-toolbar">
                <button id="prev-page" title="Previous Page (←)">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="m15 18-6-6 6-6"/>
                    </svg>
                </button>
                <button id="next-page" title="Next Page (→)">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="m9 18 6-6-6-6"/>
                    </svg>
                </button>
                <div class="page-info">
                    <span>Page</span>
                    <input type="text" id="page-input" value="1">
                    <span id="page-count">/ ${this.pageCount}</span>
                </div>
                <div class="zoom-controls">
                    <button id="zoom-out" title="Zoom Out">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="11" cy="11" r="8"/>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                            <line x1="8" y1="11" x2="14" y2="11"/>
                        </svg>
                    </button>
                    <span class="zoom-level" id="zoom-level">100%</span>
                    <button id="zoom-in" title="Zoom In">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="11" cy="11" r="8"/>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                            <line x1="11" y1="8" x2="11" y2="14"/>
                            <line x1="8" y1="11" x2="14" y2="11"/>
                        </svg>
                    </button>
                    <button id="fit-width" title="Fit Width">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M2 12h20"/>
                            <path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-6"/>
                            <path d="m4 8 4-4 4 4"/>
                            <path d="M20 8l-4-4-4 4"/>
                        </svg>
                    </button>
                </div>
                <div class="ocr-entry" id="ocr-entry">
                    <button class="ocr-toggle-btn" id="ocr-toggle" title="OCR Text Recognition">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="3" y="3" width="18" height="18" rx="2"/>
                            <path d="M7 7h2v2H7zM7 11h2v2H7zM7 15h2v2H7zM11 7h6M11 11h6M11 15h6"/>
                        </svg>
                        <span>OCR Text</span>
                        <svg class="ocr-caret" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="m6 9 6 6 6-6"/>
                        </svg>
                    </button>
                    <div class="ocr-mode-menu" id="ocr-mode-menu" hidden>
                        <button class="ocr-mode-item" id="ocr-mode-page">
                            <span class="ocr-mode-title">OCR This Page</span>
                            <span class="ocr-mode-desc">Fast recognition for current page only.</span>
                        </button>
                        <button class="ocr-mode-item" id="ocr-mode-document">
                            <span class="ocr-mode-title">OCR Entire PDF</span>
                            <span class="ocr-mode-desc">Background scan for all pages with progress.</span>
                        </button>
                    </div>
                </div>
                <div class="ocr-progress" id="ocr-progress" hidden>
                    <div class="ocr-progress-row">
                        <span class="ocr-progress-label" id="ocr-progress-label">OCR</span>
                        <span class="ocr-progress-meta" id="ocr-progress-meta">0%</span>
                    </div>
                    <div class="ocr-progress-track">
                        <div class="ocr-progress-fill" id="ocr-progress-fill"></div>
                    </div>
                </div>
            </div>
            <div class="pdf-viewport" id="pdf-viewport">
                <div class="pdf-page-container" id="page-container">
                    <img id="page-image" alt="PDF Page">
                    <div class="selection-layer" id="selection-layer"></div>
                </div>
            </div>
        `;

        this.bindEvents();
    }

    bindEvents() {
        // Navigation
        document.getElementById('prev-page')?.addEventListener('click', () => this.prevPage());
        document.getElementById('next-page')?.addEventListener('click', () => this.nextPage());

        // Page input
        const pageInput = document.getElementById('page-input');
        pageInput?.addEventListener('change', (e) => {
            const page = parseInt(e.target.value);
            if (page >= 1 && page <= this.pageCount) {
                this.goToPage(page);
            } else {
                e.target.value = this.currentPage;
            }
        });

        pageInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.target.blur();
            }
        });

        // Zoom
        document.getElementById('zoom-out')?.addEventListener('click', () => this.zoomOut());
        document.getElementById('zoom-in')?.addEventListener('click', () => this.zoomIn());
        document.getElementById('fit-width')?.addEventListener('click', () => this.fitWidth());

        // OCR controls
        document.getElementById('ocr-toggle')?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.onOcrButtonClicked();
        });
        document.getElementById('ocr-mode-page')?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.hideOcrModeMenu();
            this.enableOcr('page');
        });
        document.getElementById('ocr-mode-document')?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.hideOcrModeMenu();
            this.enableOcr('document');
        });

        // Selection
        const viewport = document.getElementById('pdf-viewport');
        const pageContainer = document.getElementById('page-container');

        if (pageContainer) {
            pageContainer.addEventListener('mousedown', (e) => this.onSelectionStart(e));
            pageContainer.addEventListener('mousemove', (e) => this.onSelectionMove(e));
            pageContainer.addEventListener('mouseup', (e) => this.onSelectionEnd(e));
        }

        // Click outside to clear selection
        viewport?.addEventListener('click', (e) => {
            if (e.target === viewport) {
                this.clearSelection();
            }
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Only handle if not typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            switch (e.key) {
                case 'ArrowLeft':
                case 'PageUp':
                    e.preventDefault();
                    this.prevPage();
                    break;
                case 'ArrowRight':
                case 'PageDown':
                    e.preventDefault();
                    this.nextPage();
                    break;
                case 'Home':
                    e.preventDefault();
                    this.goToPage(1);
                    break;
                case 'End':
                    e.preventDefault();
                    this.goToPage(this.pageCount);
                    break;
                case '+':
                case '=':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        this.zoomIn();
                    }
                    break;
                case '-':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        this.zoomOut();
                    }
                    break;
                case '0':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        this.setZoom(1.0);
                    }
                    break;
            }
        });
    }

    async renderPage() {
        if (this.isLoading || !this.pageCount) return;

        this.isLoading = true;
        const img = document.getElementById('page-image');

        try {
            const result = await API.getPage(this.currentPage, this.zoom);

            if (result.success) {
                img.src = `data:image/png;base64,${result.image_data}`;
                img.style.width = `${result.page_width * this.zoom}px`;
                img.style.height = `${result.page_height * this.zoom}px`;

                // Store page dimensions for coordinate calculations
                this.pageDimensions = {
                    width: result.page_width,
                    height: result.page_height
                };

                // Re-render OCR overlay if enabled (handles zoom changes)
                if (this.ocrEnabled && this.ocrResults[this.currentPage]) {
                    this.renderOcrOverlay(this.ocrResults[this.currentPage]);
                }
            }
        } catch (error) {
            console.error('Failed to render page:', error);
        } finally {
            this.isLoading = false;
        }
    }

    prevPage() {
        if (this.currentPage > 1) {
            this.goToPage(this.currentPage - 1);
        }
    }

    nextPage() {
        if (this.currentPage < this.pageCount) {
            this.goToPage(this.currentPage + 1);
        }
    }

    goToPage(pageNum) {
        if (pageNum < 1 || pageNum > this.pageCount || pageNum === this.currentPage) {
            return;
        }

        this.currentPage = pageNum;
        this.renderPage();
        this.updatePageInfo();
        this.clearSelection();

        if (this.ocrEnabled) {
            this.loadOcrForCurrentPage();
        }
    }

    updatePageInfo() {
        const pageInput = document.getElementById('page-input');
        const pageCount = document.getElementById('page-count');
        const prevBtn = document.getElementById('prev-page');
        const nextBtn = document.getElementById('next-page');

        if (pageInput) pageInput.value = this.currentPage;
        if (pageCount) pageCount.textContent = `/ ${this.pageCount}`;

        if (prevBtn) prevBtn.disabled = this.currentPage <= 1;
        if (nextBtn) nextBtn.disabled = this.currentPage >= this.pageCount;
    }

    zoomIn() {
        if (this.zoom < this.maxZoom) {
            this.setZoom(this.zoom + this.zoomStep, { manual: true });
        }
    }

    zoomOut() {
        if (this.zoom > this.minZoom) {
            this.setZoom(this.zoom - this.zoomStep, { manual: true });
        }
    }

    setZoom(zoom, options = {}) {
        const { manual = true } = options;
        this.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, zoom));
        if (manual) {
            this.autoFit = false;
        }
        this.renderPage();
        this.updateZoomDisplay();
    }

    fitWidth() {
        const viewport = document.getElementById('pdf-viewport');
        if (viewport && this.pageDimensions) {
            const padding = 80;
            const availableWidth = viewport.clientWidth - padding;
            const newZoom = availableWidth / this.pageDimensions.width;
            this.autoFit = true;
            this.setZoom(Math.min(newZoom, this.maxZoom), { manual: false });
        }
    }

    onLayoutResize() {
        if (!this.autoFit || !this.pageCount) return;
        if (this._layoutResizeRaf) {
            cancelAnimationFrame(this._layoutResizeRaf);
        }
        this._layoutResizeRaf = requestAnimationFrame(() => {
            this._layoutResizeRaf = null;
            this.fitWidth();
        });
    }

    updateZoomDisplay() {
        const zoomLevel = document.getElementById('zoom-level');
        if (zoomLevel) {
            zoomLevel.textContent = `${Math.round(this.zoom * 100)}%`;
        }
    }

    // ==================== Text Selection ====================

    onSelectionStart(e) {
        // Only left click
        if (e.button !== 0) return;

        // When OCR is active, let native text selection handle it
        if (this.ocrEnabled) return;

        const pageContainer = document.getElementById('page-container');
        const rect = pageContainer.getBoundingClientRect();

        this.isSelecting = true;
        this.selectionStart = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
        this.selectionEnd = { ...this.selectionStart };

        this.clearSelection();
    }

    onSelectionMove(e) {
        if (!this.isSelecting) return;

        const pageContainer = document.getElementById('page-container');
        const rect = pageContainer.getBoundingClientRect();

        this.selectionEnd = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };

        this.updateSelectionOverlay();
    }

    onSelectionEnd(e) {
        if (!this.isSelecting) return;

        this.isSelecting = false;

        // Calculate selection rectangle
        const rect = this.calculateSelectionRect();

        if (rect && this.isValidSelection(rect)) {
            this.selectionRect = rect;
            this.extractSelectedText();
            this.showSelectionMenu(e.clientX, e.clientY);
        } else {
            this.clearSelection();
        }
    }

    calculateSelectionRect() {
        if (!this.selectionStart || !this.selectionEnd) return null;

        const x1 = Math.min(this.selectionStart.x, this.selectionEnd.x);
        const y1 = Math.min(this.selectionStart.y, this.selectionEnd.y);
        const x2 = Math.max(this.selectionStart.x, this.selectionEnd.x);
        const y2 = Math.max(this.selectionStart.y, this.selectionEnd.y);

        return { x1, y1, x2, y2 };
    }

    isValidSelection(rect) {
        const minSize = 10;
        return (rect.x2 - rect.x1) > minSize && (rect.y2 - rect.y1) > minSize;
    }

    updateSelectionOverlay() {
        const layer = document.getElementById('selection-layer');
        if (!layer) return;

        const rect = this.calculateSelectionRect();
        if (!rect) return;

        // Remove existing highlight
        const existing = layer.querySelector('.selection-highlight');
        if (existing) existing.remove();

        // Create new highlight
        const highlight = document.createElement('div');
        highlight.className = 'selection-highlight';
        highlight.style.left = `${rect.x1}px`;
        highlight.style.top = `${rect.y1}px`;
        highlight.style.width = `${rect.x2 - rect.x1}px`;
        highlight.style.height = `${rect.y2 - rect.y1}px`;

        layer.appendChild(highlight);
    }

    async extractSelectedText() {
        if (!this.selectionRect) return;

        // Convert screen coordinates to PDF coordinates
        const pdfRect = this.screenToPdfCoords(this.selectionRect);

        try {
            const result = await API.extractText(this.currentPage, pdfRect);
            if (result.success) {
                this.selectedText = result.text;
            }
        } catch (error) {
            console.error('Failed to extract text:', error);
        }
    }

    screenToPdfCoords(screenRect) {
        if (!this.pageDimensions) return screenRect;

        const scaleX = this.pageDimensions.width / (document.getElementById('page-image')?.clientWidth || 1);
        const scaleY = this.pageDimensions.height / (document.getElementById('page-image')?.clientHeight || 1);

        return {
            x1: screenRect.x1 * scaleX,
            y1: screenRect.y1 * scaleY,
            x2: screenRect.x2 * scaleX,
            y2: screenRect.y2 * scaleY
        };
    }

    showSelectionMenu(x, y) {
        // Remove existing menu
        this.hideSelectionMenu();

        const menu = document.createElement('div');
        menu.className = 'selection-menu';
        menu.id = 'selection-menu';
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;

        const actions = [
            { label: 'Explain', action: 'explain' },
            { label: 'Summarize', action: 'summarize' },
            { label: 'Translate', action: 'translate' },
            { label: 'Define', action: 'define' },
            { label: 'Ask AI', action: 'ask' }
        ];

        actions.forEach(({ label, action }) => {
            const item = document.createElement('div');
            item.className = 'selection-menu-item';
            item.dataset.action = action;
            item.textContent = label;
            item.addEventListener('click', () => {
                this.handleSelectionAction(action);
                this.hideSelectionMenu();
            });
            menu.appendChild(item);
        });

        document.body.appendChild(menu);

        // Adjust position if menu goes off screen
        const menuRect = menu.getBoundingClientRect();
        if (menuRect.right > window.innerWidth) {
            menu.style.left = `${x - menuRect.width}px`;
        }
        if (menuRect.bottom > window.innerHeight) {
            menu.style.top = `${y - menuRect.height}px`;
        }
    }

    hideSelectionMenu() {
        const existing = document.getElementById('selection-menu');
        if (existing) existing.remove();
    }

    handleSelectionAction(action) {
        if (!this.selectedText) return;

        // Switch to AI panel and trigger action
        window.app?.switchPanel('ai');
        window.app?.aiPanel?.addUserMessage(`[${action}] ${this.selectedText.substring(0, 100)}...`);
        window.app?.aiPanel?.processAiAction(action, this.selectedText);
    }

    clearSelection() {
        this.hideSelectionMenu();
        this.selectionStart = null;
        this.selectionEnd = null;
        this.selectionRect = null;
        this.selectedText = '';

        const layer = document.getElementById('selection-layer');
        if (layer) {
            // Only remove selection elements, preserve OCR spans
            layer.querySelectorAll('.selection-highlight').forEach(el => el.remove());
            const menu = layer.querySelector('#selection-menu');
            if (menu) menu.remove();
        }
    }

    getCurrentPage() {
        return this.currentPage;
    }

    getPageCount() {
        return this.pageCount;
    }

    getSelectedText() {
        return this.selectedText;
    }

    // ==================== OCR ====================

    onOcrButtonClicked() {
        if (this.ocrEnabled) {
            this.disableOcr();
            return;
        }
        this.toggleOcrModeMenu();
    }

    toggleOcrModeMenu() {
        const menu = document.getElementById('ocr-mode-menu');
        if (!menu) return;
        menu.hidden = !menu.hidden;
    }

    hideOcrModeMenu() {
        const menu = document.getElementById('ocr-mode-menu');
        if (!menu) return;
        menu.hidden = true;
    }

    showOcrProgress(label, meta = '', indeterminate = false) {
        const progress = document.getElementById('ocr-progress');
        const labelEl = document.getElementById('ocr-progress-label');
        const metaEl = document.getElementById('ocr-progress-meta');
        const fillEl = document.getElementById('ocr-progress-fill');
        if (!progress || !labelEl || !metaEl || !fillEl) return;

        labelEl.textContent = label;
        metaEl.textContent = meta;
        progress.hidden = false;
        progress.classList.toggle('indeterminate', indeterminate);

        if (indeterminate) {
            fillEl.style.width = '38%';
        }
    }

    updateOcrProgress(processedPages, totalPages, totalLines = 0) {
        const progress = document.getElementById('ocr-progress');
        const metaEl = document.getElementById('ocr-progress-meta');
        const fillEl = document.getElementById('ocr-progress-fill');
        if (!progress || !metaEl || !fillEl) return;

        const total = Math.max(0, totalPages || 0);
        const processed = Math.max(0, Math.min(processedPages || 0, total || 0));
        const percent = total > 0 ? Math.round((processed / total) * 100) : 0;

        progress.classList.remove('indeterminate');
        fillEl.style.width = `${percent}%`;
        metaEl.textContent = `${processed}/${total} · ${percent}% · ${totalLines} lines`;
    }

    hideOcrProgress() {
        const progress = document.getElementById('ocr-progress');
        if (!progress) return;
        progress.hidden = true;
        progress.classList.remove('indeterminate');
    }

    enableOcr(mode = 'page') {
        this.ocrEnabled = true;
        this.ocrMode = mode;

        const btn = document.getElementById('ocr-toggle');
        if (btn) {
            btn.classList.add('active');
        }

        const layer = document.getElementById('selection-layer');
        if (layer) {
            layer.classList.add('ocr-active');
        }

        if (mode === 'document') {
            this.loadOcrForDocument();
        } else {
            this.loadOcrForCurrentPage();
        }
    }

    disableOcr() {
        this.ocrEnabled = false;
        if (this.ocrProgressTimer) {
            clearInterval(this.ocrProgressTimer);
            this.ocrProgressTimer = null;
        }
        const btn = document.getElementById('ocr-toggle');
        if (btn) {
            btn.classList.remove('active');
        }
        const layer = document.getElementById('selection-layer');
        if (layer) {
            layer.classList.remove('ocr-active');
        }
        this.clearOcrOverlay();
        this.hideOcrProgress();
    }

    async loadOcrForCurrentPage() {
        if (!this.pageCount) return;

        // Use cached result if available
        if (this.ocrResults[this.currentPage]) {
            this.renderOcrOverlay(this.ocrResults[this.currentPage]);
            return;
        }

        if (this.ocrLoading) return;
        this.ocrLoading = true;

        this.showOcrProgress('OCR This Page', 'Processing...', true);
        window.app?.showToast('Running OCR for current page...', 'info');

        try {
            const result = await API.ocrPage(this.currentPage);
            if (result.success) {
                this.ocrResults[this.currentPage] = result.lines;
                this.showOcrProgress('OCR This Page', `${result.lines.length} lines found`, false);
                this.updateOcrProgress(1, 1, result.lines.length);
                window.app?.showToast(`OCR complete: ${result.lines.length} lines found`, 'success');
                // Only render if still on the same page and OCR still enabled
                if (this.ocrEnabled) {
                    this.renderOcrOverlay(result.lines);
                }
            } else {
                window.app?.showToast(`OCR failed: ${result.error}`, 'error');
                this.hideOcrProgress();
            }
        } catch (error) {
            console.error('OCR failed:', error);
            window.app?.showToast('OCR failed', 'error');
            this.hideOcrProgress();
        } finally {
            this.ocrLoading = false;
            setTimeout(() => this.hideOcrProgress(), 1200);
        }
    }

    async loadOcrForDocument() {
        if (!this.pageCount || this.ocrLoading) return;

        this.ocrLoading = true;
        this.showOcrProgress('OCR Entire PDF', `0/${this.pageCount} · 0%`, false);
        window.app?.showToast(`Running OCR for all ${this.pageCount} pages...`, 'info', 4500);

        try {
            const startResult = await API.startOcrDocument();
            if (!startResult.success) {
                window.app?.showToast(`OCR failed: ${startResult.error}`, 'error', 6000);
                this.disableOcr();
                return;
            }

            const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
            while (this.ocrEnabled) {
                const progress = await API.getOcrProgress();
                if (!progress.success) {
                    window.app?.showToast(`OCR failed: ${progress.error || 'Unknown error'}`, 'error', 6000);
                    this.disableOcr();
                    return;
                }

                this.updateOcrProgress(
                    progress.processed_pages || 0,
                    progress.total_pages || this.pageCount,
                    progress.total_lines || 0
                );

                if (progress.status === 'completed') {
                    const currentResult = await API.ocrPage(this.currentPage);
                    if (currentResult.success) {
                        this.ocrResults[this.currentPage] = currentResult.lines;
                        if (this.ocrEnabled) {
                            this.renderOcrOverlay(currentResult.lines);
                        }
                    }
                    window.app?.showToast(
                        `OCR complete: ${progress.total_pages || this.pageCount} pages, ${progress.total_lines || 0} lines`,
                        'success',
                        4500
                    );
                    break;
                }

                if (progress.status === 'error') {
                    window.app?.showToast(`OCR failed: ${progress.error || 'Unknown error'}`, 'error', 7000);
                    this.disableOcr();
                    return;
                }

                await sleep(350);
            }
        } catch (error) {
            console.error('OCR failed:', error);
            window.app?.showToast('OCR failed', 'error');
            this.disableOcr();
        } finally {
            this.ocrLoading = false;
            setTimeout(() => this.hideOcrProgress(), 1500);
        }
    }

    renderOcrOverlay(lines) {
        this.clearOcrOverlay();

        if (!lines || !lines.length || !this.pageDimensions) return;

        const layer = document.getElementById('selection-layer');
        const img = document.getElementById('page-image');
        if (!layer || !img) return;

        const imgWidth = img.clientWidth;
        const imgHeight = img.clientHeight;
        const pageWidth = this.pageDimensions.width;
        const pageHeight = this.pageDimensions.height;
        const scaleX = imgWidth / pageWidth;
        const scaleY = imgHeight / pageHeight;

        for (const line of lines) {
            const span = document.createElement('span');
            span.className = 'ocr-text-span';
            span.textContent = line.text;

            // PDF coordinate system: Y=0 at bottom, rect.y is bottom edge
            // Screen coordinate system: Y=0 at top
            const screenX = line.x * scaleX;
            const screenY = (pageHeight - line.y - line.height) * scaleY;
            const screenW = line.width * scaleX;
            const screenH = line.height * scaleY;

            span.style.left = `${screenX}px`;
            span.style.top = `${screenY}px`;
            span.style.width = `${screenW}px`;
            span.style.height = `${screenH}px`;
            span.style.fontSize = `${screenH * 0.85}px`;

            layer.appendChild(span);
        }
    }

    clearOcrOverlay() {
        const layer = document.getElementById('selection-layer');
        if (layer) {
            layer.querySelectorAll('.ocr-text-span').forEach(el => el.remove());
        }
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PDFViewer;
}
