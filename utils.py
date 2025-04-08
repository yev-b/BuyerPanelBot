import json

def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
