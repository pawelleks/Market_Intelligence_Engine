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
            if (token) {
                try {
                    const decoded = jwtDecode(token);
                    // Check expiry
                    if (decoded.exp * 1000 < Date.now()) {
                        logout();
                    } else {
                        // Configure axios default header
                        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

                        // FIX: Fetch full user profile including Terms Status
                        try {
                            const response = await axios.get('/api/users/me');
                            // Merge decoded (jwt) with response data
                            setUser({ ...decoded, ...response.data });
                        } catch (err) {
                            console.error("Failed to fetch user profile", err);
                            // Fallback to decoded token if API fails (though API fail might mean invalid token)
                            setUser(decoded);
                        }
                    }
                } catch (e) {
                    console.error("Invalid token", e);
                    logout();
                }
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
            {!loading && children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
