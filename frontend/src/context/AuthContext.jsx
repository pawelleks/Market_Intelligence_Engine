import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from "jwt-decode";
import axios from 'axios';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem('access_token'));
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const initAuth = async () => {
            // Auth bypass for local/staging — auto-trigger existing bypassLogin()
            if (import.meta.env.VITE_DISABLE_AUTH === 'true' && !token) {
                await bypassLogin();
                return; // bypassLogin sets token, which re-triggers this effect
            }

            if (token) {
                try {
                    const decoded = jwtDecode(token);
                    // Check expiry
                    if (decoded.exp * 1000 < Date.now()) {
                        logout();
                    } else {
                        // Configure axios default header
                        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

                        // Bypass Check: If this is the dev token, skip backend validation
                        if (decoded.sub === 'bypass@local.dev') {
                            console.warn("Using Developer Bypass - Skipping Backend Validation");
                            setUser(decoded);
                            setLoading(false);
                            return;
                        }

                        // Fetch full user profile with timeout
                        try {
                            const response = await axios.get('/api/users/me', { timeout: 2000 });
                            // Merge decoded (jwt) with response data
                            setUser({ ...decoded, ...response.data });
                        } catch (err) {
                            console.error("Failed to fetch user profile", err);
                            // If token is invalid (401) or forbidden (403), logout immediately
                            if (err.response && (err.response.status === 401 || err.response.status === 403)) {
                                logout();
                            } else {
                                // For other errors (network, 500, timeout), fall back to decoded token to allow partial access
                                console.warn("Using offline/decoded token due to API error/timeout.");
                                setUser(decoded);
                            }
                        }
                    }
                } catch (e) {
                    console.error("Invalid token", e);
                    logout();
                }
            } else {
                setUser(null);
            }
            setLoading(false);
        };
        initAuth();
    }, [token]);

    // Expose a refresh function
    const refreshUser = async () => {
        if (token) {
            try {
                const response = await axios.get('/api/users/me');
                setUser(prev => ({ ...prev, ...response.data }));
            } catch (err) {
                console.error("Failed to refresh user", err);
            }
        }
    };

    const login = async (googleToken) => {
        try {
            const res = await axios.post('/api/v1/auth/login', { id_token: googleToken });
            const { access_token, message } = res.data;

            if (access_token) {
                localStorage.setItem('access_token', access_token);
                setToken(access_token);
                // We will fetch full user details in the effect hook
                // But for immediate return, decoding offers basic info
                const decoded = jwtDecode(access_token);
                setUser(decoded);
                return { success: true };
            } else {
                // Pending/New/Unapproved User (Generic 200 OK Response)
                return { success: false, message: message || "Login processed. Check your email." };
            }
        } catch (err) {
            console.error(err);
            if (err.response && err.response.data && err.response.data.detail) {
                return { success: false, message: err.response.data.detail };
            }
            return { success: false, message: "Login failed" };
        }
    };

    const bypassLogin = async () => {
        // Dummy JWT: Header.Payload.Signature
        // Payload: sub=bypass@local.dev, exp=far_future, is_admin=true
        const dummyToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJieXBhc3NAbG9jYWwuZGV2IiwiZXhwIjo5OTk5OTk5OTk5LCJuYW1lIjoiRGV2ZWxvcGVyIiwiZW1haWwiOiJieXBhc3NAbG9jYWwuZGV2IiwiaXNfYWRtaW4iOnRydWV9.dummy_signature";

        localStorage.setItem('access_token', dummyToken);
        setToken(dummyToken);

        try {
            const decoded = jwtDecode(dummyToken);
            setUser(decoded);
            return { success: true };
        } catch (e) {
            console.error("Bypass token gen failed", e);
            return { success: false, message: "Bypass failed" };
        }
    };

    const logout = () => {
        localStorage.removeItem('access_token');
        setToken(null);
        setUser(null);
        delete axios.defaults.headers.common['Authorization'];
    };

    return (
        <AuthContext.Provider value={{ user, token, login, bypassLogin, logout, loading, refreshUser }}>
            {loading ? (
                <div style={{
                    height: '100vh',
                    width: '100vw',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    backgroundColor: '#0b1220',
                    color: '#4caf50',
                    flexDirection: 'column',
                    gap: '15px'
                }}>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>Market Intelligence Engine</div>
                    <div style={{ fontSize: '0.9rem', color: '#94a3b8' }}>Initializing Application Context...</div>
                </div>
            ) : children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
