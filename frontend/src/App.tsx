import React, { useState, useEffect } from 'react';
import api from './api';
import Auth from './components/Auth';
import KeystrokeLogger from './components/KeystrokeLogger';

interface Task {
  task_id: number;
  task_title: string;
  description: string;
  difficulty_level: string;
}

const App: React.FC = () => {
  const [userId, setUserId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    // Seed tasks if they don't exist in backend (simplified)
    // In production, we'd fetch them
    setTasks([
      {
        task_id: 1,
        task_title: 'Fibonacci Sequence',
        description: 'Write a function that returns the n-th Fibonacci number.',
        difficulty_level: 'Easy',
      },
      {
        task_id: 2,
        task_title: 'String Reversal',
        description: 'Implement a function that reverses a string.',
        difficulty_level: 'Easy',
      },
    ]);
  }, []);

  const handleStartSession = async (task: Task) => {
    try {
      const response = await api.post('/session/start', {
        task_id: task.task_id,
        device_type: navigator.userAgent,
        keyboard_layout: 'Standard QWERTY', // Simplified
        os: navigator.platform,
      }, {
        params: { user_id: userId },
      });
      setSessionId(response.data.session_id);
      setSelectedTask(task);
    } catch (err) {
      console.error('Failed to start session:', err);
      alert('Could not start session. Please try again.');
    }
  };

  const handleEndSession = async () => {
    if (!sessionId) return;
    try {
      await api.post(`/session/end/${sessionId}`);
      setSessionId(null);
      setSelectedTask(null);
      alert('Session ended successfully. Thank you!');
    } catch (err) {
      console.error('Failed to end session:', err);
    }
  };

  if (!userId) {
    return (
      <div className="App" style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
        <h1 style={{ textAlign: 'center' }}>Keystroke Dynamics Platform</h1>
        <Auth onLogin={(id) => setUserId(id)} />
      </div>
    );
  }

  if (sessionId && selectedTask) {
    return (
      <div className="App" style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h2>{selectedTask.task_title}</h2>
            <p>{selectedTask.description}</p>
          </div>
          <button
            onClick={handleEndSession}
            style={{ padding: '0.75rem 1.5rem', background: '#dc3545', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            End Session
          </button>
        </div>
        <KeystrokeLogger sessionId={sessionId} taskId={selectedTask.task_id} />
      </div>
    );
  }

  return (
    <div className="App" style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>Welcome Participant</h1>
      <p>Select a task to begin your typing session.</p>
      <div className="task-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem', marginTop: '2rem' }}>
        {tasks.map((task) => (
          <div key={task.task_id} style={{ border: '1px solid #ddd', padding: '1.5rem', borderRadius: '8px', background: '#fcfcfc' }}>
            <h3>{task.task_title}</h3>
            <p style={{ color: '#666' }}>{task.description}</p>
            <p><strong>Difficulty:</strong> {task.difficulty_level}</p>
            <button
              onClick={() => handleStartSession(task)}
              style={{ padding: '0.5rem 1rem', background: '#28a745', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', marginTop: '1rem' }}
            >
              Start Session
            </button>
          </div>
        ))}
      </div>
      <button
        onClick={() => setUserId(null)}
        style={{ marginTop: '2rem', background: 'none', border: 'none', color: '#dc3545', textDecoration: 'underline', cursor: 'pointer' }}
      >
        Logout
      </button>
    </div>
  );
};

export default App;
