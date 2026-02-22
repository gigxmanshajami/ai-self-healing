'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
    History,
    CheckCircle,
    XCircle,
    Download,
    Search,
    Loader2,
    WifiOff,
    RefreshCw,
} from 'lucide-react';
import { getLogs, getHealth, LogEntry } from '@/lib/api';

export default function HealingLogsPage() {
    const [filter, setFilter] = useState<'all' | 'success' | 'failed'>('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);

    const { data: health, isError: healthError, refetch } = useQuery({
        queryKey: ['health'],
        queryFn: getHealth,
        retry: 1,
    });

    const { data, isLoading } = useQuery({
        queryKey: ['logs', filter],
        queryFn: () => getLogs(1, 100),
        enabled: !!health,
        refetchInterval: 10000,
    });

    const logs = data?.logs || [];

    const filteredLogs = logs.filter((log) => {
        const matchesFilter =
            filter === 'all' ||
            (filter === 'success' && log.level === 'INFO') ||
            (filter === 'failed' && log.level !== 'INFO');
        const matchesSearch =
            !searchQuery ||
            log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
            log.selector?.toLowerCase().includes(searchQuery.toLowerCase());
        return matchesFilter && matchesSearch;
    });

    if (healthError) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center py-20">
                    <WifiOff className="w-16 h-16 text-red-400 mb-4" />
                    <h2 className="text-xl font-bold text-gray-900 mb-2">Backend Not Connected</h2>
                    <p className="text-gray-500 mb-4">Start the backend server to view logs</p>
                    <button onClick={() => refetch()} className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg">
                        <RefreshCw className="w-4 h-4" />
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="p-6">
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
                <div className="p-4 border-b border-gray-100 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input
                                type="text"
                                placeholder="Search logs..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                        <div className="flex items-center gap-2 bg-gray-100 rounded-lg p-1">
                            {(['all', 'success', 'failed'] as const).map((f) => (
                                <button
                                    key={f}
                                    onClick={() => setFilter(f)}
                                    className={`px-3 py-1.5 text-sm rounded-md transition-colors ${filter === f ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                                        }`}
                                >
                                    {f.charAt(0).toUpperCase() + f.slice(1)}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {isLoading && <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />}
                        <button className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg hover:bg-gray-50">
                            <Download className="w-4 h-4" />
                            Export
                        </button>
                    </div>
                </div>

                {filteredLogs.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Message</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Level</th>
                                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-100">
                                {filteredLogs.map((log) => (
                                    <tr key={log.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-4">
                                            {log.level === 'INFO' ? (
                                                <div className="flex items-center gap-2">
                                                    <CheckCircle className="w-5 h-5 text-green-500" />
                                                    <span className="text-sm font-medium text-green-700">Success</span>
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-2">
                                                    <XCircle className="w-5 h-5 text-red-500" />
                                                    <span className="text-sm font-medium text-red-700">Error</span>
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-500">
                                            {format(new Date(log.timestamp), 'MMM d, HH:mm:ss')}
                                        </td>
                                        <td className="px-6 py-4">
                                            <p className="text-sm text-gray-900 max-w-md truncate">{log.message}</p>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`text-xs px-2 py-1 rounded-full ${log.level === 'INFO' ? 'bg-green-100 text-green-700' :
                                                    log.level === 'WARNING' ? 'bg-yellow-100 text-yellow-700' :
                                                        'bg-red-100 text-red-700'
                                                }`}>
                                                {log.level}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <button
                                                onClick={() => setSelectedLog(log)}
                                                className="text-blue-600 hover:text-blue-900 text-sm font-medium"
                                            >
                                                View Details
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                        <History className="w-12 h-12 mb-4" />
                        <p className="font-medium">No healing logs yet</p>
                        <p className="text-sm">Logs will appear here after running scrape jobs</p>
                    </div>
                )}
            </div>

            {/* Details Modal */}
            {selectedLog && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
                        <div className="p-6 border-b border-gray-100 flex items-center justify-between">
                            <h3 className="text-lg font-bold text-gray-900">Log Details</h3>
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="text-gray-400 hover:text-gray-600"
                            >
                                <XCircle className="w-6 h-6" />
                            </button>
                        </div>
                        <div className="p-6 overflow-y-auto font-mono text-sm">
                            <div className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-gray-50 p-3 rounded-lg">
                                        <p className="text-xs text-gray-500 uppercase mb-1">Timestamp</p>
                                        <p className="text-gray-900">{format(new Date(selectedLog.timestamp), 'PPpp')}</p>
                                    </div>
                                    <div className="bg-gray-50 p-3 rounded-lg">
                                        <p className="text-xs text-gray-500 uppercase mb-1">Level</p>
                                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${selectedLog.level === 'INFO' ? 'bg-green-100 text-green-800' :
                                                selectedLog.level === 'WARNING' ? 'bg-yellow-100 text-yellow-800' :
                                                    'bg-red-100 text-red-800'
                                            }`}>
                                            {selectedLog.level}
                                        </span>
                                    </div>
                                </div>

                                <div>
                                    <p className="text-xs text-gray-500 uppercase mb-1">Message</p>
                                    <p className="bg-gray-50 p-3 rounded-lg text-gray-900 whitespace-pre-wrap">{selectedLog.message}</p>
                                </div>

                                {selectedLog.selector && (
                                    <div>
                                        <p className="text-xs text-gray-500 uppercase mb-1">Related Selector</p>
                                        <code className="block bg-gray-900 text-gray-100 p-3 rounded-lg">{selectedLog.selector}</code>
                                    </div>
                                )}

                                <div>
                                    <p className="text-xs text-gray-500 uppercase mb-1">Full Log Object</p>
                                    <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto">
                                        {JSON.stringify(selectedLog, null, 2)}
                                    </pre>
                                </div>
                            </div>
                        </div>
                        <div className="p-4 border-t border-gray-100 bg-gray-50 rounded-b-xl flex justify-end">
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 font-medium"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
