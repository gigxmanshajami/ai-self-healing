'use client';

import { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';

const pageTitles: Record<string, { title: string; subtitle: string }> = {
    '/dashboard': { title: 'Dashboard', subtitle: 'AI Self-Healing Scraper Overview' },
    '/scrape': { title: 'Scrape', subtitle: 'Execute scraping jobs with self-healing' },
    '/healing-logs': { title: 'Healing Logs', subtitle: 'Track all self-healing attempts' },
    '/model-insights': { title: 'Model Insights', subtitle: 'ML model performance and analytics' },
    '/settings': { title: 'Settings', subtitle: 'Configure scraper and model settings' },
};

export default function DashboardLayout({
    children,
}: {
    children: ReactNode;
}) {
    const pathname = usePathname();
    const pageInfo = pageTitles[pathname] || { title: 'Dashboard', subtitle: '' };

    return (
        <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex-1 flex flex-col overflow-hidden">
                <Header title={pageInfo.title} subtitle={pageInfo.subtitle} />
                <main className="flex-1 overflow-auto">
                    {children}
                </main>
            </div>
        </div>
    );
}
