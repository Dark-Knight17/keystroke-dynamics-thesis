import React, { useState, useEffect } from 'react';
import api from './api';
import Auth from './components/Auth';
import KeystrokeLogger from './components/KeystrokeLogger';
import './App.css';

interface Task {
  task_id: number;
  task_title: string;
  description: string;
  day: number;
  difficulty_level: string;
  expected_solution_length: number;
  is_completed: boolean;
}

interface Participant {
  participant_id: string;
  user_id: string;
  device_type: string;
  keyboard_layout: string;
  os: string;
  physical_keyboard_type?: string;
}

const App: React.FC = () => {
  const [userId, setUserId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [keystrokeCount, setKeystrokeCount] = useState(0);
  const [currentEditorText, setCurrentEditorText] = useState('');
  const [participant, setParticipant] = useState<Participant | null>(null);

  const fetchData = async () => {
    try {
      const tasksResponse = await api.get('/tasks');
      setTasks(tasksResponse.data);
      
      const participantResponse = await api.get(`/participant/${userId}`);
      setParticipant(participantResponse.data);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    }
  };

  useEffect(() => {
    if (userId) {
      fetchData();
    }
  }, [userId]);

  const handleStartSession = async (task: Task) => {
    try {
      const response = await api.post('/session/start', {
        task_id: task.task_id,
        device_type: participant?.device_type || navigator.userAgent,
        keyboard_layout: participant?.keyboard_layout || 'Standard QWERTY',
        os: participant?.os || navigator.platform
        });

      setSessionId(response.data.session_id);
      setSelectedTask(task);
      setKeystrokeCount(0);
    } catch (err: any) {
      console.error('Failed to start session:', err);
      const msg = err.response?.data?.detail || 'Could not start session. Please try again.';
      alert(msg);
    }
  };

  const handleEndSession = async () => {
    if (!sessionId) return;
    try {
      await api.post(`/session/complete/${sessionId}`, {
        final_editor_text: currentEditorText
      });
      setSessionId(null);
      setSelectedTask(null);
      setKeystrokeCount(0);
      setCurrentEditorText('');
      alert('Session ended successfully. Thank you!');
      fetchData(); // Refresh completion status
    } catch (err) {
      console.error('Failed to end session:', err);
    }
  };

  if (!userId) {
    return (
      <div className="App">
        <header style={{ textAlign: 'center', marginBottom: '3rem' }}>
          <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>Keystroke Dynamics</h1>
          <p style={{ fontSize: '1.1rem', maxWidth: '600px', margin: '0 auto' }}>
            A research platform for continuous authentication through programming patterns.
          </p>
        </header>
        <Auth onLogin={(id) => setUserId(id)} />
      </div>
    );
  }

  if (sessionId && selectedTask) {
    const isThresholdMet = keystrokeCount >= selectedTask.expected_solution_length;
    
    return (
      <div className="App">
        <div className="task-header">
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: '1.75rem', marginBottom: '1rem' }}>{selectedTask.task_title}</h2>
            <p style={{ whiteSpace: 'pre-wrap', fontSize: '1.05rem' }}>{selectedTask.description}</p>
          </div>
          <div style={{ textAlign: 'right', minWidth: '240px' }}>
            <div style={{ marginBottom: '1.5rem' }}>
              <p style={{ 
                fontWeight: '600', 
                color: isThresholdMet ? 'var(--anthropic-green)' : '#a63a2a',
                fontSize: '1.1rem',
                margin: 0
              }}>
                {isThresholdMet ? '✓ Minimum length met' : `Progress: ${keystrokeCount} / ${selectedTask.expected_solution_length}`}
              </p>
              <div style={{ 
                height: '6px', 
                width: '100%', 
                backgroundColor: 'var(--anthropic-light-gray)', 
                borderRadius: '3px',
                marginTop: '0.5rem',
                overflow: 'hidden'
              }}>
                <div style={{ 
                  height: '100%', 
                  width: `${Math.min(100, (keystrokeCount / selectedTask.expected_solution_length) * 100)}%`,
                  backgroundColor: isThresholdMet ? 'var(--anthropic-green)' : 'var(--anthropic-orange)',
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>
            <button 
              onClick={handleEndSession} 
              className={`btn ${isThresholdMet ? 'btn-primary' : 'btn-secondary'}`}
              disabled={!isThresholdMet}
              title={!isThresholdMet ? `Minimum ${selectedTask.expected_solution_length} keystrokes required` : ''}
              style={{ width: '100%' }}
            >
              Submit Solution
            </button>
          </div>
        </div>
        <KeystrokeLogger 
          sessionId={sessionId} 
          taskId={selectedTask.task_id} 
          onKeystrokeChange={(count, text) => {
            setKeystrokeCount(count);
            setCurrentEditorText(text);
          }}
        />
      </div>
    );
  }

  const groupedTasks = tasks.reduce((acc, task) => {
    const day = `Day ${task.day}`;
    if (!acc[day]) acc[day] = [];
    acc[day].push(task);
    return acc;
  }, {} as Record<string, Task[]>);

  const days = ['Day 1', 'Day 2', 'Day 3'];

  const isDayLocked = (dayNum: number): boolean => {
    if (dayNum <= 1) return false;
    return tasks.some(t => t.day < dayNum && !t.is_completed);
  };

  return (
    <div className="App">
      <header style={{ marginBottom: '3rem' }}>
        <h1 style={{ fontSize: '2.25rem' }}>Participant Dashboard</h1>
        <p style={{ fontSize: '1.1rem' }}>Welcome back. Please complete the tasks assigned for each day in order.</p>
      </header>
      
      <div className="day-columns">
        {days.map((dayLabel, idx) => {
          const dayNum = idx + 1;
          const locked = isDayLocked(dayNum);
          
          return (
            <div key={dayLabel} className={`day-column ${locked ? 'day-locked' : ''}`} style={{ opacity: locked ? 0.5 : 1 }}>
              <h2>
                {dayLabel}
                {locked && <span title="Complete previous days to unlock" style={{ fontSize: '1.1rem', opacity: 0.6 }}>🔒</span>}
              </h2>
              <div className="task-list">
                {(groupedTasks[dayLabel] || []).map((task) => (
                  <div 
                    key={task.task_id} 
                    className={`task-card ${locked ? 'task-locked' : ''} ${task.is_completed ? 'task-completed' : ''}`} 
                  >
                    {task.is_completed && <span style={{ position: 'absolute', top: '1.5rem', right: '1.5rem', color: 'var(--anthropic-green)', fontWeight: '700', fontSize: '0.75rem', letterSpacing: '0.05em' }}>✓ COMPLETED</span>}
                    <h3>{task.task_title.replace(/\[Day \d\] /, '')}</h3>
                    <p style={{ fontSize: '0.95rem' }}>
                      <strong>Difficulty:</strong> {task.difficulty_level}
                    </p>
                    <button
                      onClick={() => handleStartSession(task)}
                      className={`btn ${task.is_completed ? 'btn-secondary' : 'btn-primary'}`}
                      style={{ width: '100%' }}
                      disabled={locked}
                    >
                      {locked ? 'Locked' : (task.is_completed ? 'Redo Session' : 'Start Task')}
                    </button>
                  </div>
                ))}
                {(!groupedTasks[dayLabel] || groupedTasks[dayLabel].length === 0) && (
                  <p style={{ color: 'var(--anthropic-mid-gray)', fontStyle: 'italic' }}>No tasks assigned.</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <footer style={{ marginTop: '5rem', borderTop: '1px solid var(--anthropic-light-gray)', paddingTop: '2rem', textAlign: 'center' }}>
        <button
          onClick={() => setUserId(null)}
          className="btn btn-link"
        >
          Logout from session
        </button>
      </footer>
    </div>
  );
};

export default App;
