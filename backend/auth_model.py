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

@tf.keras.utils.register_keras_serializable()
class TransformerBlock(tf.keras.layers.Layer):
    """Single Pre-LN Transformer encoder block."""
    def __init__(self, d_model=64, num_heads=4, dff=128, dropout_rate=0.1, **kwargs):
        super().__init__(**kwargs)
        self.d_model = d_model
        self.num_heads = num_heads
        self.dff = dff
        self.dropout_rate = dropout_rate
        self.attn = tf.keras.layers.MultiHeadAttention(
            num_heads=num_heads, key_dim=d_model // num_heads, dropout=dropout_rate
        )
        self.ffn1 = tf.keras.layers.Dense(dff, activation='relu')
        self.ffn2 = tf.keras.layers.Dense(d_model)
        self.norm1 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.norm2 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.drop1 = tf.keras.layers.Dropout(dropout_rate)
        self.drop2 = tf.keras.layers.Dropout(dropout_rate)

    def build(self, input_shape):
        super().build(input_shape)

    def call(self, x, attention_mask=None, training=False):
        x_norm = self.norm1(x)
        attn_out = self.attn(
            query=x_norm, value=x_norm, key=x_norm,
            attention_mask=attention_mask,
            training=training
        )
        x = x + self.drop1(attn_out, training=training)
        x_norm = self.norm2(x)
        ffn_out = self.ffn2(self.drop2(self.ffn1(x_norm), training=training))
        x = x + ffn_out
        return x

    def get_config(self):
        config = super().get_config()
        config.update({
            "d_model": self.d_model,
            "num_heads": self.num_heads,
            "dff": self.dff,
            "dropout_rate": self.dropout_rate,
        })
        return config

@tf.keras.utils.register_keras_serializable()
class CLSTokenAndPosition(tf.keras.layers.Layer):
    """Encapsulates CLS token injection and Positional Embeddings."""
    def __init__(self, seq_len=301, d_model=64, dropout_rate=0.1, **kwargs):
        super().__init__(**kwargs)
        self.seq_len = seq_len
        self.d_model = d_model
        self.dropout_rate = dropout_rate
        self.pos_embedding = tf.keras.layers.Embedding(input_dim=seq_len, output_dim=d_model)
        self.dropout = tf.keras.layers.Dropout(dropout_rate)

    def build(self, input_shape):
        self.cls_token = self.add_weight(
            shape=(1, 1, self.d_model),
            initializer='zeros',
            trainable=True,
            name='cls_token'
        )
        super().build(input_shape)

    def call(self, x, training=False):
        batch_size = tf.shape(x)[0]
        cls_tokens = tf.tile(self.cls_token, [batch_size, 1, 1])
        x = tf.concat([cls_tokens, x], axis=1)
        positions = tf.range(start=0, limit=self.seq_len, delta=1)
        x = x + self.pos_embedding(positions)
        return self.dropout(x, training=training)

    def get_config(self):
        config = super().get_config()
        config.update({
            "seq_len": self.seq_len,
            "d_model": self.d_model,
            "dropout_rate": self.dropout_rate,
        })
        return config

@tf.keras.utils.register_keras_serializable()
class FormatAttentionMask(tf.keras.layers.Layer):
    """Encapsulates attention mask formatting."""
    def call(self, mask_input):
        batch_size = tf.shape(mask_input)[0]
        cls_mask = tf.ones((batch_size, 1), dtype=tf.bool)
        full_mask = tf.concat([cls_mask, mask_input], axis=1)
        return full_mask[:, tf.newaxis, tf.newaxis, :]

@tf.keras.utils.register_keras_serializable()
class GetItem(tf.keras.layers.Layer):
    """Simple layer to extract CLS token."""
    def call(self, x, *args, **kwargs):
        return x[:, 0, :]

MAX_TIMESTEPS = 300
MIN_KEYDOWN_EVENTS = 10

@functools.lru_cache(maxsize=5)
def get_model(participant_id: str):
    """
    Loads a Transformer model for a specific participant from the disk.
    Standard Keras 3 loading for environment parity.
    """
    model_path = Path(__file__).parent / "models" / f"transformer_{participant_id}.keras"
    if not model_path.exists():
        raise FileNotFoundError(f"Model for participant {participant_id} not found at {model_path}")
    
    return tf.keras.models.load_model(str(model_path))

def preprocess_events(events: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """
    Prepares raw keystroke events for Transformer inference.
    """
    keydown_events = [e for e in events if e.get('event_type') == 'keydown']
    keydown_events.sort(key=lambda x: x['timestamp'])
    
    if not keydown_events:
        return np.zeros((1, MAX_TIMESTEPS, 3), dtype='float32'), np.zeros((1, MAX_TIMESTEPS), dtype='bool')

    timestamps = np.array([e['timestamp'] for e in keydown_events])
    flight_times = np.diff(timestamps, prepend=timestamps[0])
    flight_times = np.clip(flight_times, 0, 2000).astype('float32')

    encoded_codes = [VOCAB.get(e.get('physical_code'), 0) for e in keydown_events]
    text_lengths = [e.get('text_length', 0) for e in keydown_events]
    features = np.stack([encoded_codes, flight_times, text_lengths], axis=1).astype('float32')

    n_events = len(features)
    if n_events > MAX_TIMESTEPS:
        features = features[-MAX_TIMESTEPS:]
        mask = np.ones(MAX_TIMESTEPS, dtype='bool')
    else:
        pad_len = MAX_TIMESTEPS - n_events
        padding = np.zeros((pad_len, 3), dtype='float32')
        features = np.vstack([padding, features])
        mask = np.concatenate([np.zeros(pad_len, dtype='bool'), np.ones(n_events, dtype='bool')])

    features[:, 0] = (features[:, 0] - STATS['physical_code']['mean']) / STATS['physical_code']['std']
    features[:, 1] = (features[:, 1] - STATS['flight_time']['mean']) / STATS['flight_time']['std']
    features[:, 2] = (features[:, 2] - STATS['text_length']['mean']) / STATS['text_length']['std']

    features[~mask] = 0.0
    return features.reshape(1, MAX_TIMESTEPS, 3), mask.reshape(1, MAX_TIMESTEPS)

def predict(participant_id: str, events: list[dict]) -> dict:
    """
    Runs real-time authentication for a participant based on a batch of events.
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
    except Exception as e:
        print(f"Model Loading Error for {participant_id}: {str(e)}")
        return {
            "score": None,
            "verdict": "model_not_found",
            "keystrokes": n_keydown
        }

    X, M = preprocess_events(events)
    prediction = model.predict([X, M], verbose=0)
    score = float(prediction[0][0])
    
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
