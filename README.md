---
title: Event Annotation Tool
emoji: 📝
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
license: mit
---

# Event Extraction Annotation Tool

A lightweight annotation UI for event extraction datasets. Annotators review model predictions and finalize trigger words and event types.

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/Mohaimin66/event-annotation-tool.git
cd event-annotation-tool

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Open http://localhost:7860 in your browser.

### Deploy to Hugging Face Spaces

1. Fork this repository
2. Create a new Space on [Hugging Face](https://huggingface.co/spaces)
3. Connect it to your forked repo
4. The app will auto-deploy

## Using Your Own Dataset

### Step 1: Configure Annotators

Edit `config.json`:

```json
{
  "num_annotators": 3,
  "items_per_page": 10,
  "annotator_names": ["Alice", "Bob", "Charlie"]
}
```

- `num_annotators`: Number of annotators (determines how data is split)
- `annotator_names`: Display names for each annotator

### Step 2: Prepare Event Types

Edit `data/event_types.json`:

```json
[
  {
    "id": "unique_event_id",
    "name": "Display Name",
    "description": "Detailed description of the event type..."
  }
]
```

### Step 3: Prepare Input Data

Edit `data/input_data.json`:

```json
[
  {
    "id": 1,
    "sentence": "The original sentence text.",
    "tokens": ["The", "original", "sentence", "text", "."],
    "model_prediction": {
      "trigger_indices": [2],
      "top_event_types": ["event_id_1", "event_id_2", "event_id_3"]
    }
  }
]
```

**Fields:**
- `id`: Unique identifier for each sentence
- `sentence`: The full sentence text
- `tokens`: Pre-tokenized array of words
- `model_prediction.trigger_indices`: Token indices predicted as triggers (0-indexed)
- `model_prediction.top_event_types`: Top 3 predicted event type IDs

### Data Splitting

Data is automatically split among annotators using deterministic assignment:
- Annotator 0 gets items 0, 3, 6, 9, ...
- Annotator 1 gets items 1, 4, 7, 10, ...
- Annotator 2 gets items 2, 5, 8, 11, ...

This ensures each annotator gets a unique, non-overlapping subset.

## Output Format

Annotations are saved to `data/annotations/annotator_X.json`:

```json
[
  {
    "id": 1,
    "sentence": "He went to the jungle and killed a horse.",
    "tokens": ["He", "went", "to", "the", "jungle", "and", "killed", "a", "horse", "."],
    "model_prediction": {
      "trigger_indices": [6],
      "top_event_types": ["hunt", "kill", "attack"]
    },
    "annotation": {
      "trigger_indices": [6],
      "event_type": "kill",
      "not_in_list": false,
      "annotated_at": "2026-01-18T10:30:00Z"
    }
  }
]
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1`, `2`, `3` | Select model's 1st/2nd/3rd prediction |
| `←` / `→` | Previous/next item |
| `Space` | Toggle definition panel |
| `Ctrl+S` / `Cmd+S` | Save current annotation |
| `N` | Toggle "Not in event list" |
| `/` | Open search modal |
| `Esc` | Close search modal |

## Project Structure

```
event-annotation-tool/
├── app.py                 # Flask backend
├── config.json            # App configuration
├── requirements.txt       # Python dependencies
├── Dockerfile             # For HF Spaces deployment
├── data/
│   ├── event_types.json   # Event type definitions
│   ├── input_data.json    # Input sentences + predictions
│   └── annotations/       # Output annotations (per annotator)
├── static/
│   ├── style.css          # Styling
│   └── app.js             # Frontend logic
└── templates/
    └── index.html         # Main UI template
```

## Merging Annotations

After annotation is complete, merge all annotator files:

```python
import json
import os

annotations_dir = "data/annotations"
all_annotations = []

for filename in os.listdir(annotations_dir):
    if filename.endswith(".json"):
        with open(os.path.join(annotations_dir, filename)) as f:
            all_annotations.extend(json.load(f))

# Sort by ID
all_annotations.sort(key=lambda x: x["id"])

# Save merged file
with open("merged_annotations.json", "w") as f:
    json.dump(all_annotations, f, indent=2)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve main UI |
| `/api/config` | GET | Get app configuration |
| `/api/event-types` | GET | Get all event type definitions |
| `/api/data/<annotator_id>` | GET | Get annotator's data split |
| `/api/annotate` | POST | Save annotation |
| `/api/progress/<annotator_id>` | GET | Get annotation progress |

## License

MIT
