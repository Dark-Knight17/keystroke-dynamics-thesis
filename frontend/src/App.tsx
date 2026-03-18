import React, { useState, useEffect } from 'react';
import api from './api';
import Auth from './components/Auth';
import KeystrokeLogger from './components/KeystrokeLogger';
import './App.css';

interface Task {
  task_id: number;
  task_title: string;
  description: string;
  difficulty_level: string;
  expected_solution_length: number;
}

const App: React.FC = () => {
  const [userId, setUserId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [keystrokeCount, setKeystrokeCount] = useState(0);

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const response = await api.get('/tasks');
        setTasks(response.data);
      } catch (err) {
        console.error('Failed to fetch tasks:', err);
      }
    };
    if (userId) {
      fetchTasks();
    }
  }, [userId]);

  const handleStartSession = async (task: Task) => {
    try {
      const response = await api.post('/session/start', {
        task_id: task.task_id,
        device_type: navigator.userAgent,
        keyboard_layout: 'Standard QWERTY',
        os: navigator.platform,
      }, {
        params: { user_id: userId },
      });
      setSessionId(response.data.session_id);
      setSelectedTask(task);
      setKeystrokeCount(0);
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
      setKeystrokeCount(0);
      alert('Session ended successfully. Thank you!');
    } catch (err) {
      console.error('Failed to end session:', err);
    }
  };

  if (!userId) {
    return (
      <div className="App">
        <h1 style={{ textAlign: 'center' }}>Keystroke Dynamics Platform</h1>
        <Auth onLogin={(id) => setUserId(id)} />
      </div>
    );
  }

  if (sessionId && selectedTask) {
    const isThresholdMet = keystrokeCount >= selectedTask.expected_solution_length;
    
    return (
      <div className="App">
        <div className="task-header">
          <div>
            <h2>{selectedTask.task_title}</h2>
            <p style={{ whiteSpace: 'pre-wrap' }}>{selectedTask.description}</p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ fontWeight: 'bold', color: isThresholdMet ? '#4CAF50' : '#f44336' }}>
              Keystrokes: {keystrokeCount} / {selectedTask.expected_solution_length} required
            </p>
            <button 
              onClick={handleEndSession} 
              className={`btn ${isThresholdMet ? 'btn-danger' : 'btn-secondary'}`}
              disabled={!isThresholdMet}
              title={!isThresholdMet ? `Minimum ${selectedTask.expected_solution_length} keystrokes required` : ''}
            >
              End Session
            </button>
          </div>
        </div>
        <KeystrokeLogger 
          sessionId={sessionId} 
          taskId={selectedTask.task_id} 
          onKeystrokeChange={(count) => setKeystrokeCount(count)}
        />
      </div>
    );
  }

  const groupedTasks = tasks.reduce((acc, task) => {
    const dayMatch = task.task_title.match(/\[Day (\d)\]/);
    const day = dayMatch ? `Day ${dayMatch[1]}` : 'Other';
    if (!acc[day]) acc[day] = [];
    acc[day].push(task);
    return acc;
  }, {} as Record<string, Task[]>);

  const days = ['Day 1', 'Day 2', 'Day 3'];

  return (
    <div className="App">
      <h1>Research Participant Dashboard</h1>
      <p>Please complete the tasks assigned for each day in order.</p>
      
      <div className="day-columns" style={{ display: 'flex', gap: '2rem', marginTop: '2rem' }}>
        {days.map(day => (
          <div key={day} className="day-column" style={{ flex: 1 }}>
            <h2 style={{ borderBottom: '2px solid #333', paddingBottom: '0.5rem' }}>{day}</h2>
            <div className="task-list">
              {(groupedTasks[day] || []).map((task) => (
                <div key={task.task_id} className="task-card" style={{ marginBottom: '1rem', border: '1px solid #ddd', padding: '1rem', borderRadius: '8px' }}>
                  <h3 style={{ marginTop: 0, fontSize: '1.1rem' }}>{task.task_title.replace(/\[Day \d\] /, '')}</h3>
                  <p style={{ fontSize: '0.9rem', color: '#666' }}><strong>Difficulty:</strong> {task.difficulty_level}</p>
                  <button
                    onClick={() => handleStartSession(task)}
                    className="btn btn-success"
                    style={{ width: '100%', marginTop: '0.5rem' }}
                  >
                    Start Task
                  </button>
                </div>
              ))}
              {(!groupedTasks[day] || groupedTasks[day].length === 0) && (
                <p style={{ color: '#999', fontStyle: 'italic' }}>No tasks assigned.</p>
              )}
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={() => setUserId(null)}
        className="btn btn-link"
        style={{ marginTop: '2rem' }}
      >
        Logout
      </button>
    </div>
  );
};

export default App;
