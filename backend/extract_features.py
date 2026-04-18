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
        e.event_sequence,
        t.expected_solution_length,
        s.total_keystrokes
    FROM keystroke_events e
    JOIN sessions s ON e.session_id = s.session_id
    JOIN participants p ON s.participant_id = p.participant_id
    JOIN programming_tasks t ON s.task_id = t.task_id
    WHERE s.end_time IS NOT NULL
    ORDER BY e.session_id, e.event_sequence
    """
    df = pd.read_sql(query, engine)
    
    if df.empty:
        print("No data found for feature extraction.")
        return

    # 2. Process Sessions
    features_list = []
    
    for session_id, session_df in df.groupby('session_id'):
        participant_id = session_df['participant_id'].iloc[0]
        expected_len = session_df['expected_solution_length'].iloc[0]
        total_ks = session_df['total_keystrokes'].iloc[0]
        
        # Session Quality Gate: Drop if total keystrokes < 80% of expected
        if total_ks < (0.8 * expected_len):
            continue
        
        # Calculate Dwell Times (Level 1)
        dwell_times = []
        keydowns = {} # key -> timestamp
        
        # We also need sequential events for digraphs
        events_processed = [] # {key, type, time}
        
        for _, row in session_df.iterrows():
            key = row['key']
            etype = row['event_type']
            ts = row['timestamp']
            
            events_processed.append({'key': key, 'type': etype, 'time': ts})
            
            if etype == 'keydown':
                keydowns[key] = ts
            elif etype == 'keyup' and key in keydowns:
                duration = ts - keydowns[key]
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
        
        # Digraphs (Level 2) - KD-KD, KU-KD, KD-KU
        digraphs_kdkd = []
        digraphs_kukd = []
        digraphs_kdku = []
        
        # We need pairs of keys. We iterate through keydowns for KD-KD.
        # For others, we need sequential context.
        kd_events = [e for e in events_processed if e['type'] == 'keydown']
        for i in range(1, len(kd_events)):
            e1, e2 = kd_events[i-1], kd_events[i]
            dur = e2['time'] - e1['time']
            if 10 <= dur <= 750:
                digraphs_kdkd.append({'dg': f"{e1['key']}->{e2['key']}", 'dur': dur})
        
        # For KU-KD and KD-KU, we need the original sequence
        for i in range(1, len(events_processed)):
            e1, e2 = events_processed[i-1], events_processed[i]
            
            # KU-KD: KeyUp(n-1) -> KeyDown(n)
            if e1['type'] == 'keyup' and e2['type'] == 'keydown':
                dur = e2['time'] - e1['time']
                if 10 <= dur <= 750:
                    digraphs_kukd.append({'dg': f"{e1['key']}->{e2['key']}", 'dur': dur})
            
            # KD-KU: KeyDown(n) -> KeyUp(n) is Dwell Time (handled in L1)
            # Standard Benchmark KD-KU usually means KeyDown(n) -> KeyUp(n+1) or similar.
            # Actually, KD-KU usually refers to KeyDown(n-1) -> KeyUp(n).
            if e1['type'] == 'keydown' and e2['type'] == 'keyup':
                # Only if they are DIFFERENT keys (otherwise it's dwell)
                if e1['key'] != e2['key']:
                    dur = e2['time'] - e1['time']
                    if 10 <= dur <= 750:
                        digraphs_kdku.append({'dg': f"{e1['key']}->{e2['key']}", 'dur': dur})

        features_list.append({
            'participant_id': participant_id,
            'session_id': session_id,
            'avg_l0': avg_l0,
            'l1_raw': l1_features,
            'kdkd': pd.DataFrame(digraphs_kdkd) if digraphs_kdkd else pd.DataFrame(columns=['dg', 'dur']),
            'kukd': pd.DataFrame(digraphs_kukd) if digraphs_kukd else pd.DataFrame(columns=['dg', 'dur']),
            'kdku': pd.DataFrame(digraphs_kdku) if digraphs_kdku else pd.DataFrame(columns=['dg', 'dur'])
        })

    # 3. Global Top 100 Digraphs (KD-KD variant as baseline for selection)
    all_kdkd = pd.concat([f['kdkd'] for f in features_list]) if features_list else pd.DataFrame()
    if not all_kdkd.empty:
        top_100_dgs = all_kdkd['dg'].value_counts().head(100).index.tolist()
    else:
        top_100_dgs = []

    # 4. Final Feature Matrix (No Normalization)
    final_rows = []
    common_keys = list("abcdefghijklmnopqrstuvwxyz0123456789 {}()[]<>=/_")
    
    for entry in features_list:
        row = {
            'participant_id': entry['participant_id'],
            'session_id': entry['session_id'],
            'level_0_avg': entry['avg_l0']
        }
        
        # Level 1
        for k in common_keys:
            row[f"l1_{k}"] = entry['l1_raw'].get(k, entry['avg_l0'])
            
        # Level 2 (3 variants for top 100)
        for dg in top_100_dgs:
            # KD-KD
            df_v = entry['kdkd']
            row[f"l2_kdkd_{dg}"] = df_v[df_v['dg'] == dg]['dur'].mean() if dg in df_v['dg'].values and len(df_v[df_v['dg'] == dg]) >= 5 else entry['avg_l0']
            
            # KU-KD
            df_v = entry['kukd']
            row[f"l2_kukd_{dg}"] = df_v[df_v['dg'] == dg]['dur'].mean() if dg in df_v['dg'].values and len(df_v[df_v['dg'] == dg]) >= 5 else entry['avg_l0']
            
            # KD-KU
            df_v = entry['kdku']
            row[f"l2_kdku_{dg}"] = df_v[df_v['dg'] == dg]['dur'].mean() if dg in df_v['dg'].values and len(df_v[df_v['dg'] == dg]) >= 5 else entry['avg_l0']
                
        final_rows.append(row)
        
    result_df = pd.DataFrame(final_rows)
    result_df.to_csv("features.csv", index=False)
    print(f"Feature extraction complete. Generated features.csv with {len(result_df)} sessions. (Raw ms, no normalization)")

if __name__ == "__main__":
    extract_features()
