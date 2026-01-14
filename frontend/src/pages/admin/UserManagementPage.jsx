import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Shield, User, AlertCircle, RefreshCw, CheckCircle, XCircle } from 'lucide-react';

// --- Reusable User Table Component ---
const UserTable = ({ users, type, onAction }) => {
    const [page, setPage] = useState(1);
    const pageSize = 50;

    // Reset page when users change
    useEffect(() => { setPage(1); }, [users]);

    const totalPages = Math.ceil(users.length / pageSize);
    const displayedUsers = users.slice((page - 1) * pageSize, page * pageSize);

    if (users.length === 0) {
        return <div style={{ padding: '20px', color: '#64748b', textAlign: 'center' }}>No records found.</div>;
    }

    return (
        <div>
            {/* Counter */}
            <div style={{ padding: '10px 0', fontSize: '14px', color: '#94a3b8' }}>
                Showing {((page - 1) * pageSize) + 1}-{Math.min(page * pageSize, users.length)} of {users.length} records
            </div>

            {/* Table */}
            <div style={{ backgroundColor: '#0f172a', borderRadius: '8px', border: '1px solid #1e293b', overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                    <thead style={{ backgroundColor: '#1e293b', textAlign: 'left', color: '#94a3b8' }}>
                        <tr>
                            <th style={{ padding: '12px' }}>ID</th>
                            <th style={{ padding: '12px' }}>Email</th>
                            <th style={{ padding: '12px' }}>Name</th>
                            <th style={{ padding: '12px' }}>Visits</th>
                            <th style={{ padding: '12px', textAlign: 'center' }}>Terms</th>
                            <th style={{ padding: '12px', textAlign: 'right' }}>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayedUsers.map(user => (
                            <tr key={user.id} style={{ borderBottom: '1px solid #1e293b' }}>
                                <td style={{ padding: '12px', color: '#64748b' }}>{user.id}</td>
                                <td style={{ padding: '12px', fontWeight: 'bold' }}>{user.email}</td>
                                <td style={{ padding: '12px' }}>{user.full_name || '-'}</td>
                                <td style={{ padding: '12px' }}>{user.visit_count}</td>
                                <td style={{ padding: '12px', textAlign: 'center' }}>
                                    {user.terms_accepted ? (
                                        <div title={`v${user.terms_version}`} style={{ color: '#16a34a', display: 'flex', justifyContent: 'center' }}>
                                            <CheckCircle size={18} />
                                        </div>
                                    ) : (
                                        <div title="Not Accepted" style={{ color: '#64748b', display: 'flex', justifyContent: 'center' }}>
                                            <XCircle size={18} />
                                        </div>
                                    )}
                                </td>
                                <td style={{ padding: '12px', textAlign: 'right' }}>
                                    {type === 'pending' && (
                                        <button
                                            onClick={() => onAction(user.id, 'approve')}
                                            style={{
                                                padding: '6px 12px',
                                                backgroundColor: '#16a34a',
                                                color: 'white',
                                                border: 'none',
                                                borderRadius: '4px',
                                                cursor: 'pointer',
                                                display: 'inline-flex', alignItems: 'center', gap: '5px'
                                            }}
                                        >
                                            <CheckCircle size={14} /> Approve
                                        </button>
                                    )}
                                    {type === 'active' && (
                                        <button
                                            onClick={() => onAction(user.id, 'revoke')}
                                            style={{
                                                padding: '6px 12px',
                                                backgroundColor: '#dc2626',
                                                color: 'white',
                                                border: 'none',
                                                borderRadius: '4px',
                                                cursor: 'pointer',
                                                display: 'inline-flex', alignItems: 'center', gap: '5px'
                                            }}
                                        >
                                            <XCircle size={14} /> Revoke
                                        </button>
                                    )}
                                    {type === 'inactive' && (
                                        <button
                                            onClick={() => onAction(user.id, 'approve')}
                                            style={{
                                                padding: '6px 12px',
                                                backgroundColor: '#16a34a',
                                                color: 'white',
                                                border: 'none',
                                                borderRadius: '4px',
                                                cursor: 'pointer',
                                                display: 'inline-flex', alignItems: 'center', gap: '5px'
                                            }}
                                        >
                                            <RefreshCw size={14} /> Re-Approve
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
                <div style={{ padding: '15px 0', display: 'flex', gap: '10px', justifyContent: 'center' }}>
                    <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page === 1}
                        style={{ padding: '5px 10px', cursor: page === 1 ? 'not-allowed' : 'pointer' }}
                    >
                        Prev
                    </button>
                    <span style={{ color: '#fff' }}>Page {page} of {totalPages}</span>
                    <button
                        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        style={{ padding: '5px 10px', cursor: page === totalPages ? 'not-allowed' : 'pointer' }}
                    >
                        Next
                    </button>
                </div>
            )}
        </div>
    );
};


import { useSearchParams } from 'react-router-dom';

const UserManagementPage = () => {
    const { token } = useAuth();
    const [allUsers, setAllUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchParams, setSearchParams] = useSearchParams();

    // Default to 'requests' if no param
    const activeTab = searchParams.get('tab') || 'requests';

    const setActiveTab = (tab) => {
        setSearchParams({ tab });
    };

    const fetchUsers = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/v1/admin/users/all', {
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setAllUsers(data);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (token) fetchUsers();
    }, [token]);

    const handleAction = async (userId, action) => {
        // action: approve | revoke
        // For 'Reject' we might use 'deny', but here we focus on Approve/Revoke as requested
        try {
            const res = await fetch(`/api/v1/admin/users/${userId}/${action}`, {
                method: 'PUT',
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (res.ok) {
                fetchUsers(); // Refresh
            } else {
                alert("Action failed");
            }
        } catch (e) {
            console.error(e);
        }
    };

    // Filter Logic
    const pendingUsers = allUsers.filter(u => !u.is_approved && u.subscription_status !== 'revoked');
    const activeUsers = allUsers.filter(u => u.is_approved);
    const inactiveUsers = allUsers.filter(u => u.subscription_status === 'revoked'); // Relies on our new backend logic

    // Counters
    const counts = {
        requests: pendingUsers.length,
        active: activeUsers.length,
        inactive: inactiveUsers.length
    };

    return (
        <div style={{ padding: '20px', maxWidth: '1600px', margin: '0 auto', color: '#e2e8f0' }}>
            <h1 style={{ marginBottom: '20px', borderBottom: '1px solid #334155', paddingBottom: '10px' }}>
                User Management
            </h1>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: '20px', marginBottom: '20px' }}>
                {[
                    { id: 'requests', label: 'Approval Requests', count: counts.requests, icon: AlertCircle, color: '#f59e0b' },
                    { id: 'active', label: 'Active Users', count: counts.active, icon: User, color: '#3b82f6' },
                    { id: 'inactive', label: 'Inactive Users', count: counts.inactive, icon: Shield, color: '#64748b' }
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        style={{
                            display: 'flex', alignItems: 'center', gap: '10px',
                            padding: '10px 20px',
                            backgroundColor: activeTab === tab.id ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                            border: `1px solid ${activeTab === tab.id ? tab.color : '#334155'}`,
                            borderRadius: '8px',
                            color: activeTab === tab.id ? tab.color : '#94a3b8',
                            cursor: 'pointer',
                            fontSize: '14px',
                            fontWeight: activeTab === tab.id ? 'bold' : 'normal'
                        }}
                    >
                        <tab.icon size={18} />
                        {tab.label}
                        <span style={{
                            backgroundColor: activeTab === tab.id ? tab.color : '#334155',
                            color: activeTab === tab.id ? '#fff' : '#94a3b8',
                            padding: '2px 8px', borderRadius: '12px', fontSize: '12px'
                        }}>
                            {tab.count}
                        </span>
                    </button>
                ))}
            </div>

            {/* Content */}
            {loading ? (
                <div>Loading...</div>
            ) : (
                <>
                    {activeTab === 'requests' && <UserTable users={pendingUsers} type="pending" onAction={handleAction} />}
                    {activeTab === 'active' && <UserTable users={activeUsers} type="active" onAction={handleAction} />}
                    {activeTab === 'inactive' && <UserTable users={inactiveUsers} type="inactive" onAction={handleAction} />}
                </>
            )}
        </div>
    );
};

export default UserManagementPage;
