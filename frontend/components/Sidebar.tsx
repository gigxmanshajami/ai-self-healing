'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
    LayoutDashboard,
    Globe,
    History,
    Brain,
    Settings,
    Zap,
    WifiOff,
    Loader2,
    ShoppingBag,
} from 'lucide-react';
import { getHealth } from '@/lib/api';

const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Scrape', href: '/scrape', icon: Globe },
    { name: 'Products', href: '/products', icon: ShoppingBag },
    { name: 'Healing Logs', href: '/healing-logs', icon: History },
    { name: 'Model Insights', href: '/model-insights', icon: Brain },
    { name: 'Settings', href: '/settings', icon: Settings },
];

export default function Sidebar() {
    const pathname = usePathname();

    const { data: health, isLoading, isError } = useQuery({
        queryKey: ['health'],
        queryFn: getHealth,
        retry: 1,
        refetchInterval: 10000,
    });

    const isConnected = !!health && !isError;

    return (
        <aside className="w-64 bg-white border-r border-gray-200 min-h-screen flex flex-col">
            {/* Logo */}
            <div className="h-16 flex items-center px-6 border-b border-gray-200">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                        <Zap className="w-5 h-5 text-white" />
                    </div>
                    <span className="font-bold text-lg text-gray-900">SelfHeal</span>
                </div>
            </div>

            {/* Navigation */}
            <nav className="p-4 space-y-1 flex-1">
                {navigation.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${isActive
                                ? 'bg-blue-50 text-blue-700 font-medium'
                                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                                }`}
                        >
                            <item.icon className={`w-5 h-5 ${isActive ? 'text-blue-600' : ''}`} />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>

            {/* Status Card */}
            <div className="p-4">
                {isLoading ? (
                    <div className="bg-gray-100 rounded-xl p-4 text-center">
                        <Loader2 className="w-6 h-6 text-gray-400 animate-spin mx-auto mb-2" />
                        <p className="text-xs text-gray-500">Connecting...</p>
                    </div>
                ) : isConnected ? (
                    <div className="bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl p-4 text-white">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                            <span className="text-sm font-medium">Backend Connected</span>
                        </div>
                        <p className="text-xs opacity-90">v{health?.version || '1.0.0'}</p>
                        <div className="mt-2 text-xs opacity-80">
                            <p>DB: {health?.database_connected ? '✓ Connected' : '✗ Disconnected'}</p>
                            <p>Model: {health?.model_loaded ? '✓ Loaded' : '✗ Not loaded'}</p>
                        </div>
                    </div>
                ) : (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <WifiOff className="w-4 h-4 text-red-500" />
                            <span className="text-sm font-medium text-red-700">Disconnected</span>
                        </div>
                        <p className="text-xs text-red-600">Backend not running</p>
                        <p className="text-xs text-red-500 mt-1">Start with: uvicorn main:app</p>
                    </div>
                )}
            </div>
        </aside>
    );
}
