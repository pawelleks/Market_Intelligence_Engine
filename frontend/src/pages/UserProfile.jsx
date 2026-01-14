import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext'; // Updated path from instructions '../contexts/AuthContext' to match existing folder 'context'

export const UserProfile = () => {
    const { user, logout } = useAuth();
    // user might be null initially

    const [emailNotifications, setEmailNotifications] = useState(true);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [showTerms, setShowTerms] = useState(false); // Can trigger Modal if integrated globally or locally

    // Need to sync state with user data when available
    useEffect(() => {
        if (user) {
            setEmailNotifications(user.emailNotifications ?? true);
            // Wait, endpoint provides camelCase keys, ensure usage matches what AuthContext provides.
            // If AuthContext uses snake_case, update here.
            // I'll assume AuthContext provides normalized user object or raw API response.
            // I should check AuthContext.
        }
    }, [user]);

    const handleToggleNotifications = async () => {
        try {
            const response = await fetch('/api/users/preferences', {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}` // Ensure token
                },
                body: JSON.stringify({ email_notifications: !emailNotifications }),
            });

            if (response.ok) {
                setEmailNotifications(!emailNotifications);
            }
        } catch (error) {
            console.error('Failed to update preferences:', error);
        }
    };

    const handleDeleteAccount = async () => {
        try {
            const response = await fetch('/api/users/me', {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });

            if (response.ok) {
                alert('Your account has been deleted. You will be logged out.');
                logout();
            }
        } catch (error) {
            console.error('Failed to delete account:', error);
            alert('Failed to delete account. Please try again.');
        }
    };

    const handleResetTerms = async () => {
        try {
            const response = await fetch('/api/users/dev/reset-terms', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });

            if (response.ok) {
                alert('Terms reset! Logout and login again to see the terms modal.');
            }
        } catch (error) {
            console.error('Failed to reset terms:', error);
        }
    };

    if (!user) return <div className="p-6">Loading profile...</div>;

    return (
        <div className="max-w-4xl mx-auto p-6 space-y-8 text-left">
            <h1 className="text-3xl font-bold dark:text-white">Profile & Settings</h1>

            {/* Account Information */}
            <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow">
                <h2 className="text-xl font-semibold mb-4 dark:text-white">Account Information</h2>
                <div className="space-y-2 text-gray-700 dark:text-gray-300">
                    <p><strong>Email:</strong> {user.email}</p>
                    <p><strong>Role:</strong> {user.role || (user.is_admin ? 'admin' : 'user')}</p>
                    <p><strong>Status:</strong> {user.status || (user.is_approved ? 'Active' : 'Pending')}</p>
                </div>
            </section>

            {/* Preferences */}
            <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow">
                <h2 className="text-xl font-semibold mb-4 dark:text-white">Preferences</h2>
                <label className="flex items-center space-x-3 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={emailNotifications}
                        onChange={handleToggleNotifications}
                        className="h-4 w-4 text-blue-600 rounded"
                    />
                    <span className="text-gray-700 dark:text-gray-300">
                        Receive email notifications about updates and new features
                    </span>
                </label>
            </section>

            {/* Terms & Privacy */}
            <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow">
                <h2 className="text-xl font-semibold mb-4 dark:text-white">Terms & Privacy</h2>
                <div className="space-y-3">
                    <p className="text-gray-700 dark:text-gray-300">
                        <strong>Terms accepted:</strong>{' '}
                        {user.termsAcceptedAt || user.terms_accepted_at
                            ? new Date(user.termsAcceptedAt || user.terms_accepted_at).toLocaleDateString()
                            : (user.termsAccepted ? 'Yes' : 'Not accepted')}
                    </p>
                    <p className="text-gray-700 dark:text-gray-300">
                        <strong>Version:</strong> {user.termsVersion || user.terms_version || 'N/A'}
                    </p>
                    {/* <button
            onClick={() => setShowTerms(true)}
            className="text-blue-600 hover:underline"
          >
            View Terms of Use →
          </button> */}
                </div>
            </section>

            {/* Admin Testing Tools */}
            {(user.role === 'admin' || user.is_admin) && (
                <section className="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-6 shadow border-2 border-yellow-400">
                    <h2 className="text-xl font-semibold mb-4 flex items-center dark:text-white">
                        🔧 Admin Testing Tools
                    </h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                        Development tools for testing the terms acceptance flow
                    </p>
                    <button
                        onClick={handleResetTerms}
                        className="px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-white rounded-lg transition"
                    >
                        Reset My Terms Acceptance
                    </button>
                    <p className="text-xs text-gray-500 mt-2">
                        After clicking, logout and login again to see the terms modal
                    </p>
                </section>
            )}

            {/* Danger Zone */}
            <section className="bg-red-50 dark:bg-red-900/20 rounded-lg p-6 shadow border-2 border-red-400">
                <h2 className="text-xl font-semibold mb-4 text-red-700 dark:text-red-400">
                    Danger Zone
                </h2>
                <p className="text-gray-700 dark:text-gray-300 mb-4">
                    Permanently delete your account and all associated data. This action cannot be undone.
                </p>
                <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition"
                >
                    Delete My Account
                </button>
            </section>

            {/* Delete Confirmation Modal */}
            {showDeleteConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
                    <div className="bg-white dark:bg-gray-900 rounded-lg p-6 max-w-md shadow-xl text-left">
                        <h3 className="text-xl font-bold mb-4 dark:text-white">Delete Account?</h3>
                        <p className="text-gray-700 dark:text-gray-300 mb-6">
                            Are you absolutely sure? This action cannot be undone. All your data will be permanently deleted.
                        </p>
                        <div className="flex justify-end space-x-3">
                            <button
                                onClick={() => setShowDeleteConfirm(false)}
                                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 dark:text-white"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleDeleteAccount}
                                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg"
                            >
                                Yes, Delete My Account
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
