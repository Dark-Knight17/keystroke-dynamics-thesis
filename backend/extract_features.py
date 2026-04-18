import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/keystroke_db")

def extract_features():
    engine = create_engine(DATABASE_URL)
    
    # 1. Load Data
    query = """
    SELECT 
        p.participant_id,
        e.session_id,
        e.key,
        e.event_type,
        e.timestamp,
        e.event_sequence
    FROM keystroke_events e
    JOIN sessions s ON e.session_id = s.session_id
    JOIN participants p ON s.participant_id = p.participant_id
    WHERE s.end_time IS NOT NULL
    ORDER BY e.session_id, e.event_sequence
    """
    df = pd.read_sql(query, engine)
    
    if df.empty:
        print("No data found for feature extraction.")
        return

    # 2. Calculate Latencies (Dwell Time and Flight Time)
    # Dwell Time: KeyUp - KeyDown for the same key instance
    # Flight Time: KeyDown(n) - KeyUp(n-1)
    
    features_list = []
    
    for session_id, session_df in df.groupby('session_id'):
        participant_id = session_df['participant_id'].iloc[0]
        
        # Calculate Dwell Times (Level 1)
        dwell_times = []
        keydowns = {}
        
        for _, row in session_df.iterrows():
            key = row['key']
            if row['event_type'] == 'keydown':
                keydowns[key] = row['timestamp']
            elif row['event_type'] == 'keyup' and key in keydowns:
                duration = row['timestamp'] - keydowns[key]
                # Filtering: 10ms < latency < 750ms
                if 10 <= duration <= 750:
                    dwell_times.append({'key': key, 'duration': duration})
                del keydowns[key]
        
        if not dwell_times:
            continue
            
        dwell_df = pd.DataFrame(dwell_times)
        
        # Level 0: Global average keypress time
        avg_l0 = dwell_df['duration'].mean()
        
        # Level 1: Specific key average times (Threshold: >= 5 occurrences)
        key_counts = dwell_df['key'].value_counts()
        valid_keys = key_counts[key_counts >= 5].index
        l1_features = dwell_df[dwell_df['key'].isin(valid_keys)].groupby('key')['duration'].mean().to_dict()
        
        # Digraphs (Level 2)
        # We need sequential keydowns for digraph flight time: KeyDown(n) - KeyDown(n-1) 
        # OR KeyDown(n) - KeyUp(n-1). Longi et al usually refers to digraph latencies.
        # We'll use KeyDown(n) - KeyDown(n-1) as a common digraph feature.
        
        digraphs = []
        last_keydown_time = None
        last_key = None
        
        for _, row in session_df[session_df['event_type'] == 'keydown'].iterrows():
            if last_keydown_time is not None:
                duration = row['timestamp'] - last_keydown_time
                if 10 <= duration <= 750:
                    digraphs.append({'digraph': f"{last_key}->{row['key']}", 'duration': duration})
            last_keydown_time = row['timestamp']
            last_key = row['key']
            
        digraph_df = pd.DataFrame(digraphs) if digraphs else pd.DataFrame(columns=['digraph', 'duration'])
        
        session_features = {
            'participant_id': participant_id,
            'session_id': session_id,
            'avg_l0': avg_l0
        }
        
        # Store for later processing
        features_list.append({
            'participant_id': participant_id,
            'session_id': session_id,
            'avg_l0': avg_l0,
            'l1_raw': l1_features,
            'l2_raw': digraph_df
        })

    # 3. Global Top 100 Digraphs
    all_digraphs = pd.concat([f['l2_raw'] for f in features_list]) if features_list else pd.DataFrame()
    if not all_digraphs.empty:
        top_100_digraphs = all_digraphs['digraph'].value_counts().head(100).index.tolist()
    else:
        top_100_digraphs = []

    # 4. Final Feature Matrix Construction
    final_rows = []
    for entry in features_list:
        row = {
            'participant_id': entry['participant_id'],
            'session_id': entry['session_id'],
            'level_0_avg': entry['avg_l0']
        }
        
        # Level 1 Imputation
        # We'll use a fixed set of common keys for Level 1 to ensure consistent columns
        # (e.g., alphanumerics and programming symbols)
        common_keys = list("abcdefghijklmnopqrstuvwxyz0123456789 {}()[]<>=/_")
        for k in common_keys:
            val = entry['l1_raw'].get(k, entry['avg_l0']) # Impute with L0
            row[f"l1_{k}"] = val
            
        # Level 2 Features (Only Top 100)
        l2_df = entry['l2_raw']
        if not l2_df.empty:
            l2_counts = l2_df['digraph'].value_counts()
            l2_avgs = l2_df.groupby('digraph')['duration'].mean()
            for dg in top_100_digraphs:
                if dg in l2_counts and l2_counts[dg] >= 5:
                    row[f"l2_{dg}"] = l2_avgs[dg]
                else:
                    row[f"l2_{dg}"] = entry['avg_l0'] # Impute with L0
        else:
            for dg in top_100_digraphs:
                row[f"l2_{dg}"] = entry['avg_l0']
                
        final_rows.append(row)
        
    result_df = pd.DataFrame(final_rows)
    
    # 5. Normalization (Min-Max Scaling)
    feature_cols = [c for k, c in enumerate(result_df.columns) if c not in ['participant_id', 'session_id']]
    for col in feature_cols:
        min_val = result_df[col].min()
        max_val = result_df[col].max()
        if max_val - min_val > 0:
            result_df[col] = (result_df[col] - min_val) / (max_val - min_val)
        else:
            result_df[col] = 0.0
            
    result_df.to_csv("features.csv", index=False)
    print(f"Feature extraction complete. Generated features.csv with {len(result_df)} sessions.")

if __name__ == "__main__":
    extract_features()
