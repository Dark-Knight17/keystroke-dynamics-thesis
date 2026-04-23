import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/keystroke_db")

def extract_features():
    engine = create_engine(DATABASE_URL)
    
    # 1. Load Data with epoch_anchor
    query = """
    SELECT 
        p.participant_id,
        e.session_id,
        e.key,
        e.event_type,
        e.timestamp,
        e.event_sequence,
        t.expected_solution_length,
        s.total_keystrokes,
        s.epoch_anchor,
        s.final_editor_text
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

    # Convert relative timestamps to absolute
    df['abs_timestamp'] = df['epoch_anchor'] + df['timestamp']
    
    # Save a copy with absolute timestamps for research
    df.to_csv("events_with_abs_timestamps.csv", index=False)

    # 2. Process Sessions
    features_list = []
    
    all_kd_digraphs = []
    all_trigraphs = []

    for session_id, session_df in df.groupby('session_id'):
        participant_id = session_df['participant_id'].iloc[0]
        expected_len = session_df['expected_solution_length'].iloc[0]
        total_ks = session_df['total_keystrokes'].iloc[0]
        final_text = session_df['final_editor_text'].iloc[0] or ""
        
        # Dual Quality Gate: keystroke threshold (80%) OR final text length (50%)
        if (total_ks < 0.8 * expected_len) or (len(final_text.strip()) < 0.5 * expected_len):
            continue
        
        # CPM calculation
        time_span_ms = session_df['timestamp'].max() - session_df['timestamp'].min()
        typing_speed_cpm = (total_ks / time_span_ms * 60000) if time_span_ms > 0 else 0
        
        dwell_times = []
        keydowns = {} 
        events_processed = [] 
        
        backspace_count = 0

        for _, row in session_df.iterrows():
            key = row['key']
            etype = row['event_type']
            ts = row['timestamp']
            
            events_processed.append({'key': key, 'type': etype, 'time': ts})
            
            if etype == 'keydown':
                keydowns[key] = ts
                if key == 'Backspace':
                    backspace_count += 1
            elif etype == 'keyup' and key in keydowns:
                duration = ts - keydowns[key]
                if 10 <= duration <= 750:
                    dwell_times.append({'key': key, 'duration': duration})
                del keydowns[key]
        
        if not dwell_times:
            continue
            
        dwell_df = pd.DataFrame(dwell_times)
        
        # Dense Features (Macro-level)
        mean_dwell = dwell_df['duration'].mean()
        std_dwell = dwell_df['duration'].std()
        backspace_ratio = backspace_count / total_ks if total_ks > 0 else 0
        
        # N-grams & Flight Times
        digraphs_kdkd = []
        digraphs_kukd = []
        digraphs_kdku = []
        trigraphs = []
        
        kd_events = [e for e in events_processed if e['type'] == 'keydown']
        
        # Flight times KD-KD for mean flight time and pauses
        flight_times = []
        for i in range(1, len(kd_events)):
            e1, e2 = kd_events[i-1], kd_events[i]
            dur = e2['time'] - e1['time']
            if 10 <= dur <= 5000: # Broad range for flight time analysis
                flight_times.append(dur)
                if 10 <= dur <= 750:
                    dg_str = f"{e1['key']}->{e2['key']}"
                    digraphs_kdkd.append({'dg': dg_str, 'dur': dur})
                    all_kd_digraphs.append(dg_str)
        
        mean_flight = np.mean(flight_times) if flight_times else 0
        pause_frequency = len([f for f in flight_times if f > 500])

        # Trigraphs
        for i in range(2, len(kd_events)):
            e1, e2, e3 = kd_events[i-2], kd_events[i-1], kd_events[i]
            dur = e3['time'] - e1['time']
            if 20 <= dur <= 1500:
                tg_str = f"{e1['key']}->{e2['key']}->{e3['key']}"
                trigraphs.append({'tg': tg_str, 'dur': dur})
                all_trigraphs.append(tg_str)

        # Other Digraphs
        for i in range(1, len(events_processed)):
            e1, e2 = events_processed[i-1], events_processed[i]
            if e1['type'] == 'keyup' and e2['type'] == 'keydown':
                dur = e2['time'] - e1['time']
                if 10 <= dur <= 750:
                    digraphs_kukd.append({'dg': f"{e1['key']}->{e2['key']}", 'dur': dur})
            if e1['type'] == 'keydown' and e2['type'] == 'keyup' and e1['key'] != e2['key']:
                dur = e2['time'] - e1['time']
                if 10 <= dur <= 750:
                    digraphs_kdku.append({'dg': f"{e1['key']}->{e2['key']}", 'dur': dur})

        # Level 1 per-key features
        key_counts = dwell_df['key'].value_counts()
        valid_keys = key_counts[key_counts >= 5].index
        l1_features = dwell_df[dwell_df['key'].isin(valid_keys)].groupby('key')['duration'].mean().to_dict()

        features_list.append({
            'participant_id': participant_id,
            'session_id': session_id,
            'typing_speed_cpm': typing_speed_cpm,
            'mean_dwell_time': mean_dwell,
            'std_dwell_time': std_dwell,
            'mean_flight_time': mean_flight,
            'backspace_ratio': backspace_ratio,
            'pause_frequency': pause_frequency,
            'l1_raw': l1_features,
            'kdkd': pd.DataFrame(digraphs_kdkd) if digraphs_kdkd else pd.DataFrame(columns=['dg', 'dur']),
            'kukd': pd.DataFrame(digraphs_kukd) if digraphs_kukd else pd.DataFrame(columns=['dg', 'dur']),
            'kdku': pd.DataFrame(digraphs_kdku) if digraphs_kdku else pd.DataFrame(columns=['dg', 'dur']),
            'trigraphs': pd.DataFrame(trigraphs) if trigraphs else pd.DataFrame(columns=['tg', 'dur'])
        })

    # 3. Top N-grams selection
    top_100_dgs = pd.Series(all_kd_digraphs).value_counts().head(100).index.tolist()
    top_50_tgs = pd.Series(all_trigraphs).value_counts().head(50).index.tolist()

    # 4. Final Matrix
    final_rows = []
    common_keys = list("abcdefghijklmnopqrstuvwxyz0123456789 {}()[]<>=/_")
    
    for entry in features_list:
        row = {
            'participant_id': entry['participant_id'],
            'session_id': entry['session_id'],
            'typing_speed_cpm': entry['typing_speed_cpm'],
            'mean_dwell_time': entry['mean_dwell_time'],
            'std_dwell_time': entry['std_dwell_time'],
            'mean_flight_time': entry['mean_flight_time'],
            'backspace_ratio': entry['backspace_ratio'],
            'pause_frequency': entry['pause_frequency']
        }
        
        for k in common_keys:
            row[f"l1_{k}"] = entry['l1_raw'].get(k, np.nan)
            
        for dg in top_100_dgs:
            df_v = entry['kdkd']
            row[f"l2_kdkd_{dg}"] = df_v[df_v['dg'] == dg]['dur'].mean() if dg in df_v['dg'].values and len(df_v[df_v['dg'] == dg]) >= 5 else np.nan
            df_v = entry['kukd']
            row[f"l2_kukd_{dg}"] = df_v[df_v['dg'] == dg]['dur'].mean() if dg in df_v['dg'].values and len(df_v[df_v['dg'] == dg]) >= 5 else np.nan
            df_v = entry['kdku']
            row[f"l2_kdku_{dg}"] = df_v[df_v['dg'] == dg]['dur'].mean() if dg in df_v['dg'].values and len(df_v[df_v['dg'] == dg]) >= 5 else np.nan
        
        for tg in top_50_tgs:
            df_v = entry['trigraphs']
            row[f"l2_tg_{tg}"] = df_v[df_v['tg'] == tg]['dur'].mean() if tg in df_v['tg'].values and len(df_v[df_v['tg'] == tg]) >= 3 else np.nan
                
        final_rows.append(row)
        
    result_df = pd.DataFrame(final_rows)
    result_df.to_csv("features.csv", index=False)
    print(f"Feature extraction complete. Generated features.csv with {len(result_df)} sessions.")

if __name__ == "__main__":
    extract_features()
