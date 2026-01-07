import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
    ChevronLeft,
    ChevronRight,
    ChevronDown,
    LogOut,
    User,
    Shield,
    Database
} from 'lucide-react';
import { NAV_DATA } from '../config/navigation';

import Logo from './Logo';

const Sidebar = ({ user, logout }) => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const location = useLocation();

    // State for Accordion Sections (default: all open for discoverability)
    // Using an object map: { 'section_id': boolean }
    const [expandedSections, setExpandedSections] = useState({
        long_term: true,
        trading: true,
        pure_quant: true,
        market: true,
        economy: true,
        settings: true
    });

    const toggleSection = (id) => {
        setExpandedSections(prev => ({
            ...prev,
            [id]: !prev[id]
        }));
    };

    // Styles
    const sidebarWidth = isCollapsed ? '64px' : '260px';
    const transition = 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)';

    const colors = {
        bg: '#0e1525',
        border: '#203049',
        text: '#94a3b8',
        textActive: '#ffffff',
        textHeader: '#64748b', // Lighter for interactivity
        textHeaderHover: '#94a3b8',
        hover: '#1e293b',
        activeBg: 'rgba(59, 130, 246, 0.1)',
        activeBorder: '#3b82f6',
        logout: '#ef4444'
    };

    // Helper to render a navigation link
    const renderNavLink = (item) => {
        const isActive = location.pathname === item.to;
        const Icon = item.icon;

        return (
            <div key={item.to} style={{ padding: '2px 12px' }}>
                <Link
                    to={item.to}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        // High Density Padding: py-1 equivalent (4px top/bottom)
                        padding: '5px 10px',
                        borderRadius: '6px',
                        textDecoration: 'none',
                        color: isActive ? colors.textActive : colors.text,
                        backgroundColor: isActive ? colors.activeBg : 'transparent',
                        borderLeft: isActive ? `3px solid ${colors.activeBorder}` : '3px solid transparent',
                        transition: 'background-color 0.15s, color 0.15s',
                        justifyContent: isCollapsed ? 'center' : 'flex-start',
                    }}
                    onMouseEnter={(e) => {
                        if (!isActive) {
                            e.currentTarget.style.color = '#fff';
                            e.currentTarget.style.backgroundColor = colors.hover;
                        }
                    }}
                    onMouseLeave={(e) => {
                        if (!isActive) {
                            e.currentTarget.style.color = colors.text;
                            e.currentTarget.style.backgroundColor = 'transparent';
                        }
                    }}
                    title={isCollapsed ? item.label : ''}
                >
                    <Icon size={18} strokeWidth={1.5} style={{ flexShrink: 0 }} />

                    {!isCollapsed && (
                        <span style={{
                            fontSize: '0.85rem', // High Density Text (text-sm approx)
                            fontWeight: isActive ? 500 : 400,
                            whiteSpace: 'nowrap',
                            opacity: 1,
                            transition: 'opacity 0.2s',
                        }}>
                            {item.label}
                        </span>
                    )}
                </Link>
            </div>
        );
    };

    return (
        <nav style={{
            width: sidebarWidth,
            backgroundColor: colors.bg,
            borderRight: `1px solid ${colors.border}`,
            display: 'flex',
            flexDirection: 'column',
            height: '100vh',
            transition: transition,
            position: 'relative',
            flexShrink: 0,
            overflow: 'hidden'
        }}>
            {/* 1. Toggle Header */}
            <div style={{
                padding: isCollapsed ? '16px 0' : '16px 20px',
                display: 'flex',
                justifyContent: isCollapsed ? 'center' : 'space-between',
                alignItems: 'center',
                borderBottom: `1px solid ${colors.border}`,
                flexShrink: 0 // Prevent shrinking
            }}>
                {/* LOGO */}
                {!isCollapsed && (
                    <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
                        <Logo fontSize="1.25rem" />
                    </Link>
                )}

                <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    style={{
                        background: 'transparent',
                        border: 'none',
                        color: colors.text,
                        cursor: 'pointer',
                        padding: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: '4px',
                    }}
                    title={isCollapsed ? "Expand" : "Collapse"}
                >
                    {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
                </button>
            </div>

            {/* 2. Scrollable Content Area */}
            <div style={{
                flexGrow: 1,
                overflowY: 'auto',
                overflowX: 'hidden',
                paddingTop: '10px',
                paddingBottom: '20px',
                // Custom Scrollbar styling for Webkit
                scrollbarWidth: 'thin',
                scrollbarColor: `${colors.border} transparent`
            }}>
                {/* Admin Link Special Case */}
                {user && user.is_admin && !isCollapsed && (
                    <div style={{ marginBottom: '8px', padding: '0 12px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                        <Link
                            to="/admin/users"
                            style={{
                                display: 'flex', alignItems: 'center', gap: '12px', padding: '6px 10px',
                                borderRadius: '6px', textDecoration: 'none', color: '#ef4444', fontWeight: 'bold', fontSize: '0.85rem'
                            }}
                        >
                            <User size={16} />
                            <span>User Management</span>
                        </Link>
                        <Link
                            to="/admin/data"
                            style={{
                                display: 'flex', alignItems: 'center', gap: '12px', padding: '6px 10px',
                                borderRadius: '6px', textDecoration: 'none', color: '#ef4444', fontWeight: 'bold', fontSize: '0.85rem'
                            }}
                        >
                            <Database size={16} />
                            <span>Data Management</span>
                        </Link>
                    </div>
                )}

                {/* Admin Icon Only */}
                {user && user.is_admin && isCollapsed && (
                    <div style={{ display: 'flex', justifyContent: 'center', flexDirection: 'column', alignItems: 'center', marginBottom: '10px', gap: '10px' }}>
                        <Link to="/admin/users" title="User Management" style={{ color: '#ef4444' }}>
                            <User size={18} />
                        </Link>
                        <Link to="/admin/data" title="Data Management" style={{ color: '#ef4444' }}>
                            <Database size={18} />
                        </Link>
                    </div>
                )}

                {/* Start/Top Items */}
                {NAV_DATA.start.map(item => renderNavLink(item))}

                {/* Sections */}
                {NAV_DATA.sections.map((section) => {
                    const isOpen = expandedSections[section.id];

                    // SECURITY CHECK:
                    // Hide "Settings & Utilities" for non-admins
                    if (section.title === 'Settings & Utilities') {
                        if (!user || !user.is_admin) return null;
                    }

                    // If collapsed, we just show the items flat (without headers) or with a spacer
                    if (isCollapsed) {
                        return (
                            <div key={section.id}>
                                <div style={{ height: '16px' }} /> {/* Spacer between groups */}
                                {section.items.map(item => renderNavLink(item))}
                            </div>
                        );
                    }

                    return (
                        <div key={section.id} style={{ marginTop: '4px' }}>
                            {/* Interactive Header */}
                            <div
                                onClick={() => toggleSection(section.id)}
                                style={{
                                    padding: '8px 24px 4px 24px', // Compact Header
                                    fontSize: '0.75rem', // text-xs
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                    color: colors.textHeader,
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    userSelect: 'none',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    transition: 'color 0.2s'
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.color = colors.textHeaderHover}
                                onMouseLeave={(e) => e.currentTarget.style.color = colors.textHeader}
                            >
                                <span>{section.title}</span>
                                {/* Rotating Chevron */}
                                <div style={{
                                    transition: 'transform 0.2s ease',
                                    transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                                    display: 'flex', // fix vertical align
                                    opacity: 0.7
                                }}>
                                    <ChevronDown size={14} />
                                </div>
                            </div>

                            {/* Accordion Body */}
                            <div style={{
                                height: isOpen ? 'auto' : 0,
                                overflow: 'hidden',
                                display: isOpen ? 'block' : 'none'
                            }}>
                                {section.items.map(item => {
                                    return renderNavLink(item);
                                })}
                            </div>
                        </div>
                    );
                })}

            </div>

            {/* 3. Pinned Footer */}
            <div style={{
                padding: isCollapsed ? '16px' : '16px 20px',
                borderTop: `1px solid ${colors.border}`,
                backgroundColor: '#0b111e',
                flexShrink: 0, // Ensure it stays at bottom
                zIndex: 10
            }}>
                {isCollapsed ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '15px' }}>
                        <User size={18} color={colors.text} />
                        <button
                            onClick={logout}
                            style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: colors.logout }}
                            title="Sign Out"
                        >
                            <LogOut size={18} />
                        </button>
                    </div>
                ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                            <div style={{
                                width: '28px', height: '28px', borderRadius: '50%', background: '#1e293b',
                                display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', flexShrink: 0
                            }}>
                                {user && user.picture ? (
                                    <img src={user.picture} alt="User" style={{ width: '100%', borderRadius: '50%' }} />
                                ) : (
                                    <User size={14} />
                                )}
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                                <span style={{ fontSize: '0.8rem', color: '#fff', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {user ? (user.name || user.email?.split('@')[0]) : 'Guest'}
                                </span>
                                <span style={{ fontSize: '0.7rem', color: colors.text }}>
                                    {user && user.is_admin ? 'Admin' : 'Viewer'}
                                </span>
                            </div>
                        </div>

                        <button
                            onClick={logout}
                            title="Sign Out"
                            style={{
                                background: 'transparent',
                                border: 'none',
                                color: colors.logout,
                                cursor: 'pointer',
                                padding: '4px',
                                display: 'flex'
                            }}
                        >
                            <LogOut size={16} />
                        </button>
                    </div>
                )}
            </div>
        </nav>
    );
};

export default Sidebar;
