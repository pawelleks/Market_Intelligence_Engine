import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

const API_BASE = "/api/v1/admin/users";

const AdminUserManagement = () => {
    const { token } = useAuth();
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [actionMessage, setActionMessage] = useState(null);

    const fetchUsers = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/all`, {
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });
            if (res.ok) {
                const data = await res.json();
                setUsers(data);
            } else {
                setError("Failed to fetch users");
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, [token]);

    const handleAction = async (userId, action) => {
        // action = 'approve' | 'deny'
        try {
            const method = 'PUT';
            const url = `${API_BASE}/${userId}/${action}`;

            const res = await fetch(url, {
                method,
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });

            if (res.ok) {
                setActionMessage(`User ${action}d successfully.`);
                fetchUsers(); // Refresh
                setTimeout(() => setActionMessage(null), 3000);
            } else {
                const json = await res.json();
                alert(`Error: ${json.detail}`);
            }
        } catch (err) {
            console.error(err);
            alert("Action failed");
        }
    };

    return (
        <div style={{ color: '#e0e0e0', padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{ margin: 0 }}>Registered Users</h3>
                <button
                    onClick={fetchUsers}
                    style={{
                        padding: '8px 16px',
                        backgroundColor: '#334155',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer'
                    }}
                >
                    Refresh List
                </button>
            </div>

            {actionMessage && (
                <div style={{ padding: '10px', backgroundColor: '#064e3b', color: '#6ee7b7', marginBottom: '15px', borderRadius: '4px' }}>
                    {actionMessage}
                </div>
            )}

            {error && <div style={{ color: '#ef4444', marginBottom: '15px' }}>{error}</div>}

            <div style={{ overflowX: 'auto', backgroundColor: '#0f172a', borderRadius: '8px', border: '1px solid #1e293b' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                    <thead style={{ backgroundColor: '#1e293b', textAlign: 'left', color: '#94a3b8' }}>
                        <tr>
                            <th style={{ padding: '12px' }}>ID</th>
                            <th style={{ padding: '12px' }}>Email</th>
                            <th style={{ padding: '12px' }}>Name</th>
                            <th style={{ padding: '12px' }}>Status</th>
                            <th style={{ padding: '12px' }}>Role</th>
                            <th style={{ padding: '12px' }}>Visits</th>
                            <th style={{ padding: '12px', textAlign: 'right' }}>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr><td colSpan="7" style={{ padding: '20px', textAlign: 'center' }}>Loading...</td></tr>
                        ) : users.length === 0 ? (
                            <tr><td colSpan="7" style={{ padding: '20px', textAlign: 'center' }}>No users found.</td></tr>
                        ) : (
                            users.sort((a, b) => b.id - a.id).map(user => (
                                <tr key={user.id} style={{ borderBottom: '1px solid #1e293b' }}>
                                    <td style={{ padding: '12px', color: '#64748b' }}>{user.id}</td>
                                    <td style={{ padding: '12px', fontWeight: 'bold' }}>{user.email}</td>
                                    <td style={{ padding: '12px' }}>{user.full_name || '-'}</td>
                                    <td style={{ padding: '12px' }}>
                                        <span style={{
                                            padding: '2px 8px',
                                            borderRadius: '12px',
                                            fontSize: '12px',
                                            backgroundColor: user.is_approved ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                            color: user.is_approved ? '#34d399' : '#f87171'
                                        }}>
                                            {user.is_approved ? 'Active' : 'Pending'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '12px', color: user.is_admin ? '#f472b6' : '#94a3b8' }}>
                                        {user.is_admin ? 'Admin' : 'User'}
                                    </td>
                                    <td style={{ padding: '12px' }}>{user.visit_count}</td>
                                    <td style={{ padding: '12px', textAlign: 'right' }}>
                                        {!user.is_approved && (
                                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                                                <button
                                                    onClick={() => handleAction(user.id, 'approve')}
                                                    style={{
                                                        padding: '4px 10px',
                                                        backgroundColor: '#16a34a', // green
                                                        color: 'white',
                                                        border: 'none',
                                                        borderRadius: '4px',
                                                        cursor: 'pointer',
                                                        fontSize: '12px'
                                                    }}
                                                >
                                                    Approve
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        if (window.confirm(`Delete user ${user.email}?`)) handleAction(user.id, 'deny');
                                                    }}
                                                    style={{
                                                        padding: '4px 10px',
                                                        backgroundColor: '#dc2626', // red
                                                        color: 'white',
                                                        border: 'none',
                                                        borderRadius: '4px',
                                                        cursor: 'pointer',
                                                        fontSize: '12px'
                                                    }}
                                                >
                                                    Deny
                                                </button>
                                            </div>
                                        )}
                                        {user.is_approved && (
                                            <span style={{ color: '#64748b', fontSize: '12px' }}>Authorized</span>
                                            // Admin toggle could be added here
                                        )}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default AdminUserManagement;
