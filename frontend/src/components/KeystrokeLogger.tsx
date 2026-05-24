import React, { useEffect, useRef, useState, useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { v4 as uuidv4 } from 'uuid';
import api from '../api';

type Monaco = any;

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

const BATCH_TIME_MS = 2000;
const BATCH_SIZE = 50;

const MODIFIER_KEYS = new Set(['Shift', 'Control', 'Alt', 'Meta', 'CapsLock']);

const KeystrokeLogger: React.FC<KeystrokeLoggerProps> = ({ sessionId, taskId: _taskId, onKeystrokeChange }) => {
  const [code, setCode] = useState('# Start typing your solution here...');
  const [authStatus, setAuthStatus] = useState<{
    verdict: 'genuine' | 'impostor' | 'uncertain' | 'insufficient_data' | 'model_not_found' | 'idle';
    score: number | null;
    keystrokes: number;
  }>({ verdict: 'idle', score: null, keystrokes: 0 });

  const eventBuffer = useRef<KeystrokeEvent[]>([]);
  const keystrokeCount = useRef<number>(0);
  const eventSequence = useRef<number>(0);
  const isFirstBatch = useRef<boolean>(true);
  const pressedKeys = useRef<Set<string>>(new Set());
  const beaconSignature = useRef<string | null>(null);
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<Monaco | null>(null);

  const flushBuffer = async (useBeacon = false) => {
    if (eventBuffer.current.length === 0) return;

    const eventsToUpload = [...eventBuffer.current];
    eventBuffer.current = [];
    const batchId = uuidv4();
    const payload: any = {
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
      await api.post('/keystrokes/batch', payload);
    } catch (error) {
      console.error('Failed to upload keystrokes:', error);
      // Put back at the beginning of buffer
      eventBuffer.current = [...eventsToUpload, ...eventBuffer.current];
    }
  };

  const runAuthVerification = useCallback(async () => {
    const buffer = eventBuffer.current;
    if (buffer.length < 10) {
      setAuthStatus(prev => ({ ...prev, verdict: 'insufficient_data' }));
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
    eventSequence.current = 0; // Reset sequence on new session
    isFirstBatch.current = true; // Reset sync flag for new session
    setAuthStatus({ verdict: 'idle', score: null, keystrokes: 0 }); // Reset auth status
    
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
  }, [sessionId, runAuthVerification]);

  const handleEditorDidMount = (editor: any, monaco: Monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    editor.onKeyDown((e: any) => {
      if ((e.ctrlKey || e.metaKey) && (e.keyCode === monaco.KeyCode.KeyC || e.keyCode === monaco.KeyCode.KeyV)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });

    const logEvent = (e: any, type: string) => {
      const browserEvent = e.browserEvent as KeyboardEvent;
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
      const cursorOffset = model ? model.getOffsetAt(position) : 0;
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

    editor.onKeyDown((e: any) => logEvent(e, 'keydown'));
    editor.onKeyUp((e: any) => logEvent(e, 'keyup'));
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
