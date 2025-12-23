
import React, { useEffect, useState } from 'react';
import { Shield, Check, X, Clock, Eye } from 'lucide-react';

const AdminAllUsersPage = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchUsers = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('/api/v1/admin/users/all', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch users');
            }

            const data = await response.json();
            setUsers(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    if (loading) return <div className="p-8 text-blue-100">Loading users...</div>;
    if (error) return <div className="p-8 text-red-400">Error: {error}</div>;

    return (
        <div className="p-8 min-h-screen bg-slate-900 text-slate-100">
            <h1 className="text-3xl font-bold mb-8 text-blue-400 flex items-center gap-2">
                <Shield className="w-8 h-8" />
                User Management
            </h1>

            <div className="overflow-x-auto bg-slate-800 rounded-lg border border-slate-700">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-slate-900 text-slate-400 border-b border-slate-700">
                            <th className="p-4">ID</th>
                            <th className="p-4">Email</th>
                            <th className="p-4">Name</th>
                            <th className="p-4 text-center">Approved</th>
                            <th className="p-4 text-center">Admin</th>
                            <th className="p-4 text-center">Page Visits</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                        {users.map(user => (
                            <tr key={user.id} className="hover:bg-slate-750">
                                <td className="p-4 font-mono text-slate-500">#{user.id}</td>
                                <td className="p-4 font-medium text-blue-100">{user.email}</td>
                                <td className="p-4 text-slate-300">{user.full_name || '-'}</td>
                                <td className="p-4 text-center">
                                    {user.is_approved ? (
                                        <span className="inline-flex items-center px-2 py-1 rounded bg-green-500/20 text-green-400 text-xs font-bold">
                                            <Check className="w-3 h-3 mr-1" /> Yes
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center px-2 py-1 rounded bg-yellow-500/20 text-yellow-400 text-xs font-bold">
                                            <Clock className="w-3 h-3 mr-1" /> Pending
                                        </span>
                                    )}
                                </td>
                                <td className="p-4 text-center">
                                    {user.is_admin ? (
                                        <span className="inline-flex items-center px-2 py-1 rounded bg-purple-500/20 text-purple-400 text-xs font-bold">
                                            <Shield className="w-3 h-3 mr-1" /> Admin
                                        </span>
                                    ) : (
                                        <span className="text-slate-600">-</span>
                                    )}
                                </td>
                                <td className="p-4 text-center">
                                    <span className="inline-flex items-center px-3 py-1 rounded-full bg-slate-700 text-blue-300 font-mono text-sm">
                                        <Eye className="w-3 h-3 mr-2 text-blue-400" />
                                        {user.visit_count || 0}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="mt-4 text-slate-400 text-sm text-right">
                Total Users: {users.length}
            </div>
        </div>
    );
};

export default AdminAllUsersPage;
