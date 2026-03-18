import React, { useEffect, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import api from '../api';

type Monaco = any;

interface KeystrokeEvent {
  key: string;
  event_type: string;
  timestamp: number;
  cursor_position: number;
  text_length: number;
  is_auto_repeat: boolean;
}

interface KeystrokeLoggerProps {
  sessionId: string;
  taskId: number;
  onKeystrokeChange?: (count: number) => void;
}

const BATCH_TIME_MS = 2000;
const BATCH_SIZE = 50;

const KeystrokeLogger: React.FC<KeystrokeLoggerProps> = ({ sessionId, taskId, onKeystrokeChange }) => {
  const [code, setCode] = useState('# Start typing your solution here...');
  const eventBuffer = useRef<KeystrokeEvent[]>([]);
  const keystrokeCount = useRef<number>(0);
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<Monaco | null>(null);

  const flushBuffer = async () => {
    if (eventBuffer.current.length === 0) return;

    const eventsToUpload = [...eventBuffer.current];
    eventBuffer.current = [];

    try {
      await api.post('/keystrokes/batch', {
        session_id: sessionId,
        events: eventsToUpload,
      });
    } catch (error) {
      console.error('Failed to upload keystrokes:', error);
      eventBuffer.current = [...eventsToUpload, ...eventBuffer.current];
    }
  };

  useEffect(() => {
    const interval = setInterval(() => {
      flushBuffer();
    }, BATCH_TIME_MS);

    return () => {
      clearInterval(interval);
      flushBuffer();
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
      const position = editor.getPosition();
      const model = editor.getModel();
      const cursorOffset = model ? model.getOffsetAt(position) : 0;
      const textLength = model ? model.getValueLength() : 0;

      const event: KeystrokeEvent = {
        key: e.browserEvent.key,
        event_type: type,
        timestamp: performance.now(),
        cursor_position: cursorOffset,
        text_length: textLength,
        is_auto_repeat: e.browserEvent.repeat || false,
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
