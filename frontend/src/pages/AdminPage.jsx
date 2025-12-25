import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Loader2, CheckCircle, XCircle, User, Activity, Clock, AlertTriangle } from 'lucide-react';

const AdminPage = () => {
    const [activeTab, setActiveTab] = useState('pending'); // 'pending' | 'all'
    const [pendingUsers, setPendingUsers] = useState([]);
    const [allUsers, setAllUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [actionLoading, setActionLoading] = useState(null);

    const fetchPendingUsers = async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/v1/admin/users');
            setPendingUsers(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const fetchAllUsers = async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/v1/admin/users/all');
            setAllUsers(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'pending') {
            fetchPendingUsers();
        } else {
            fetchAllUsers();
        }
    }, [activeTab]);

    const handleApprove = async (id) => {
        setActionLoading(id);
        try {
            await axios.put(`/api/v1/admin/users/${id}/approve`);
            setPendingUsers(pendingUsers.filter(u => u.id !== id));
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
            setPendingUsers(pendingUsers.filter(u => u.id !== id));
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
        warning: '#ff9800',
    };

    return (
        <div style={{ padding: '20px', backgroundColor: colors.bg, minHeight: '100vh', color: colors.text }}>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h1 style={{ fontSize: '24px', margin: 0 }}>Admin Panel</h1>
                <div style={{ display: 'flex', gap: 10 }}>
                    <button
                        onClick={() => setActiveTab('pending')}
                        style={{
                            padding: '8px 16px', borderRadius: 4, cursor: 'pointer',
                            backgroundColor: activeTab === 'pending' ? colors.accent : 'transparent',
                            color: activeTab === 'pending' ? 'white' : colors.textMuted,
                            border: `1px solid ${activeTab === 'pending' ? colors.accent : colors.border}`
                        }}
                    >
                        User Approval
                    </button>
                    <button
                        onClick={() => setActiveTab('all')}
                        style={{
                            padding: '8px 16px', borderRadius: 4, cursor: 'pointer',
                            backgroundColor: activeTab === 'all' ? colors.accent : 'transparent',
                            color: activeTab === 'all' ? 'white' : colors.textMuted,
                            border: `1px solid ${activeTab === 'all' ? colors.accent : colors.border}`
                        }}
                    >
                        All Users
                    </button>
                </div>
            </div>

            {loading ? (
                <div style={{ textAlign: 'center', padding: 50, color: colors.textMuted }}>
                    <Loader2 className="animate-spin" style={{ display: 'inline', marginRight: 10 }} /> Loading...
                </div>
            ) : (
                <>
                    {activeTab === 'pending' && (
                        pendingUsers.length === 0 ? (
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
                                        {pendingUsers.map(user => (
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
                                                                backgroundColor: 'transparent', border: `1px solid ${colors.danger}`, color: colors.danger, cursor: 'pointer',
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
                        )
                    )}

                    {activeTab === 'all' && (
                        <div style={{ backgroundColor: colors.panelBg, borderRadius: 8, border: `1px solid ${colors.border}`, overflow: 'hidden' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                                <thead style={{ backgroundColor: '#1a2639' }}>
                                    <tr>
                                        <th style={{ textAlign: 'left', padding: 15, color: colors.textMuted }}>ID</th>
                                        <th style={{ textAlign: 'left', padding: 15, color: colors.textMuted }}>User</th>
                                        <th style={{ textAlign: 'left', padding: 15, color: colors.textMuted }}>Email</th>
                                        <th style={{ textAlign: 'center', padding: 15, color: colors.textMuted }}>Role</th>
                                        <th style={{ textAlign: 'center', padding: 15, color: colors.textMuted }}>Status</th>
                                        <th style={{ textAlign: 'center', padding: 15, color: colors.textMuted }}>Visits</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {allUsers.map(user => (
                                        <tr key={user.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                                            <td style={{ padding: 15, color: colors.textMuted }}>#{user.id}</td>
                                            <td style={{ padding: 15 }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                                    <div style={{ padding: 6, borderRadius: '50%', backgroundColor: '#2a3a50' }}>
                                                        <User size={14} />
                                                    </div>
                                                    {user.full_name || "-"}
                                                </div>
                                            </td>
                                            <td style={{ padding: 15, color: colors.text }}>{user.email}</td>
                                            <td style={{ padding: 15, textAlign: 'center' }}>
                                                {user.is_admin ? (
                                                    <span style={{ backgroundColor: 'rgba(124, 58, 237, 0.2)', color: '#a78bfa', padding: '2px 8px', borderRadius: 4, fontSize: '12px' }}>Admin</span>
                                                ) : <span style={{ color: colors.textMuted }}>User</span>}
                                            </td>
                                            <td style={{ padding: 15, textAlign: 'center' }}>
                                                {user.is_approved ? (
                                                    <span style={{ color: colors.success }}>Approved</span>
                                                ) : <span style={{ color: colors.warning }}>Pending</span>}
                                            </td>
                                            <td style={{ padding: 15, textAlign: 'center' }}>
                                                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, backgroundColor: 'rgba(33, 150, 243, 0.1)', color: colors.accent, padding: '2px 10px', borderRadius: 12 }}>
                                                    <Clock size={12} />
                                                    {user.visit_count || 0}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default AdminPage;
