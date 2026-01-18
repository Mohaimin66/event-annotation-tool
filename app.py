"""
Event Extraction Annotation Tool - Flask Backend
"""
import json
import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# Determine base path for data files (supports Hugging Face Spaces persistent storage)
DATA_DIR = os.environ.get('DATA_DIR', 'data')


def load_json(filepath):
    """Load JSON file safely."""
    full_path = os.path.join(DATA_DIR, filepath) if not filepath.startswith(DATA_DIR) else filepath
    if not os.path.exists(full_path):
        # Try relative path
        full_path = filepath
    with open(full_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath, data):
    """Save JSON file safely."""
    full_path = os.path.join(DATA_DIR, filepath) if not filepath.startswith(DATA_DIR) else filepath
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_config():
    """Load app configuration."""
    return load_json('config.json')


def get_event_types():
    """Load event type definitions."""
    return load_json(os.path.join(DATA_DIR, 'event_types.json'))


def get_input_data():
    """Load input data."""
    return load_json(os.path.join(DATA_DIR, 'input_data.json'))


def get_annotator_split(annotator_id, total_annotators, data):
    """
    Deterministic split: each annotator gets every Nth item starting at their index.
    annotator_id is 0-indexed.
    """
    return [item for i, item in enumerate(data) if i % total_annotators == annotator_id]


def get_annotations_path(annotator_id):
    """Get path to annotator's annotations file."""
    return os.path.join(DATA_DIR, 'annotations', f'annotator_{annotator_id}.json')


def load_annotations(annotator_id):
    """Load existing annotations for an annotator."""
    path = get_annotations_path(annotator_id)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_annotation(annotator_id, annotation_data):
    """Save a single annotation."""
    path = get_annotations_path(annotator_id)
    annotations = load_annotations(annotator_id)

    # Find and update existing annotation or add new
    item_id = annotation_data['id']
    found = False
    for i, ann in enumerate(annotations):
        if ann['id'] == item_id:
            annotations[i] = annotation_data
            found = True
            break

    if not found:
        annotations.append(annotation_data)

    # Sort by ID for consistency
    annotations.sort(key=lambda x: x['id'])
    save_json(path, annotations)
    return True


# Routes
@app.route('/')
def index():
    """Serve main UI."""
    return render_template('index.html')


@app.route('/api/config')
def api_config():
    """Get app configuration."""
    try:
        config = get_config()
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/event-types')
def api_event_types():
    """Get all event type definitions."""
    try:
        event_types = get_event_types()
        return jsonify(event_types)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/<int:annotator_id>')
def api_data(annotator_id):
    """Get annotator's data split with any existing annotations."""
    try:
        config = get_config()
        all_data = get_input_data()

        # Get this annotator's split
        split_data = get_annotator_split(annotator_id, config['num_annotators'], all_data)

        # Load existing annotations
        existing_annotations = load_annotations(annotator_id)
        ann_by_id = {ann['id']: ann.get('annotation') for ann in existing_annotations}

        # Merge annotations into split data
        for item in split_data:
            if item['id'] in ann_by_id:
                item['annotation'] = ann_by_id[item['id']]

        return jsonify({
            'items': split_data,
            'total': len(split_data)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/annotate', methods=['POST'])
def api_annotate():
    """Save an annotation."""
    try:
        data = request.json
        annotator_id = data.get('annotator_id')
        item = data.get('item')
        annotation = data.get('annotation')

        if annotator_id is None or item is None or annotation is None:
            return jsonify({'error': 'Missing required fields'}), 400

        # Add timestamp
        annotation['annotated_at'] = datetime.utcnow().isoformat() + 'Z'

        # Build full annotation record
        annotation_record = {
            'id': item['id'],
            'sentence': item['sentence'],
            'tokens': item['tokens'],
            'model_prediction': item['model_prediction'],
            'annotation': annotation
        }

        save_annotation(annotator_id, annotation_record)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/progress/<int:annotator_id>')
def api_progress(annotator_id):
    """Get annotation progress for an annotator."""
    try:
        config = get_config()
        all_data = get_input_data()

        # Get total items in this annotator's split
        split_data = get_annotator_split(annotator_id, config['num_annotators'], all_data)
        total = len(split_data)

        # Count completed annotations
        annotations = load_annotations(annotator_id)
        completed = len([a for a in annotations if 'annotation' in a])

        return jsonify({
            'completed': completed,
            'total': total,
            'percentage': round(completed / total * 100, 1) if total > 0 else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Ensure annotations directory exists
    os.makedirs(os.path.join(DATA_DIR, 'annotations'), exist_ok=True)

    # Run the app
    port = int(os.environ.get('PORT', 7860))  # 7860 is Hugging Face Spaces default
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'false').lower() == 'true')
