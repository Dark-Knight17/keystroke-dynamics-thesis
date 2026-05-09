import React, { useState } from 'react';
import api from '../api';

interface AuthProps {
  onLogin: (userId: string) => void;
}

const Auth: React.FC<AuthProps> = ({ onLogin }) => {
  const [isRegistering, setIsRegistering] = useState(false);
  const [matricNumber, setMatricNumber] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [physicalKeyboardType, setPhysicalKeyboardType] = useState('');
  const [keyboardLayout, setKeyboardLayout] = useState('QWERTY');
  const [error, setError] = useState('');
  const [consented, setConsented] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

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
    setIsLoading(true);

    if (isRegistering && !consented) {
      setError('You must consent to the study to register.');
      setIsLoading(false);
      return;
    }

    if (isRegistering && !physicalKeyboardType) {
      setError('Please select your keyboard type.');
      setIsLoading(false);
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
          keyboard_layout: keyboardLayout,
        });
        setIsRegistering(false);
        alert('Registration successful! Please login.');
      } else {
        const response = await api.post('/login', {
          matric_number: matricNumber,
          password: password,
        });
        const { user_id, access_token } = response.data;
        if (access_token) {
          localStorage.setItem('access_token', access_token);
        }
        onLogin(user_id);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <h2 style={{ fontSize: '1.75rem', marginBottom: '1.5rem', textAlign: 'center' }}>
        {isRegistering ? 'Join Study' : 'Sign In'}
      </h2>
      <form onSubmit={handleSubmit} className="auth-form">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.9rem', fontWeight: '500', color: 'var(--anthropic-mid-gray)' }}>Matriculation Number</label>
          <input
            type="text"
            placeholder="e.g. 12345678"
            value={matricNumber}
            onChange={(e) => setMatricNumber(e.target.value)}
            required
            className="auth-input"
          />
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.9rem', fontWeight: '500', color: 'var(--anthropic-mid-gray)' }}>Password</label>
          <div className="password-input-container">
            <input
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="auth-input"
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? '👁️' : '👁️‍🗨️'}
            </button>
          </div>
        </div>

        {isRegistering && (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.9rem', fontWeight: '500', color: 'var(--anthropic-mid-gray)' }}>Physical Keyboard Type</label>
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
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.9rem', fontWeight: '500', color: 'var(--anthropic-mid-gray)' }}>Keyboard Layout</label>
              <select
                value={keyboardLayout}
                onChange={(e) => setKeyboardLayout(e.target.value)}
                required
                className="auth-input"
              >
                <option value="QWERTY">QWERTY</option>
                <option value="AZERTY">AZERTY</option>
                <option value="Dvorak">Dvorak</option>
                <option value="Colemak">Colemak</option>
                <option value="Unknown">Unknown</option>
              </select>
            </div>
          </>
        )}
        
        {isRegistering && (
          <div className="consent-form">
            <h3 style={{ fontSize: '1rem', marginTop: 0, marginBottom: '0.5rem' }}>Consent & Privacy</h3>
            <p style={{ fontSize: '0.85rem', marginBottom: '1rem' }}>
              By participating, you agree to have your keystroke dynamics collected
              for research purposes. All data is strictly anonymized and linked only to a random ID.
            </p>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.9rem' }}>
              <input
                type="checkbox"
                checked={consented}
                onChange={(e) => setConsented(e.target.checked)}
                style={{ width: '18px', height: '18px', cursor: 'pointer' }}
              />
              <span>I consent to these terms</span>
            </label>
          </div>
        )}

        <button 
          type="submit" 
          className="btn btn-primary" 
          style={{ marginTop: '0.5rem' }} 
          disabled={isLoading}
        >
          {isLoading && <div className="spinner"></div>}
          {isRegistering ? 'Create Account' : 'Sign In'}
        </button>
      </form>
      
      <div style={{ marginTop: '2rem', textAlign: 'center', fontSize: '0.95rem', color: 'var(--anthropic-mid-gray)' }}>
        {isRegistering ? 'Already have an account?' : 'New to the study?'}
        {' '}
        <button
          onClick={() => setIsRegistering(!isRegistering)}
          className="btn-link"
          style={{ fontWeight: '500' }}
        >
          {isRegistering ? 'Sign in instead' : 'Register here'}
        </button>
      </div>

      {error && <div className="error-msg">{error}</div>}
    </div>
  );
};

export default Auth;
