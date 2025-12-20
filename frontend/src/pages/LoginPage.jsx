import React, { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Lock } from 'lucide-react';

const LoginPage = () => {
    const { login, bypassLogin } = useAuth();
    const navigate = useNavigate();
    const [error, setError] = useState(null);

    const handleSuccess = async (credentialResponse) => {
        const result = await login(credentialResponse.credential);
        if (result.success) {
            navigate('/');
        } else {
            setError(result.message);
        }
    };

    const handleError = () => {
        setError('Google Login Failed');
    };

    // DEBUG: Check Client ID
    console.log('Current Client ID:', import.meta.env.VITE_GOOGLE_CLIENT_ID);

    return (
        <div style={{
            height: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#0b1220',
            color: '#d7e3f3'
        }}>
            <div style={{
                padding: '40px',
                backgroundColor: '#0e1525',
                border: '1px solid #203049',
                borderRadius: '8px',
                textAlign: 'center',
                width: '100%',
                maxWidth: '400px'
            }}>


                <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'center' }}>
                    <div style={{ padding: 10, borderRadius: '50%', backgroundColor: 'rgba(33, 150, 243, 0.1)' }}>
                        <Lock size={32} color="#2196f3" />
                    </div>
                </div>
                <h2 style={{ marginBottom: 10 }}>Sign In</h2>
                <p style={{ color: '#9e9e9e', marginBottom: 30 }}>Access Market Intelligence Engine</p>

                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
                    <GoogleLogin
                        onSuccess={handleSuccess}
                        onError={handleError}
                        theme="filled_black"
                        shape="pill"
                    />
                </div>

                {/* Developer Bypass for Localhost */}
                {(window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && (
                    <div style={{ marginBottom: 20 }}>
                        <button
                            onClick={async () => {
                                const result = await bypassLogin();
                                if (result.success) {
                                    navigate('/');
                                } else {
                                    setError('Bypass Failed');
                                }
                            }}
                            style={{
                                background: 'transparent',
                                border: '1px solid #444',
                                color: '#888',
                                padding: '8px 16px',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '0.8rem'
                            }}
                        >
                            Developer Bypass
                        </button>
                    </div>
                )}

                {error && (
                    <div style={{
                        marginTop: 20,
                        padding: 10,
                        backgroundColor: 'rgba(244, 67, 54, 0.1)',
                        border: '1px solid #f44336',
                        color: '#f44336',
                        borderRadius: 4,
                        fontSize: '14px'
                    }}>
                        {error}
                    </div>
                )}
            </div>
        </div>
    );
};

export default LoginPage;
