"""
Event Extraction Annotation Tool - Flask Backend
Enhanced with IAA tracking, admin dashboard, and adjudication workflow
"""
import json
import os
import secrets
import random
import math
from datetime import datetime
from functools import wraps
from collections import Counter, defaultdict
from flask import Flask, render_template, jsonify, request, session, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Determine base path for data files (supports Hugging Face Spaces persistent storage)
DATA_DIR = os.environ.get('DATA_DIR', 'data')

# Random seed for reproducibility
SPLIT_SEED = 42


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
    DEPRECATED: Use get_annotator_split_with_iaa() for new projects.
    """
    return [item for i, item in enumerate(data) if i % total_annotators == annotator_id]


def get_split_metadata_path():
    """Get path to split metadata file."""
    return os.path.join(DATA_DIR, 'split_metadata.json')


def generate_split_metadata(all_data, config):
    """
    Generate split metadata for IAA overlap distribution.

    Creates a source of truth for which items go to which annotators,
    ensuring overlap items are assigned to exactly `overlap_annotators` annotators each.
    """
    random.seed(SPLIT_SEED)

    total_items = len(all_data)
    num_annotators = config['num_annotators']
    overlap_percent = config.get('iaa_overlap_percent', 15) / 100
    overlap_annotators = config.get('overlap_annotators', 3)

    # Calculate overlap pool size
    overlap_count = math.ceil(total_items * overlap_percent)

    # Get all item IDs (assuming 1-indexed)
    all_item_ids = [item['id'] for item in all_data]

    # Randomly select overlap items
    overlap_item_ids = sorted(random.sample(all_item_ids, min(overlap_count, len(all_item_ids))))

    # Get unique items (non-overlap)
    unique_item_ids = [id for id in all_item_ids if id not in overlap_item_ids]

    # Distribute overlap items - each goes to exactly `overlap_annotators` annotators
    overlap_assignments = {}
    annotator_overlap_counts = [0] * num_annotators

    for item_id in overlap_item_ids:
        # Select annotators with least overlap items assigned
        # Use random tiebreaking
        annotator_scores = [(i, annotator_overlap_counts[i], random.random())
                          for i in range(num_annotators)]
        annotator_scores.sort(key=lambda x: (x[1], x[2]))
        selected_annotators = [a[0] for a in annotator_scores[:overlap_annotators]]

        overlap_assignments[str(item_id)] = selected_annotators
        for ann_id in selected_annotators:
            annotator_overlap_counts[ann_id] += 1

    # Distribute unique items round-robin
    unique_assignments = {str(i): [] for i in range(num_annotators)}
    random.shuffle(unique_item_ids)  # Shuffle for fairness

    for i, item_id in enumerate(unique_item_ids):
        annotator_id = i % num_annotators
        unique_assignments[str(annotator_id)].append(item_id)

    metadata = {
        'overlap_item_ids': overlap_item_ids,
        'overlap_assignments': overlap_assignments,
        'unique_assignments': unique_assignments,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'seed': SPLIT_SEED,
        'config_snapshot': {
            'num_annotators': num_annotators,
            'iaa_overlap_percent': config.get('iaa_overlap_percent', 15),
            'overlap_annotators': overlap_annotators,
            'total_items': total_items
        }
    }

    return metadata


def ensure_split_metadata():
    """
    Generate split metadata on first run if not exists.
    Returns the metadata (either loaded or newly generated).
    """
    metadata_path = get_split_metadata_path()

    if os.path.exists(metadata_path):
        return load_json(metadata_path)

    # Generate new split
    config = get_config()
    all_data = get_input_data()
    metadata = generate_split_metadata(all_data, config)
    save_json(metadata_path, metadata)
    return metadata


def get_annotator_split_with_iaa(annotator_id, data):
    """
    Get annotator's data split using IAA overlap system.

    Each annotator gets:
    - Their assigned overlap items (shared with other annotators for IAA)
    - Their assigned unique items
    - Items are shuffled to hide which are overlap vs unique
    """
    metadata = ensure_split_metadata()
    data_by_id = {item['id']: item for item in data}

    annotator_str = str(annotator_id)

    # Get overlap items assigned to this annotator
    overlap_items = []
    for item_id_str, annotators in metadata['overlap_assignments'].items():
        if annotator_id in annotators:
            item_id = int(item_id_str)
            if item_id in data_by_id:
                overlap_items.append(data_by_id[item_id])

    # Get unique items assigned to this annotator
    unique_item_ids = metadata['unique_assignments'].get(annotator_str, [])
    unique_items = [data_by_id[id] for id in unique_item_ids if id in data_by_id]

    # Combine and shuffle
    all_items = overlap_items + unique_items

    # Use a deterministic shuffle per annotator for consistency
    random.seed(SPLIT_SEED + annotator_id)
    random.shuffle(all_items)

    return all_items


def is_overlap_item(item_id):
    """Check if an item is an overlap item."""
    metadata = ensure_split_metadata()
    return item_id in metadata['overlap_item_ids']


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


# ============== IAA Calculation Functions ==============

def get_gold_standard_path():
    """Get path to gold standard file."""
    return os.path.join(DATA_DIR, 'annotations', 'gold_standard.json')


def load_gold_standard():
    """Load gold standard annotations."""
    path = get_gold_standard_path()
    if os.path.exists(path):
        return load_json(path)
    return {}


def save_gold_standard(gold_data):
    """Save gold standard annotations."""
    save_json(get_gold_standard_path(), gold_data)


def get_all_annotations_for_item(item_id):
    """Get all annotations for a specific item from all annotators."""
    config = get_config()
    annotations = []

    for ann_id in range(config['num_annotators']):
        ann_data = load_annotations(ann_id)
        for item in ann_data:
            if item['id'] == item_id and 'annotation' in item:
                annotations.append({
                    'annotator_id': ann_id,
                    'annotator_name': config['annotator_names'][ann_id],
                    'annotation': item['annotation'],
                    'sentence': item.get('sentence', ''),
                    'tokens': item.get('tokens', [])
                })
    return annotations


def calculate_cohen_kappa(annotations1, annotations2, key='event_type'):
    """
    Calculate Cohen's Kappa between two annotators for a specific key.
    """
    if not annotations1 or not annotations2:
        return None

    # Find common items
    ids1 = {a['id'] for a in annotations1 if 'annotation' in a}
    ids2 = {a['id'] for a in annotations2 if 'annotation' in a}
    common_ids = ids1 & ids2

    if len(common_ids) < 2:
        return None

    # Get annotation values
    values1 = {a['id']: a['annotation'].get(key) for a in annotations1
               if a['id'] in common_ids and 'annotation' in a}
    values2 = {a['id']: a['annotation'].get(key) for a in annotations2
               if a['id'] in common_ids and 'annotation' in a}

    # Calculate agreement
    agreements = sum(1 for id in common_ids if values1.get(id) == values2.get(id))
    n = len(common_ids)

    # Get all possible categories
    all_values = list(set(values1.values()) | set(values2.values()))

    # Calculate expected agreement by chance
    pe = 0
    for val in all_values:
        p1 = sum(1 for v in values1.values() if v == val) / n
        p2 = sum(1 for v in values2.values() if v == val) / n
        pe += p1 * p2

    po = agreements / n  # Observed agreement

    if pe == 1:
        return 1.0  # Perfect agreement

    kappa = (po - pe) / (1 - pe)
    return round(kappa, 3)


def calculate_fleiss_kappa(all_annotations, key='event_type'):
    """
    Calculate Fleiss' Kappa for multi-annotator agreement.
    all_annotations: dict of {item_id: [{annotator_id, annotation}, ...]}
    """
    # Filter items with multiple annotators
    items_with_multi = {k: v for k, v in all_annotations.items() if len(v) >= 2}

    if not items_with_multi:
        return None

    # Get all possible categories
    categories = set()
    for item_anns in items_with_multi.values():
        for ann in item_anns:
            val = ann['annotation'].get(key)
            if val:
                categories.add(val)

    if len(categories) < 2:
        return None

    categories = sorted(list(categories))
    n_categories = len(categories)
    n_items = len(items_with_multi)

    # Build rating matrix
    matrix = []
    for item_id, anns in items_with_multi.items():
        row = [0] * n_categories
        for ann in anns:
            val = ann['annotation'].get(key)
            if val in categories:
                row[categories.index(val)] += 1
        matrix.append(row)

    # Calculate Fleiss' Kappa
    N = n_items
    n = max(sum(row) for row in matrix)  # Number of raters per item

    if n < 2:
        return None

    # P_i for each item
    P_i = []
    for row in matrix:
        n_i = sum(row)
        if n_i < 2:
            continue
        sum_sq = sum(r * r for r in row)
        P_i.append((sum_sq - n_i) / (n_i * (n_i - 1)))

    if not P_i:
        return None

    P_bar = sum(P_i) / len(P_i)

    # p_j for each category
    total_ratings = sum(sum(row) for row in matrix)
    p_j = [sum(row[j] for row in matrix) / total_ratings for j in range(n_categories)]

    P_e = sum(p * p for p in p_j)

    if P_e == 1:
        return 1.0

    kappa = (P_bar - P_e) / (1 - P_e)
    return round(kappa, 3)


def calculate_trigger_f1(annotations1, annotations2):
    """
    Calculate F1 score for trigger word agreement between two annotators.
    Uses token-level comparison.
    """
    if not annotations1 or not annotations2:
        return None

    # Find common items
    ids1 = {a['id'] for a in annotations1 if 'annotation' in a}
    ids2 = {a['id'] for a in annotations2 if 'annotation' in a}
    common_ids = ids1 & ids2

    if not common_ids:
        return None

    total_precision = 0
    total_recall = 0
    count = 0

    ann1_by_id = {a['id']: a for a in annotations1}
    ann2_by_id = {a['id']: a for a in annotations2}

    for item_id in common_ids:
        triggers1 = set(ann1_by_id[item_id]['annotation'].get('trigger_indices', []))
        triggers2 = set(ann2_by_id[item_id]['annotation'].get('trigger_indices', []))

        if not triggers1 and not triggers2:
            total_precision += 1
            total_recall += 1
        elif triggers1 and triggers2:
            intersection = triggers1 & triggers2
            precision = len(intersection) / len(triggers1) if triggers1 else 0
            recall = len(intersection) / len(triggers2) if triggers2 else 0
            total_precision += precision
            total_recall += recall
        # If one is empty and other isn't, add 0

        count += 1

    if count == 0:
        return None

    avg_precision = total_precision / count
    avg_recall = total_recall / count

    if avg_precision + avg_recall == 0:
        return 0

    f1 = 2 * (avg_precision * avg_recall) / (avg_precision + avg_recall)
    return round(f1, 3)


def get_iaa_metrics():
    """
    Calculate comprehensive IAA metrics for overlap items.
    """
    config = get_config()
    metadata = ensure_split_metadata()
    overlap_item_ids = metadata['overlap_item_ids']

    # Collect all annotations grouped by item
    all_item_annotations = defaultdict(list)

    for ann_id in range(config['num_annotators']):
        annotations = load_annotations(ann_id)
        for ann in annotations:
            if ann['id'] in overlap_item_ids and 'annotation' in ann:
                all_item_annotations[ann['id']].append({
                    'annotator_id': ann_id,
                    'annotator_name': config['annotator_names'][ann_id],
                    'annotation': ann['annotation']
                })

    # Calculate Fleiss' Kappa for event types
    fleiss_kappa = calculate_fleiss_kappa(all_item_annotations)

    # Calculate pairwise Cohen's Kappa
    pairwise_kappa = {}
    for i in range(config['num_annotators']):
        for j in range(i + 1, config['num_annotators']):
            ann_i = load_annotations(i)
            ann_j = load_annotations(j)
            kappa = calculate_cohen_kappa(ann_i, ann_j)
            if kappa is not None:
                pair_name = f"{config['annotator_names'][i]} vs {config['annotator_names'][j]}"
                pairwise_kappa[pair_name] = kappa

    # Calculate trigger F1
    pairwise_f1 = {}
    for i in range(config['num_annotators']):
        for j in range(i + 1, config['num_annotators']):
            ann_i = load_annotations(i)
            ann_j = load_annotations(j)
            f1 = calculate_trigger_f1(ann_i, ann_j)
            if f1 is not None:
                pair_name = f"{config['annotator_names'][i]} vs {config['annotator_names'][j]}"
                pairwise_f1[pair_name] = f1

    # Find disagreements
    disagreements = []
    for item_id, anns in all_item_annotations.items():
        if len(anns) >= 2:
            event_types = [a['annotation'].get('event_type') for a in anns]
            triggers = [tuple(sorted(a['annotation'].get('trigger_indices', []))) for a in anns]

            # Check for event type disagreement
            if len(set(event_types)) > 1 or len(set(triggers)) > 1:
                disagreements.append({
                    'item_id': item_id,
                    'annotations': anns,
                    'event_type_disagreement': len(set(event_types)) > 1,
                    'trigger_disagreement': len(set(triggers)) > 1
                })

    return {
        'fleiss_kappa': fleiss_kappa,
        'pairwise_cohen_kappa': pairwise_kappa,
        'pairwise_trigger_f1': pairwise_f1,
        'disagreements': disagreements,
        'overlap_items_count': len(overlap_item_ids),
        'annotated_overlap_count': len(all_item_annotations)
    }


def get_kappa_interpretation(kappa):
    """Return interpretation of Kappa value."""
    if kappa is None:
        return 'N/A'
    if kappa < 0.20:
        return 'Poor'
    elif kappa < 0.40:
        return 'Fair'
    elif kappa < 0.60:
        return 'Moderate'
    elif kappa < 0.80:
        return 'Substantial'
    else:
        return 'Almost Perfect'


# ============== Merge and Export Functions ==============

def merge_annotations():
    """
    Merge all annotations into final datasets.
    - Unique items: Direct merge
    - Overlap items: Majority vote with conflict flagging
    """
    config = get_config()
    metadata = ensure_split_metadata()
    all_data = get_input_data()
    data_by_id = {item['id']: item for item in all_data}

    overlap_item_ids = set(metadata['overlap_item_ids'])

    # Collect all annotations
    all_annotations = defaultdict(list)
    for ann_id in range(config['num_annotators']):
        annotations = load_annotations(ann_id)
        for ann in annotations:
            if 'annotation' in ann:
                all_annotations[ann['id']].append({
                    'annotator_id': ann_id,
                    'annotator_name': config['annotator_names'][ann_id],
                    'annotation': ann['annotation']
                })

    merged_unique = []
    merged_overlap = []

    for item_id, item_data in data_by_id.items():
        anns = all_annotations.get(item_id, [])

        if item_id in overlap_item_ids:
            # Overlap item - use majority vote
            if anns:
                merged_item = resolve_overlap_item(item_data, anns)
                merged_overlap.append(merged_item)
        else:
            # Unique item - should have single annotation
            if anns:
                merged_item = {
                    **item_data,
                    'annotation': anns[0]['annotation'],
                    'annotated_by': anns[0]['annotator_name']
                }
                merged_unique.append(merged_item)

    return merged_unique, merged_overlap


def resolve_overlap_item(item_data, annotations):
    """
    Resolve an overlap item using majority vote.
    Returns the merged item with resolution status.
    """
    # Count event types
    event_type_counts = Counter(a['annotation'].get('event_type') for a in annotations)

    # Majority vote for event type
    most_common_type = event_type_counts.most_common(1)[0] if event_type_counts else (None, 0)

    # Check if there's agreement
    total_votes = len(annotations)
    majority_votes = most_common_type[1]
    has_majority = majority_votes > total_votes / 2

    # Find most common trigger
    trigger_counts = Counter(
        tuple(sorted(a['annotation'].get('trigger_indices', [])))
        for a in annotations
    )
    most_common_trigger = trigger_counts.most_common(1)[0] if trigger_counts else ([], 0)

    resolution_status = 'majority_vote' if has_majority else 'needs_adjudication'

    return {
        **item_data,
        'annotation': {
            'event_type': most_common_type[0],
            'trigger_indices': list(most_common_trigger[0]),
            'not_in_list': most_common_type[0] is None and any(
                a['annotation'].get('not_in_list') for a in annotations
            )
        },
        'resolution_status': resolution_status,
        'annotator_votes': [
            {
                'annotator': a['annotator_name'],
                'event_type': a['annotation'].get('event_type'),
                'trigger_indices': a['annotation'].get('trigger_indices', [])
            }
            for a in annotations
        ],
        'agreement_ratio': f"{majority_votes}/{total_votes}"
    }


# ============== Authentication ==============

def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = get_config()
        # If no password set, allow access
        if not config.get('password'):
            return f(*args, **kwargs)
        # Check if logged in
        if not session.get('logged_in'):
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            if request.is_json:
                return jsonify({'error': 'Admin access required'}), 403
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page - handles both regular and admin login."""
    config = get_config()

    # If no password set, redirect to main app
    if not config.get('password'):
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')

        # Check admin password first
        if password == config.get('admin_password'):
            session['logged_in'] = True
            session['is_admin'] = True
            return redirect(url_for('admin'))
        # Check regular annotator password
        elif password == config.get('password'):
            session['logged_in'] = True
            session['is_admin'] = False
            return redirect(url_for('index'))
        else:
            error = 'Invalid password'

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    """Serve main UI."""
    return render_template('index.html')


@app.route('/api/config')
@login_required
def api_config():
    """Get app configuration."""
    try:
        config = get_config()
        # Don't expose password to frontend
        safe_config = {k: v for k, v in config.items() if k != 'password'}
        return jsonify(safe_config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/event-types')
@login_required
def api_event_types():
    """Get all event type definitions."""
    try:
        event_types = get_event_types()
        return jsonify(event_types)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/<int:annotator_id>')
@login_required
def api_data(annotator_id):
    """Get annotator's data split with any existing annotations (using IAA system)."""
    try:
        all_data = get_input_data()

        # Get this annotator's split using IAA-aware function
        split_data = get_annotator_split_with_iaa(annotator_id, all_data)

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
@login_required
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
@login_required
def api_progress(annotator_id):
    """Get annotation progress for an annotator."""
    try:
        all_data = get_input_data()

        # Get total items in this annotator's split (using IAA system)
        split_data = get_annotator_split_with_iaa(annotator_id, all_data)
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


# ============== Admin Routes ==============

@app.route('/admin')
@admin_required
def admin():
    """Admin dashboard."""
    return render_template('admin.html')


@app.route('/api/admin/progress')
@admin_required
def api_admin_progress():
    """Get progress for all annotators."""
    try:
        config = get_config()
        all_data = get_input_data()

        progress = []
        for ann_id in range(config['num_annotators']):
            split_data = get_annotator_split_with_iaa(ann_id, all_data)
            total = len(split_data)

            annotations = load_annotations(ann_id)
            completed = len([a for a in annotations if 'annotation' in a])

            progress.append({
                'annotator_id': ann_id,
                'name': config['annotator_names'][ann_id],
                'completed': completed,
                'total': total,
                'percentage': round(completed / total * 100, 1) if total > 0 else 0
            })

        # Overall stats
        total_items = len(all_data)
        metadata = ensure_split_metadata()
        overlap_count = len(metadata['overlap_item_ids'])

        return jsonify({
            'annotators': progress,
            'total_items': total_items,
            'overlap_items': overlap_count,
            'unique_items': total_items - overlap_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/iaa')
@admin_required
def api_admin_iaa():
    """Get IAA metrics and disagreements."""
    try:
        metrics = get_iaa_metrics()
        all_data = get_input_data()
        data_by_id = {item['id']: item for item in all_data}

        # Enhance disagreements with sentence info
        for disagreement in metrics['disagreements']:
            item_id = disagreement['item_id']
            if item_id in data_by_id:
                disagreement['sentence'] = data_by_id[item_id]['sentence']
                disagreement['tokens'] = data_by_id[item_id]['tokens']

        # Add kappa interpretations
        if metrics['fleiss_kappa'] is not None:
            metrics['fleiss_kappa_interpretation'] = get_kappa_interpretation(metrics['fleiss_kappa'])

        for pair, kappa in metrics['pairwise_cohen_kappa'].items():
            metrics['pairwise_cohen_kappa'][pair] = {
                'value': kappa,
                'interpretation': get_kappa_interpretation(kappa)
            }

        # Load gold standard status
        gold = load_gold_standard()
        metrics['gold_standard_count'] = len(gold)

        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/export')
@admin_required
def api_admin_export():
    """Export all annotations."""
    try:
        merged_unique, merged_overlap = merge_annotations()

        # Save merged files
        save_json(os.path.join(DATA_DIR, 'annotations', 'merged_unique.json'), merged_unique)
        save_json(os.path.join(DATA_DIR, 'annotations', 'merged_overlap.json'), merged_overlap)

        return jsonify({
            'merged_unique': merged_unique,
            'merged_overlap': merged_overlap,
            'unique_count': len(merged_unique),
            'overlap_count': len(merged_overlap),
            'files_saved': [
                'data/annotations/merged_unique.json',
                'data/annotations/merged_overlap.json'
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/adjudicate', methods=['POST'])
@admin_required
def api_admin_adjudicate():
    """Save a gold standard annotation."""
    try:
        data = request.json
        item_id = data.get('item_id')
        annotation = data.get('annotation')

        if item_id is None or annotation is None:
            return jsonify({'error': 'Missing required fields'}), 400

        gold = load_gold_standard()

        # Add adjudication metadata
        annotation['adjudicated_at'] = datetime.utcnow().isoformat() + 'Z'

        gold[str(item_id)] = annotation
        save_gold_standard(gold)

        return jsonify({'success': True, 'total_gold': len(gold)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/gold')
@admin_required
def api_admin_gold():
    """Get gold standard annotations."""
    try:
        gold = load_gold_standard()
        return jsonify({
            'gold_standard': gold,
            'count': len(gold)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/item/<int:item_id>')
@admin_required
def api_admin_item(item_id):
    """Get all annotations for a specific item (for adjudication)."""
    try:
        all_data = get_input_data()
        data_by_id = {item['id']: item for item in all_data}

        if item_id not in data_by_id:
            return jsonify({'error': 'Item not found'}), 404

        item = data_by_id[item_id]
        annotations = get_all_annotations_for_item(item_id)
        gold = load_gold_standard()

        return jsonify({
            'item': item,
            'annotations': annotations,
            'gold_standard': gold.get(str(item_id)),
            'is_overlap': is_overlap_item(item_id)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/event-types-map')
@login_required
def api_event_types_map():
    """Get event types as a map by ID."""
    try:
        event_types = get_event_types()
        return jsonify({et['id']: et for et in event_types})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Ensure annotations directory exists
    os.makedirs(os.path.join(DATA_DIR, 'annotations'), exist_ok=True)

    # Run the app
    port = int(os.environ.get('PORT', 7860))  # 7860 is Hugging Face Spaces default
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'false').lower() == 'true')
