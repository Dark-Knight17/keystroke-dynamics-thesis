import React, { useEffect, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import { v4 as uuidv4 } from 'uuid';
import api from '../api';

type Monaco = any;

interface KeystrokeEvent {
  key: string;
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
  onKeystrokeChange?: (count: number) => void;
}

const BATCH_TIME_MS = 2000;
const BATCH_SIZE = 50;

const MODIFIER_KEYS = new Set(['Shift', 'Control', 'Alt', 'Meta', 'CapsLock']);

const KeystrokeLogger: React.FC<KeystrokeLoggerProps> = ({ sessionId, taskId: _taskId, onKeystrokeChange }) => {
  const [code, setCode] = useState('# Start typing your solution here...');
  const eventBuffer = useRef<KeystrokeEvent[]>([]);
  const keystrokeCount = useRef<number>(0);
  const eventSequence = useRef<number>(0);
  const pressedKeys = useRef<Set<string>>(new Set());
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<Monaco | null>(null);

  const flushBuffer = async (useBeacon = false) => {
    if (eventBuffer.current.length === 0) return;

    const eventsToUpload = [...eventBuffer.current];
    eventBuffer.current = [];
    const batchId = uuidv4();
    const payload = {
      session_id: sessionId,
      batch_id: batchId,
      events: eventsToUpload,
    };

    if (useBeacon) {
      const url = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/keystrokes/beacon`;
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

  useEffect(() => {
    eventSequence.current = 0; // Reset sequence on new session
    
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

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      clearInterval(interval);
      flushBuffer(true); // Final flush on unmount
    };
  }, [sessionId]);

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
      const key = e.browserEvent.key;

      if (type === 'keydown') {
        // Prevent auto-repeat events
        if (e.browserEvent.repeat || pressedKeys.current.has(key)) {
          return;
        }
        pressedKeys.current.add(key);
      } else if (type === 'keyup') {
        pressedKeys.current.delete(key);
      }

      const position = editor.getPosition();
      const model = editor.getModel();
      const cursorOffset = model ? model.getOffsetAt(position) : 0;
      const textLength = model ? model.getValueLength() : 0;

      eventSequence.current += 1;
      const event: KeystrokeEvent = {
        key: key,
        event_type: type,
        timestamp: performance.now(),
        cursor_position: cursorOffset,
        text_length: textLength,
        is_auto_repeat: e.browserEvent.repeat || false,
        is_modifier: MODIFIER_KEYS.has(key),
        event_sequence: eventSequence.current,
      };

      eventBuffer.current.push(event);

      if (type === 'keydown') {
        keystrokeCount.current += 1;
        if (onKeystrokeChange) {
          onKeystrokeChange(keystrokeCount.current);
        }
      }

      if (eventBuffer.current.length >= BATCH_SIZE) {
        flushBuffer();
      }
    };

    editor.onKeyDown((e: any) => logEvent(e, 'keydown'));
    editor.onKeyUp((e: any) => logEvent(e, 'keyup'));
  };

  return (
    <div className="keystroke-logger-container">
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
