import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

// Converted to JSX as project seems to be JS based on file extensions
export const TermsModal = ({ isOpen, onAccept, onDecline }) => {
    const [termsContent, setTermsContent] = useState('');
    const [termsVersion, setTermsVersion] = useState('');
    const [loading, setLoading] = useState(true);
    const [accepting, setAccepting] = useState(false);

    const [checks, setChecks] = useState({
        experimental: false,
        notAdvice: false,
        notifications: false,
        ageAndAccept: false,
    });

    const allChecked = Object.values(checks).every(v => v);

    useEffect(() => {
        if (isOpen) {
            fetchTerms();
        }
    }, [isOpen]);

    const fetchTerms = async () => {
        try {
            const response = await fetch('/api/users/terms/current');
            // Added localhost:8000 assuming dev environment, or use /api relative if proxy setup?
            // Usually relative /api is better if proxy is configured (vite).
            // I'll stick to relative path as per user code, assuming proxy.
            // If not, I might need full URL.
            // User code used '/api/users/terms/current'.

            const data = await response.json();
            setTermsContent(data.content);
            setTermsVersion(data.version);
            setLoading(false);
        } catch (error) {
            console.error('Failed to load terms:', error);
            // Fallback or retry?
        }
    };

    const handleAccept = async () => {
        if (!allChecked) return;

        setAccepting(true);
        try {
            await onAccept(termsVersion);
        } catch (error) {
            console.error('Failed to accept terms:', error);
            alert('Failed to accept terms. Please try again.');
        } finally {
            setAccepting(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] flex flex-col">
                {/* Header */}
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                        Welcome to BlindMonkey.io
                    </h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        Please review and accept our Terms of Use to continue
                    </p>
                </div>

                {/* Terms Content (Scrollable) */}
                <div className="p-6 overflow-y-auto flex-1">
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                        </div>
                    ) : (
                        <div className="prose dark:prose-invert max-w-none text-left">
                            <ReactMarkdown>{termsContent}</ReactMarkdown>
                        </div>
                    )}
                </div>

                {/* Checkboxes */}
                <div className="p-6 border-t border-gray-200 dark:border-gray-700 space-y-3">
                    <label className="flex items-start space-x-3 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={checks.experimental}
                            onChange={(e) => setChecks({ ...checks, experimental: e.target.checked })}
                            className="mt-1 h-4 w-4 text-blue-600 rounded"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300 text-left">
                            I acknowledge this is an experimental platform and data may be incomplete or inaccurate
                        </span>
                    </label>

                    <label className="flex items-start space-x-3 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={checks.notAdvice}
                            onChange={(e) => setChecks({ ...checks, notAdvice: e.target.checked })}
                            className="mt-1 h-4 w-4 text-blue-600 rounded"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300 text-left">
                            <strong>I understand this is NOT financial advice</strong> and I am solely responsible for my investment decisions
                        </span>
                    </label>

                    <label className="flex items-start space-x-3 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={checks.notifications}
                            onChange={(e) => setChecks({ ...checks, notifications: e.target.checked })}
                            className="mt-1 h-4 w-4 text-blue-600 rounded"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300 text-left">
                            I agree to receive email notifications about updates, features, and analysis
                        </span>
                    </label>

                    <label className="flex items-start space-x-3 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={checks.ageAndAccept}
                            onChange={(e) => setChecks({ ...checks, ageAndAccept: e.target.checked })}
                            className="mt-1 h-4 w-4 text-blue-600 rounded"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300 text-left">
                            I am 18+ years old and accept these Terms of Use
                        </span>
                    </label>
                </div>

                {/* Actions */}
                <div className="p-6 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
                    <button
                        onClick={onDecline}
                        className="px-6 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition"
                    >
                        Decline
                    </button>
                    <button
                        onClick={handleAccept}
                        disabled={!allChecked || accepting}
                        className={`px-6 py-2 rounded-lg transition ${allChecked && !accepting
                            ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
                            : 'bg-gray-300 dark:bg-gray-700 text-gray-500 cursor-not-allowed'
                            }`}
                    >
                        {accepting ? 'Accepting...' : 'Accept Terms & Continue'}
                    </button>
                </div>
            </div>
        </div>
    );
};
