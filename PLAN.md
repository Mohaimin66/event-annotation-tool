# Event Extraction Annotation Tool - Implementation Progress

## Project Overview
A lightweight, localhost-hosted annotation UI for event extraction datasets. Annotators review model predictions and finalize trigger words and event types.

**Hosting**: Hugging Face Spaces (free, centralized output for all annotators)

---

## Current Status: Setting Up GitHub Repository

### Session Checkpoints
- [x] Created project directory: `event-annotation-tool/`
- [x] Initialized git repository
- [x] Installed GitHub CLI (gh)
- [ ] **IN PROGRESS**: Authenticating with GitHub
- [ ] Create GitHub repository
- [ ] Push initial setup

---

## Implementation Phases

### Phase 1: Project Setup
- [ ] Create directory structure (data/, static/, templates/, data/annotations/)
- [ ] Create config.json
- [ ] Create sample event_types.json (10-20 types for testing)
- [ ] Create sample input_data.json (20-30 sentences for testing)
- [ ] Create requirements.txt for Flask

### Phase 2: Backend API (app.py)
- [ ] Flask app initialization
- [ ] `/` - Serve main UI
- [ ] `/api/config` - Get app configuration
- [ ] `/api/event-types` - Get all event type definitions
- [ ] `/api/data/<annotator_id>` - Get annotator's data split (deterministic)
- [ ] `/api/annotate` - Save annotation (POST)
- [ ] `/api/progress/<annotator_id>` - Get annotation progress

### Phase 3: Frontend - Basic UI (index.html)
- [ ] HTML template with layout structure
- [ ] Annotator dropdown selection
- [ ] Sentence display with clickable tokens
- [ ] Event type buttons for model predictions
- [ ] Progress bar

### Phase 4: Styling (style.css)
- [ ] Clean, modern look
- [ ] Token chips with selection states
- [ ] Event type cards with hover/selected states
- [ ] Responsive layout
- [ ] Search modal styling

### Phase 5: Frontend Logic (app.js)
- [ ] Token click/selection logic (including Shift+range)
- [ ] Event type selection with definition toggle
- [ ] Search modal for all event types
- [ ] "Not in event list" checkbox
- [ ] Pagination controls
- [ ] Progress bar updates
- [ ] Keyboard shortcuts (1/2/3, arrows, Space, Ctrl+S, N, /, Esc)
- [ ] Auto-save on navigation

### Phase 6: Hugging Face Spaces Configuration
- [ ] Create README.md with HF Spaces metadata
- [ ] Adapt file paths for persistent storage
- [ ] Test deployment

### Phase 7: Testing & Polish
- [ ] Test with sample data locally
- [ ] Test multi-annotator splits
- [ ] Test all keyboard shortcuts
- [ ] Verify output JSON format
- [ ] Deploy to Hugging Face Spaces
- [ ] Test remote access

---

## Architecture

```
event-annotation-tool/
├── app.py                 # Flask backend
├── config.json            # App configuration
├── requirements.txt       # Python dependencies
├── README.md              # HF Spaces config
├── data/
│   ├── event_types.json   # 200 event type definitions
│   ├── input_data.json    # Sentences + model predictions
│   └── annotations/       # Output: one file per annotator
├── static/
│   ├── style.css
│   └── app.js
└── templates/
    └── index.html
```

---

## Key Design Decisions

1. **Centralized Storage via HF Spaces**: All annotators access same deployment, annotations saved to HF persistent storage
2. **Deterministic Splitting**: `annotator_id % num_annotators == item_index % num_annotators`
3. **JSON File Output**: One file per annotator in `data/annotations/`
4. **Keyboard-First UX**: Heavy keyboard shortcut support for speed

---

## Last Updated
2026-01-18 - Session started, setting up GitHub
