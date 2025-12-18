import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Loader2, CheckCircle, XCircle, User } from 'lucide-react';

const AdminPage = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(null); // ID of user being processed

    const fetchUsers = async () => {
        try {
            const res = await axios.get('/api/v1/admin/users');
            setUsers(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleApprove = async (id) => {
        setActionLoading(id);
        try {
            await axios.put(`/api/v1/admin/users/${id}/approve`);
            setUsers(users.filter(u => u.id !== id)); // Remove from list
        } catch (err) {
            console.error(err);
            alert("Failed to approve");
        } finally {
            setActionLoading(null);
        }
    };

    const handleDeny = async (id) => {
        if (!confirm("Are you sure you want to deny (delete) this user?")) return;
        setActionLoading(id);
        try {
            await axios.put(`/api/v1/admin/users/${id}/deny`);
            setUsers(users.filter(u => u.id !== id));
        } catch (err) {
            console.error(err);
            alert("Failed to deny");
        } finally {
            setActionLoading(null);
        }
    };

    const colors = {
        bg: '#0b1220',
        panelBg: '#0e1525',
        border: '#203049',
        text: '#d7e3f3',
        textMuted: '#9e9e9e',
        accent: '#2196f3',
        success: '#4caf50',
        danger: '#f44336',
    };

    return (
        <div style={{ padding: '20px', backgroundColor: colors.bg, minHeight: '100vh', color: colors.text }}>
            <h1 style={{ fontSize: '24px', marginBottom: 20 }}>Admin Panel: Pending Approvals</h1>

            {loading ? (
                <div style={{ textAlign: 'center', padding: 50, color: colors.textMuted }}>
                    <Loader2 className="animate-spin" style={{ display: 'inline', marginRight: 10 }} /> Loading...
                </div>
            ) : users.length === 0 ? (
                <div style={{ padding: 20, backgroundColor: colors.panelBg, borderRadius: 8, border: `1px solid ${colors.border}`, color: colors.textMuted }}>
                    No pending users.
                </div>
            ) : (
                <div style={{ backgroundColor: colors.panelBg, borderRadius: 8, border: `1px solid ${colors.border}`, overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                        <thead style={{ backgroundColor: '#1a2639' }}>
                            <tr>
                                <th style={{ textAlign: 'left', padding: 15, color: colors.textMuted }}>User</th>
                                <th style={{ textAlign: 'left', padding: 15, color: colors.textMuted }}>Email</th>
                                <th style={{ textAlign: 'right', padding: 15, color: colors.textMuted }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map(user => (
                                <tr key={user.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                                    <td style={{ padding: 15 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                            <div style={{ padding: 8, borderRadius: '50%', backgroundColor: '#2a3a50' }}>
                                                <User size={16} />
                                            </div>
                                            {user.full_name || "Unknown"}
                                        </div>
                                    </td>
                                    <td style={{ padding: 15 }}>{user.email}</td>
                                    <td style={{ padding: 15, textAlign: 'right' }}>
                                        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                                            <button
                                                onClick={() => handleApprove(user.id)}
                                                disabled={actionLoading === user.id}
                                                style={{
                                                    display: 'flex', alignItems: 'center', gap: 5,
                                                    padding: '6px 12px', borderRadius: 4,
                                                    border: 'none', backgroundColor: colors.success, color: 'white', cursor: 'pointer',
                                                    opacity: actionLoading === user.id ? 0.5 : 1
                                                }}
                                            >
                                                {actionLoading === user.id ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                                                Approve
                                            </button>
                                            <button
                                                onClick={() => handleDeny(user.id)}
                                                disabled={actionLoading === user.id}
                                                style={{
                                                    display: 'flex', alignItems: 'center', gap: 5,
                                                    padding: '6px 12px', borderRadius: 4,
                                                    border: 'none', backgroundColor: 'transparent', border: `1px solid ${colors.danger}`, color: colors.danger, cursor: 'pointer',
                                                    opacity: actionLoading === user.id ? 0.5 : 1
                                                }}
                                            >
                                                <XCircle size={14} />
                                                Deny
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default AdminPage;
