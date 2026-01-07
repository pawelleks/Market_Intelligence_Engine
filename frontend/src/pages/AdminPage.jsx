import React, { useState } from 'react';
import FredPipeline from '../components/FredPipeline';
import AdminUserManagement from '../components/AdminUserManagement';

const AdminPage = () => {
    const [activeTab, setActiveTab] = useState('users'); // Default to users as it's the nav link

    return (
        <div style={{ padding: '20px', maxWidth: '1600px', margin: '0 auto' }}>
            <h1 style={{ color: '#fff', marginBottom: '20px' }}>Admin Dashboard</h1>

            {/* Tabs Header */}
            <div style={{
                display: 'flex',
                gap: '10px',
                marginBottom: '20px',
                borderBottom: '1px solid #334155',
                paddingBottom: '10px'
            }}>
                <button
                    onClick={() => setActiveTab('users')}
                    style={{
                        padding: '10px 20px',
                        backgroundColor: activeTab === 'users' ? '#3b82f6' : 'transparent',
                        color: activeTab === 'users' ? '#fff' : '#94a3b8',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontWeight: activeTab === 'users' ? 'bold' : 'normal'
                    }}
                >
                    User Management
                </button>
                <button
                    onClick={() => setActiveTab('fred')}
                    style={{
                        padding: '10px 20px',
                        backgroundColor: activeTab === 'fred' ? '#3b82f6' : 'transparent',
                        color: activeTab === 'fred' ? '#fff' : '#94a3b8',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontWeight: activeTab === 'fred' ? 'bold' : 'normal'
                    }}
                >
                    FRED Data
                </button>
            </div>

            {/* Tab Content */}
            <div style={{ minHeight: '600px' }}>
                {activeTab === 'users' && <AdminUserManagement />}
                {activeTab === 'fred' && <FredPipeline />}
            </div>
        </div>
    );
};

export default AdminPage;
