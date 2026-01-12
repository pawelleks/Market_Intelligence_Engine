
import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { useLocation, Link } from 'react-router-dom';
import { ChevronLeft, FileText, Download } from 'lucide-react';

const MarkdownViewer = () => {
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const location = useLocation();

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        // Supports full URL or relative path
        const path = params.get('path');

        if (!path) {
            setError("No report path specified.");
            setLoading(false);
            return;
        }

        setLoading(true);
        fetch(path)
            .then(res => {
                if (!res.ok) throw new Error(`Failed to load report (Status ${res.status}): ${res.statusText}`);
                return res.text();
            })
            .then(text => {
                setContent(text);
                setLoading(false);
            })
            .catch(err => {
                console.error("Error fetching report:", err);
                setError(err.message);
                setLoading(false);
            });
    }, [location]);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-slate-900">
                <div className="text-blue-400 text-lg flex items-center gap-2">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-400"></div>
                    Loading Report...
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-slate-900">
                <div className="bg-red-900/30 border border-red-500/50 p-8 rounded-lg max-w-md text-center">
                    <h3 className="text-xl font-bold text-red-400 mb-2">Error Loading Report</h3>
                    <p className="text-slate-300">{error}</p>
                    <Link to="/analysis/prediction" className="mt-6 inline-flex items-center text-blue-400 hover:text-blue-300">
                        <ChevronLeft className="w-4 h-4 mr-1" /> Back to Dashboard
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-900 text-slate-200">
            {/* Header */}
            <div className="bg-slate-800 border-b border-slate-700 sticky top-0 z-10 shadow-md">
                <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
                    <Link to="/analysis/prediction" className="flex items-center text-slate-400 hover:text-white transition-colors">
                        <ChevronLeft className="w-5 h-5 mr-1" />
                        Back to Dashboard
                    </Link>
                    <div className="flex items-center gap-2 text-slate-200 font-semibold">
                        <FileText className="w-5 h-5 text-blue-400" />
                        Report Viewer
                    </div>
                </div>
            </div>

            <div className="max-w-5xl mx-auto p-6 md:p-10">
                <div className="bg-slate-800/50 rounded-lg p-8 md:p-12 shadow-xl border border-slate-700">
                    <article className="prose prose-invert prose-blue max-w-none prose-headings:text-blue-100 prose-a:text-blue-400 prose-strong:text-white prose-table:border-slate-700 prose-th:bg-slate-700 prose-td:border-slate-700">
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeRaw]}
                            components={{
                                a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
                                table: ({ node, ...props }) => <div className="overflow-x-auto my-6"><table {...props} className="w-full text-left border-collapse" /></div>,
                                th: ({ node, ...props }) => <th {...props} className="bg-slate-700/50 p-2 border border-slate-600 font-bold" />,
                                td: ({ node, ...props }) => <td {...props} className="p-2 border border-slate-600" />
                            }}
                        >
                            {content}
                        </ReactMarkdown>
                    </article>
                </div>
            </div>
        </div>
    );
};

export default MarkdownViewer;
