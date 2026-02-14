# OCR Text Selection Layer Integration

## Architecture Overview

The OCR integration enables text selection on scanned PDF pages by overlaying transparent text spans on top of the rendered PDF image. The flow is:

```
User clicks OCR toggle
    → Frontend calls API.ocrPage(pageNum)
    → Backend lazy-inits OCRPipeline, renders page to PNG, runs PaddleOCR
    → Returns text lines with bounding boxes in PDF coordinate space
    → Frontend converts coordinates to screen space
    → Creates transparent <span> elements positioned over the PDF image
    → Browser native text selection allows copy/paste
```

## Data Flow

### Backend (`backend/api.py`)

1. `ocr_page(page_num)` checks the in-memory cache first
2. On cache miss, lazy-initializes `OCRPipeline` with a temp directory for rendered images
3. Calls `pipeline.run(first_page=N, last_page=N)` which:
   - Renders the PDF page to PNG at 150 DPI
   - Runs PaddleOCR to detect text regions
   - Normalizes pixel coordinates to PDF point coordinates
4. Simplifies polygon bounding boxes to rectangles `{x, y, width, height}`
5. Caches the result and returns `{"success": true, "lines": [...]}`

### Frontend (`frontend/js/pdf-viewer.js`)

1. `toggleOcr()` enables/disables OCR mode
2. `loadOcrForCurrentPage()` fetches OCR data (with client-side caching)
3. `renderOcrOverlay(lines)` creates positioned transparent spans
4. `clearOcrOverlay()` removes only OCR spans, preserving selection highlights

## Coordinate System Conversion

PDF and screen coordinate systems differ in Y-axis orientation:

```
PDF coordinates:          Screen coordinates:
Y=pageHeight (top)        Y=0 (top)
    ↑                         ↓
    |                         |
    |                         |
Y=0 (bottom)              Y=imgHeight (bottom)
```

The OCR pipeline outputs bounding boxes in PDF coordinates where:
- `rect.x` = left edge X position
- `rect.y` = **bottom** edge Y position (Y=0 is at page bottom)
- `rect.width` = box width
- `rect.height` = box height

Conversion to screen coordinates:

```javascript
scaleX = imgWidth / pageWidth;
scaleY = imgHeight / pageHeight;

screenX = rect.x * scaleX;
screenY = (pageHeight - rect.y - rect.height) * scaleY;
screenW = rect.width * scaleX;
screenH = rect.height * scaleY;
```

The `pageHeight - rect.y - rect.height` formula flips the Y axis and positions at the top edge of the text box.

## Caching Strategy

Two levels of caching are used:

1. **Backend cache** (`self._ocr_cache`): Maps page numbers to simplified line data. Persists for the lifetime of the current PDF. Cleared when a new PDF is opened via `_cleanup_ocr()`.

2. **Frontend cache** (`this.ocrResults`): Maps page numbers to the API response lines. Avoids redundant API calls when navigating back to previously OCR'd pages. Reset when a new document is loaded.

Cache invalidation occurs automatically when:
- A new PDF is opened (both caches cleared)
- OCR toggle is turned off (overlay removed, cache retained for re-enable)

## Integration Points

### Page Navigation
When `goToPage()` is called with OCR enabled, `loadOcrForCurrentPage()` is triggered automatically. Cached pages render instantly; uncached pages show a loading toast.

### Zoom Changes
`renderPage()` calls `renderOcrOverlay()` after the page image loads, recalculating all span positions using the new image dimensions. This ensures overlay alignment at any zoom level.

### Selection Mode
When OCR is active (`ocrEnabled = true`):
- `onSelectionStart()` returns early, disabling rectangle selection
- The selection layer gets `pointer-events: auto` and `user-select: text`
- Browser native text selection works on the transparent spans

When OCR is inactive:
- Rectangle selection mode operates as before
- `clearSelection()` preserves any OCR spans that may exist

## Extending the System

### Replacing the OCR Engine
The OCR engine is encapsulated in `backend/ocr/engine.py`. To use a different engine:
1. Create a new engine class with a `process_image(path) -> list[dict]` method
2. Each dict must have `text`, `confidence`, and `bbox` (polygon vertices in pixels)
3. Pass it to `OCRPipeline` or modify the pipeline constructor

### Adding Native Text Layer Support
For PDFs with embedded text, you could:
1. Add a `has_text(page_num)` method to `PDFEngine`
2. Check before running OCR; if native text exists, extract it with coordinates using PyMuPDF's `page.get_text("dict")`
3. Return the same `{text, confidence, x, y, width, height}` format so the frontend overlay code works unchanged
