'use client';

import { ReactNode } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';

interface ClientLayoutProps {
    children: ReactNode;
    title?: string;
    subtitle?: string;
}

export default function ClientLayout({ children, title, subtitle }: ClientLayoutProps) {
    return (
        <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex-1 flex flex-col overflow-hidden">
                <Header title={title || 'Dashboard'} subtitle={subtitle || ''} />
                <main className="flex-1 overflow-auto">
                    {children}
                </main>
            </div>
        </div>
    );
}
