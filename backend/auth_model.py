import os
import functools
import numpy as np
import tensorflow as tf
from pathlib import Path

# Normalization statistics (Hardcoded from training results)
STATS = {
    'physical_code': {'mean': 47.00, 'std': 22.05},
    'flight_time': {'mean': 445.15, 'std': 488.03},
    'text_length': {'mean': 131.78, 'std': 78.55}
}

# Physical code vocabulary mapping (Hardcoded from LabelEncoder mapping)
VOCAB = {'AltLeft': 0, 'AltRight': 1, 'ArrowDown': 2, 'ArrowLeft': 3, 'ArrowRight': 4, 'ArrowUp': 5, 'AudioVolumeDown': 6, 'AudioVolumeMute': 7, 'AudioVolumeUp': 8, 'Backquote': 9, 'Backslash': 10, 'Backspace': 11, 'BracketLeft': 12, 'BracketRight': 13, 'CapsLock': 14, 'Comma': 15, 'ControlLeft': 16, 'ControlRight': 17, 'Delete': 18, 'Digit0': 19, 'Digit1': 20, 'Digit2': 21, 'Digit3': 22, 'Digit4': 23, 'Digit5': 24, 'Digit6': 25, 'Digit7': 26, 'Digit8': 27, 'Digit9': 28, 'End': 29, 'Enter': 30, 'Equal': 31, 'Escape': 32, 'F1': 33, 'F14': 34, 'Home': 35, 'Insert': 36, 'IntlBackslash': 37, 'KeyA': 38, 'KeyB': 39, 'KeyC': 40, 'KeyD': 41, 'KeyE': 42, 'KeyF': 43, 'KeyG': 44, 'KeyH': 45, 'KeyI': 46, 'KeyJ': 47, 'KeyK': 48, 'KeyL': 49, 'KeyM': 50, 'KeyN': 51, 'KeyO': 52, 'KeyP': 53, 'KeyQ': 54, 'KeyR': 55, 'KeyS': 56, 'KeyT': 57, 'KeyU': 58, 'KeyV': 59, 'KeyW': 60, 'KeyX': 61, 'KeyY': 62, 'KeyZ': 63, 'MediaPlayPause': 64, 'MetaLeft': 65, 'MetaRight': 66, 'Minus': 67, 'NumLock': 68, 'Numpad0': 69, 'Numpad4': 70, 'NumpadAdd': 71, 'NumpadSubtract': 72, 'PageDown': 73, 'Period': 74, 'PrintScreen': 75, 'Quote': 76, 'Semicolon': 77, 'ShiftLeft': 78, 'ShiftRight': 79, 'Slash': 80, 'Space': 81, 'Tab': 82, 'nan': 83}

MAX_TIMESTEPS = 300
MIN_KEYDOWN_EVENTS = 10

@functools.lru_cache(maxsize=5)
def get_model(participant_id: str):
    """
    Loads a Transformer model for a specific participant from the disk.
    Uses LRU cache to keep only the 5 most recently used models in memory.
    """
    model_path = Path(__file__).parent / "models" / f"transformer_{participant_id}.keras"
    if not model_path.exists():
        raise FileNotFoundError(f"Model for participant {participant_id} not found at {model_path}")
    
    return tf.keras.models.load_model(str(model_path))

def preprocess_events(events: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """
    Prepares raw keystroke events for Transformer inference.
    
    Processing steps:
    1. Filter to 'keydown' events only.
    2. Sort events by timestamp.
    3. Compute flight_time (diff between consecutive keydowns).
    4. Encode physical_code using hardcoded VOCAB.
    5. Stack features: [physical_code, flight_time, text_length].
    6. Truncate/Pre-pad to exactly 300 timesteps.
    7. Generate boolean mask for real data positions.
    8. Normalize features using hardcoded STATS and re-zero padded positions.
    """
    # 1. & 2. Filter and Sort
    keydown_events = [e for e in events if e.get('event_type') == 'keydown']
    keydown_events.sort(key=lambda x: x['timestamp'])
    
    if not keydown_events:
        return np.zeros((1, MAX_TIMESTEPS, 3), dtype='float32'), np.zeros((1, MAX_TIMESTEPS), dtype='bool')

    # 3. Compute flight_time
    timestamps = np.array([e['timestamp'] for e in keydown_events])
    flight_times = np.diff(timestamps, prepend=timestamps[0])
    flight_times = np.clip(flight_times, 0, 2000).astype('float32')  # Cap at 2000ms to reduce outlier impact

    # 4. Encode physical_code
    encoded_codes = [VOCAB.get(e.get('physical_code'), 0) for e in keydown_events]

    # 5. Stack features
    text_lengths = [e.get('text_length', 0) for e in keydown_events]
    features = np.stack([encoded_codes, flight_times, text_lengths], axis=1).astype('float32')

    # 6. Truncate/Pad
    n_events = len(features)
    if n_events > MAX_TIMESTEPS:
        features = features[-MAX_TIMESTEPS:]
        mask = np.ones(MAX_TIMESTEPS, dtype='bool')
    else:
        pad_len = MAX_TIMESTEPS - n_events
        padding = np.zeros((pad_len, 3), dtype='float32')
        features = np.vstack([padding, features])
        mask = np.concatenate([np.zeros(pad_len, dtype='bool'), np.ones(n_events, dtype='bool')])

    # 7. Normalize
    # physical_code normalization
    features[:, 0] = (features[:, 0] - STATS['physical_code']['mean']) / STATS['physical_code']['std']
    # flight_time normalization
    features[:, 1] = (features[:, 1] - STATS['flight_time']['mean']) / STATS['flight_time']['std']
    # text_length normalization
    features[:, 2] = (features[:, 2] - STATS['text_length']['mean']) / STATS['text_length']['std']

    # 8. Re-zero padded positions
    features[~mask] = 0.0

    # Reshape for model input (batch_size=1)
    return features.reshape(1, MAX_TIMESTEPS, 3), mask.reshape(1, MAX_TIMESTEPS)

def predict(participant_id: str, events: list[dict]) -> dict:
    """
    Runs real-time authentication for a participant based on a batch of events.
    
    Returns:
        dict: {
            "score": float | None,
            "verdict": "genuine" | "impostor" | "uncertain" | "insufficient_data",
            "keystrokes": int
        }
    """
    keydown_events = [e for e in events if e.get('event_type') == 'keydown']
    n_keydown = len(keydown_events)
    
    if n_keydown < MIN_KEYDOWN_EVENTS:
        return {
            "score": None,
            "verdict": "insufficient_data",
            "keystrokes": n_keydown
        }
    
    try:
        model = get_model(participant_id)
    except FileNotFoundError:
        # If model doesn't exist, we can't authenticate. 
        # In a real system we might fallback or return an error.
        return {
            "score": None,
            "verdict": "model_not_found",
            "keystrokes": n_keydown
        }

    X, M = preprocess_events(events)
    
    # Run inference
    # Note: Transformer model expects two inputs [sequence, mask]
    prediction = model.predict([X, M], verbose=0)
    score = float(prediction[0][0])
    
    # Verdict thresholds
    if score >= 0.65:
        verdict = "genuine"
    elif score <= 0.35:
        verdict = "impostor"
    else:
        verdict = "uncertain"
        
    return {
        "score": score,
        "verdict": verdict,
        "keystrokes": n_keydown
    }
