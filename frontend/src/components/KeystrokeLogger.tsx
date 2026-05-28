import React, { useEffect, useRef, useState, useCallback } from 'react';
import Editor, { type Monaco, type OnMount } from '@monaco-editor/react';
import { v4 as uuidv4 } from 'uuid';
import api from '../api';

interface KeystrokeEvent {
  key: string;
  physical_code: string;
  event_type: string;
  timestamp: number;
  cursor_position: number;
  text_length: number;
  is_auto_repeat: boolean;
  is_modifier: boolean;
  event_sequence: number;
}

interface KeystrokeLoggerProps {
  sessionId: string;
  taskId: number;
  onKeystrokeChange?: (count: number, currentText: string) => void;
}

interface SyncInfo {
  perf_now: number;
  date_now: number;
}

interface KeystrokeBatchPayload {
  session_id: string;
  batch_id: string;
  events: KeystrokeEvent[];
  sync?: SyncInfo;
}

interface IMonacoKeyboardEvent {
  browserEvent: KeyboardEvent;
  keyCode: number;
  ctrlKey: boolean;
  metaKey: boolean;
  preventDefault(): void;
  stopPropagation(): void;
}

const BATCH_TIME_MS = 2000;
const BATCH_SIZE = 50;

const MODIFIER_KEYS = new Set(['Shift', 'Control', 'Alt', 'Meta', 'CapsLock']);

// IndexedDB Setup for research data persistence
const DB_NAME = 'KeystrokeData';
const STORE_NAME = 'pending_batches';

const initDB = (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'batch_id' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
};

const saveBatch = async (batch: KeystrokeBatchPayload) => {
  const db = await initDB();
  const tx = db.transaction(STORE_NAME, 'readwrite');
  tx.objectStore(STORE_NAME).put(batch);
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => reject(tx.error);
  });
};

const deleteBatch = async (batchId: string) => {
  const db = await initDB();
  const tx = db.transaction(STORE_NAME, 'readwrite');
  tx.objectStore(STORE_NAME).delete(batchId);
};

const getPendingBatches = async (): Promise<KeystrokeBatchPayload[]> => {
  const db = await initDB();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const store = tx.objectStore(STORE_NAME);
  const request = store.getAll();
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
};

const KeystrokeLogger: React.FC<KeystrokeLoggerProps> = ({ sessionId, onKeystrokeChange }) => {
  const [code, setCode] = useState('# Start typing your solution here...');
  const [syncStatus, setSyncStatus] = useState<'synced' | 'syncing' | 'offline'>('synced');
  const [authStatus, setAuthStatus] = useState<{
    verdict: 'genuine' | 'impostor' | 'uncertain' | 'insufficient_data' | 'model_not_found' | 'idle';
    score: number | null;
    keystrokes: number;
  }>({ verdict: 'idle', score: null, keystrokes: 0 });

  const eventBuffer = useRef<KeystrokeEvent[]>([]);
  const authBuffer = useRef<KeystrokeEvent[]>([]);
  const keystrokeCount = useRef<number>(0);
  const eventSequence = useRef<number>(0);
  const isFirstBatch = useRef<boolean>(true);
  const pressedKeys = useRef<Set<string>>(new Set());
  const beaconSignature = useRef<string | null>(null);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Monaco | null>(null);

  // Pattern to reset state when prop changes to avoid synchronous setState in useEffect
  const [prevSessionId, setPrevSessionId] = useState(sessionId);
  if (sessionId !== prevSessionId) {
    setPrevSessionId(sessionId);
    setAuthStatus({ verdict: 'idle', score: null, keystrokes: 0 });
    authBuffer.current = [];
    eventBuffer.current = [];
    keystrokeCount.current = 0;
    eventSequence.current = 0;
    isFirstBatch.current = true;
  }

  const flushBuffer = useCallback(async (useBeacon = false) => {
    if (eventBuffer.current.length === 0) return;

    const eventsToUpload = [...eventBuffer.current];
    eventBuffer.current = [];
    const batchId = uuidv4();
    const payload: KeystrokeBatchPayload = {
      session_id: sessionId,
      batch_id: batchId,
      events: eventsToUpload,
    };

    if (isFirstBatch.current) {
      payload.sync = {
        perf_now: performance.now(),
        date_now: Date.now(),
      };
      isFirstBatch.current = false;
    }

    if (useBeacon && beaconSignature.current) {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('access_token');
      const url = `${baseUrl}/keystrokes/beacon?signature=${beaconSignature.current}${token ? `&access_token=${token}` : ''}`;
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      navigator.sendBeacon(url, blob);
      return;
    }

    try {
      setSyncStatus('syncing');
      await saveBatch(payload); // Persist locally first
      await api.post('/keystrokes/batch', payload);
      await deleteBatch(batchId); // Clear on success
      setSyncStatus('synced');
    } catch (error) {
      console.error('Failed to upload keystrokes:', error);
      setSyncStatus('offline');
      // Events are safely in IndexedDB, will retry via sync effect
    }
  }, [sessionId]);

  // Background Sync Effect
  useEffect(() => {
    const syncPending = async () => {
      const pending = await getPendingBatches();
      if (pending.length === 0) return;

      setSyncStatus('syncing');
      for (const batch of pending) {
        try {
          await api.post('/keystrokes/batch', batch);
          await deleteBatch(batch.batch_id);
        } catch (err) {
          setSyncStatus('offline');
          return; // Stop trying if still offline
        }
      }
      setSyncStatus('synced');
    };

    const interval = setInterval(syncPending, 10000); // Retry every 10s
    return () => clearInterval(interval);
  }, []);

  const runAuthVerification = useCallback(async () => {
    const buffer = authBuffer.current;
    if (buffer.length < 10) {
      return;
    }

    try {
      const response = await api.post(`/authenticate/verify/${sessionId}`, { events: buffer });
      const { verdict, score, keystrokes } = response.data;
      setAuthStatus({ verdict, score, keystrokes });
    } catch (error) {
      console.error('Authentication verification failed:', error);
    }
  }, [sessionId]);

  useEffect(() => {
    // Fetch beacon signature
    const fetchSignature = async () => {
      try {
        const response = await api.get(`/session/${sessionId}/signature`);
        beaconSignature.current = response.data.signature;
      } catch (error) {
        console.error('Failed to fetch beacon signature:', error);
      }
    };
    fetchSignature();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        flushBuffer(true);
        pressedKeys.current.clear();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    const interval = setInterval(() => {
      flushBuffer();
    }, BATCH_TIME_MS);

    const authInterval = setInterval(() => {
      runAuthVerification();
    }, 30000);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      clearInterval(interval);
      clearInterval(authInterval);
      flushBuffer(true); // Final flush on unmount
    };
  }, [sessionId, runAuthVerification, flushBuffer]);

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    editor.onKeyDown((e: IMonacoKeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.keyCode === monaco.KeyCode.KeyC || e.keyCode === monaco.KeyCode.KeyV)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });

    const logEvent = (e: IMonacoKeyboardEvent, type: 'keydown' | 'keyup') => {
      const browserEvent = e.browserEvent;
      const key = browserEvent.key;
      const physical_code = browserEvent.code;

      if (type === 'keydown') {
        // Prevent auto-repeat events
        if (browserEvent.repeat || pressedKeys.current.has(key)) {
          return;
        }
        pressedKeys.current.add(key);
      } else if (type === 'keyup') {
        pressedKeys.current.delete(key);
      }

      const position = editorRef.current?.getPosition();
      const model = editorRef.current?.getModel();
      const cursorOffset = position && model ? model.getOffsetAt(position) : 0;
      const textLength = model ? model.getValueLength() : 0;
      const currentText = model ? model.getValue() : '';

      eventSequence.current += 1;
      const event: KeystrokeEvent = {
        key: key,
        physical_code: physical_code,
        event_type: type,
        timestamp: performance.now(),
        cursor_position: cursorOffset,
        text_length: textLength,
        is_auto_repeat: browserEvent.repeat || false,
        is_modifier: MODIFIER_KEYS.has(key),
        event_sequence: eventSequence.current,
      };

      eventBuffer.current.push(event);
      authBuffer.current.push(event);
      
      // Maintain rolling window in logEvent for memory efficiency
      if (authBuffer.current.length > 300) {
        authBuffer.current = authBuffer.current.slice(-300);
      }

      if (type === 'keydown') {
        keystrokeCount.current += 1;
      }
      
      if (onKeystrokeChange) {
        onKeystrokeChange(keystrokeCount.current, currentText);
      }

      if (eventBuffer.current.length >= BATCH_SIZE) {
        flushBuffer();
      }
    };

    editor.onKeyDown((e: IMonacoKeyboardEvent) => logEvent(e, 'keydown'));
    editor.onKeyUp((e: IMonacoKeyboardEvent) => logEvent(e, 'keyup'));
  };

  const getStatusConfig = () => {
    switch (authStatus.verdict) {
      case 'genuine':
        return { icon: '🛡', label: 'Verified', bgColor: '#e6f4ea', textColor: '#137333' };
      case 'impostor':
        return { icon: '🚫', label: 'Flagged', bgColor: '#fce8e6', textColor: '#c5221f' };
      case 'uncertain':
        return { icon: '⚠', label: 'Uncertain', bgColor: '#fef7e0', textColor: '#b06000' };
      case 'insufficient_data':
        return { icon: '⚠', label: 'Checking...', bgColor: '#fef7e0', textColor: '#b06000' };
      case 'model_not_found':
        return { icon: '🔒', label: 'Unavailable', bgColor: '#f1f3f4', textColor: '#5f6368' };
      default:
        return { icon: '🔒', label: 'Monitoring', bgColor: '#f1f3f4', textColor: '#5f6368' };
    }
  };

  const { icon, label, bgColor, textColor } = getStatusConfig();

  return (
    <div className="keystroke-logger-container" style={{ position: 'relative' }}>
      {sessionId && (
        <div style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          zIndex: 10,
          width: '120px',
          padding: '8px',
          borderRadius: '8px',
          fontSize: '12px',
          backgroundColor: bgColor,
          color: textColor,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
          transition: 'all 0.3s ease'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 'bold' }}>
            <span>{icon}</span>
            <span>{label}</span>
          </div>
          {authStatus.score !== null && (
            <div style={{ fontSize: '10px', marginTop: '2px', opacity: 0.8 }}>
              {Math.round(authStatus.score * 100)}% Match
            </div>
          )}
          <div style={{ 
            fontSize: '9px', 
            marginTop: '4px', 
            padding: '2px 6px', 
            borderRadius: '4px',
            backgroundColor: 'rgba(255,255,255,0.5)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
            <span style={{ 
              width: '6px', 
              height: '6px', 
              borderRadius: '50%', 
              backgroundColor: syncStatus === 'synced' ? '#34a853' : (syncStatus === 'syncing' ? '#fbbc05' : '#ea4335') 
            }}></span>
            {syncStatus.toUpperCase()}
          </div>
        </div>
      )}
      <Editor
        height="60vh"
        defaultLanguage="python"
        theme="vs-dark"
        value={code}
        onChange={(value) => setCode(value || '')}
        onMount={handleEditorDidMount}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          scrollBeyondLastLine: false,
          automaticLayout: true,
          wordBasedSuggestions: 'off',
          suggestOnTriggerCharacters: false,
          parameterHints: { enabled: false },
          quickSuggestions: false,
          snippetSuggestions: 'none',
          contextmenu: false,
          dragAndDrop: false,
        }}
      />
    </div>
  );
};

export default KeystrokeLogger;
