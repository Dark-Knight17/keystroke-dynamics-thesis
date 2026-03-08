import React, { useState } from 'react';
import api from '../api';

interface AuthProps {
  onLogin: (userId: string) => void;
}

const Auth: React.FC<AuthProps> = ({ onLogin }) => {
  const [isRegistering, setIsRegistering] = useState(false);
  const [matricNumber, setMatricNumber] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [consented, setConsented] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (isRegistering && !consented) {
      setError('You must consent to the study to register.');
      return;
    }

    try {
      if (isRegistering) {
        const response = await api.post('/register', {
          matric_number: matricNumber,
          password: password,
        });
        setIsRegistering(false);
        alert('Registration successful! Please login.');
      } else {
        const response = await api.post('/login', {
          matric_number: matricNumber,
          password: password,
        });
        onLogin(response.data.user_id);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred. Please try again.');
    }
  };

  return (
    <div className="auth-container" style={{ maxWidth: '400px', margin: 'auto', padding: '2rem' }}>
      <h2>{isRegistering ? 'Register Participant' : 'Login'}</h2>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <input
          type="text"
          placeholder="Matriculation Number"
          value={matricNumber}
          onChange={(e) => setMatricNumber(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        
        {isRegistering && (
          <div className="consent-form" style={{ background: '#f9f9f9', padding: '1rem', borderRadius: '4px', fontSize: '0.9rem' }}>
            <h3>Consent Form</h3>
            <p>
              By participating in this study, you agree to have your keystroke dynamics collected
              for research purposes. All data will be anonymized. Participation is voluntary.
            </p>
            <label>
              <input
                type="checkbox"
                checked={consented}
                onChange={(e) => setConsented(e.target.checked)}
              />
              {' '}I consent to the terms of this study.
            </label>
          </div>
        )}

        <button type="submit" style={{ padding: '0.75rem', background: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
          {isRegistering ? 'Register' : 'Login'}
        </button>
      </form>
      
      <p style={{ marginTop: '1rem', textAlign: 'center' }}>
        {isRegistering ? 'Already have an account?' : 'Need to register?'}
        {' '}
        <button
          onClick={() => setIsRegistering(!isRegistering)}
          style={{ background: 'none', border: 'none', color: '#007bff', textDecoration: 'underline', cursor: 'pointer' }}
        >
          {isRegistering ? 'Login here' : 'Register here'}
        </button>
      </p>

      {error && <p style={{ color: 'red', textAlign: 'center' }}>{error}</p>}
    </div>
  );
};

export default Auth;
