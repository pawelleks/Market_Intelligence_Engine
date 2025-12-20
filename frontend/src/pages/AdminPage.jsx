import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Loader2, CheckCircle, XCircle, User, Activity, Clock, AlertTriangle } from 'lucide-react';

const AdminPage = () => {
    const [activeTab, setActiveTab] = useState('users'); // 'users' | 'system'
    const [users, setUsers] = useState([]);
    const [auditData, setAuditData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [auditLoading, setAuditLoading] = useState(false);
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

    const fetchAuditLog = async () => {
        setAuditLoading(true);
        try {
            const res = await axios.get('/api/v1/system/audit/latest');
            setAuditData(res.data);
        } catch (err) {
            console.error("Failed to fetch audit log:", err);
        } finally {
            setAuditLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
        fetchAuditLog();
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
        warning: '#ff9800',
    };

    const StatusBadge = ({ status }) => {
        let color = colors.textMuted;
        let Icon = Clock;

        const s = (status || "").toUpperCase();

        if (s === 'COMPLETED' || s === 'SUCCESS') {
            color = colors.success;
            Icon = CheckCircle;
        } else if (s === 'FAILED' || s === 'ERROR') {
            color = colors.danger;
            Icon = XCircle;
        } else if (s === 'RUNNING') {
            color = colors.accent;
            Icon = Loader2;
        } else if (s === 'SKIPPED') {
            color = colors.warning;
            Icon = AlertTriangle;
        }

        return (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: color, fontWeight: 500 }}>
                <Icon size={16} className={s === 'RUNNING' ? "animate-spin" : ""} />
                {s || "UNKNOWN"}
            </div>
        );
    };

    const renderAuditSection = () => {
        if (auditLoading && !auditData) {
            return (
                <div style={{ textAlign: 'center', padding: 50, color: colors.textMuted }}>
                    <Loader2 className="animate-spin" style={{ display: 'inline', marginRight: 10 }} /> Loading Audit Log...
                </div>
            );
        }

        if (!auditData) {
            return (
                <div style={{ padding: 20, backgroundColor: colors.panelBg, borderRadius: 8, border: `1px solid ${colors.border}`, color: colors.textMuted }}>
                    No audit logs available. Run a pipeline job to generate data.
                </div>
            );
        }

        return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {/* Header Card */}
                <div style={{ padding: 20, backgroundColor: colors.panelBg, borderRadius: 8, border: `1px solid ${colors.border}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 }}>
                        <div>
                            <h2 style={{ fontSize: '18px', color: colors.text, margin: 0 }}>{auditData.job_name || "Pipeline Job"}</h2>
                            <div style={{ fontSize: '12px', color: colors.textMuted, marginTop: 5 }}>
                                Started: {new Date(auditData.start_time).toLocaleString()}
                            </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '14px', marginBottom: 5 }}>Overall Status</div>
                            <StatusBadge status={auditData.status} />
                            {auditData.end_time && (
                                <div style={{ fontSize: '12px', color: colors.textMuted, marginTop: 5 }}>
                                    Ended: {new Date(auditData.end_time).toLocaleString()}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Stages List */}
                <div style={{ backgroundColor: colors.panelBg, borderRadius: 8, border: `1px solid ${colors.border}`, overflow: 'hidden' }}>
                    <div style={{ padding: '15px 20px', borderBottom: `1px solid ${colors.border}`, display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Activity size={18} color={colors.accent} />
                        <h3 style={{ margin: 0, fontSize: '16px', color: colors.text }}>Pipeline Stages</h3>
                    </div>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                        <thead style={{ backgroundColor: '#1a2639' }}>
                            <tr>
                                <th style={{ textAlign: 'left', padding: 15, color: colors.textMuted }}>Stage Name</th>
                                <th style={{ textAlign: 'left', padding: 15, color: colors.textMuted }}>Timestamp</th>
                                <th style={{ textAlign: 'left', padding: 15, color: colors.textMuted }}>Details</th>
                                <th style={{ textAlign: 'right', padding: 15, color: colors.textMuted }}>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {Object.entries(auditData.stages || {}).map(([name, stage]) => (
                                <tr key={name} style={{ borderBottom: `1px solid ${colors.border}` }}>
                                    <td style={{ padding: 15, fontWeight: 500 }}>{name}</td>
                                    <td style={{ padding: 15, color: colors.textMuted, fontSize: '12px' }}>
                                        {stage.start_time ? new Date(stage.start_time).toLocaleTimeString() : "-"}
                                    </td>
                                    <td style={{ padding: 15, color: colors.textMuted, fontSize: '12px', maxWidth: 300 }}>
                                        {stage.details ? JSON.stringify(stage.details).slice(0, 100) : "-"}
                                        {stage.error && <div style={{ color: colors.danger, marginTop: 4 }}>Error: {stage.error}</div>}
                                    </td>
                                    <td style={{ padding: 15, textAlign: 'right' }}>
                                        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                                            <StatusBadge status={stage.status} />
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            {Object.keys(auditData.stages || {}).length === 0 && (
                                <tr>
                                    <td colSpan={4} style={{ padding: 20, textAlign: 'center', color: colors.textMuted }}>
                                        No stages recorded yet.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    };

    return (
        <div style={{ padding: '20px', backgroundColor: colors.bg, minHeight: '100vh', color: colors.text }}>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h1 style={{ fontSize: '24px', margin: 0 }}>Admin Panel</h1>
                <div style={{ display: 'flex', gap: 10 }}>
                    <button
                        onClick={() => setActiveTab('users')}
                        style={{
                            padding: '8px 16px', borderRadius: 4, cursor: 'pointer',
                            backgroundColor: activeTab === 'users' ? colors.accent : 'transparent',
                            color: activeTab === 'users' ? 'white' : colors.textMuted,
                            border: `1px solid ${activeTab === 'users' ? colors.accent : colors.border}`
                        }}
                    >
                        User Approval
                    </button>
                    <button
                        onClick={() => setActiveTab('system')}
                        style={{
                            padding: '8px 16px', borderRadius: 4, cursor: 'pointer',
                            backgroundColor: activeTab === 'system' ? colors.accent : 'transparent',
                            color: activeTab === 'system' ? 'white' : colors.textMuted,
                            border: `1px solid ${activeTab === 'system' ? colors.accent : colors.border}`
                        }}
                    >
                        Pipeline Audit
                    </button>
                </div>
            </div>

            {activeTab === 'system' ? renderAuditSection() : (
                <>
                    {loading ? (
                        <div style={{ textAlign: 'center', padding: 50, color: colors.textMuted }}>
                            <Loader2 className="animate-spin" style={{ display: 'inline', marginRight: 10 }} /> Loading Users...
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
                    )}
                </>
            )}
        </div>
    );
};

export default AdminPage;
