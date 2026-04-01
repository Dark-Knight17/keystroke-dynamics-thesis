import React, { useState } from 'react';
import api from '../api';

interface AuthProps {
  onLogin: (userId: string) => void;
}

const Auth: React.FC<AuthProps> = ({ onLogin }) => {
  const [isRegistering, setIsRegistering] = useState(false);
  const [matricNumber, setMatricNumber] = useState('');
  const [password, setPassword] = useState('');
  const [physicalKeyboardType, setPhysicalKeyboardType] = useState('');
  const [error, setError] = useState('');
  const [consented, setConsented] = useState(false);

  const getOS = () => {
    const ua = navigator.userAgent;
    if (ua.indexOf('Win') !== -1) return 'Windows';
    if (ua.indexOf('Mac') !== -1) return 'MacOS';
    if (ua.indexOf('Linux') !== -1) return 'Linux';
    if (ua.indexOf('Android') !== -1) return 'Android';
    if (ua.indexOf('like Mac') !== -1) return 'iOS';
    return 'Unknown';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (isRegistering && !consented) {
      setError('You must consent to the study to register.');
      return;
    }

    if (isRegistering && !physicalKeyboardType) {
      setError('Please select your keyboard type.');
      return;
    }

    try {
      if (isRegistering) {
        await api.post('/register', {
          matric_number: matricNumber,
          password: password,
          physical_keyboard_type: physicalKeyboardType,
          device_type: navigator.userAgent,
          os: getOS(),
          keyboard_layout: 'Standard QWERTY',
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
    <div className="auth-container">
      <h2>{isRegistering ? 'Register Participant' : 'Login'}</h2>
      <form onSubmit={handleSubmit} className="auth-form">
        <input
          type="text"
          placeholder="Matriculation Number"
          value={matricNumber}
          onChange={(e) => setMatricNumber(e.target.value)}
          required
          className="auth-input"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="auth-input"
        />

        {isRegistering && (
          <select
            value={physicalKeyboardType}
            onChange={(e) => setPhysicalKeyboardType(e.target.value)}
            required
            className="auth-input"
          >
            <option value="" disabled>Select your keyboard type...</option>
            <option value="Built-in Laptop Keyboard">Built-in Laptop Keyboard</option>
            <option value="External Standard (Membrane) Keyboard">External Standard (Membrane) Keyboard</option>
            <option value="External Mechanical Keyboard">External Mechanical Keyboard</option>
          </select>
        )}
        
        {isRegistering && (
          <div className="consent-form">
            <h3 style={{ marginTop: 0 }}>Consent Form</h3>
            <p>
              By participating in this study, you agree to have your keystroke dynamics collected
              for research purposes. All data will be anonymized. Participation is voluntary.
            </p>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="checkbox"
                checked={consented}
                onChange={(e) => setConsented(e.target.checked)}
              />
              I consent to the terms of this study.
            </label>
          </div>
        )}

        <button type="submit" className="btn btn-primary">
          {isRegistering ? 'Register' : 'Login'}
        </button>
      </form>
      
      <p style={{ marginTop: '1rem', textAlign: 'center' }}>
        {isRegistering ? 'Already have an account?' : 'Need to register?'}
        {' '}
        <button
          onClick={() => setIsRegistering(!isRegistering)}
          className="btn-link"
        >
          {isRegistering ? 'Login here' : 'Register here'}
        </button>
      </p>

      {error && <p className="error-msg">{error}</p>}
    </div>
  );
};

export default Auth;
