'use client';

import { useQuery } from '@tanstack/react-query';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
} from 'recharts';
import {
    Activity,
    CheckCircle,
    AlertCircle,
    Brain,
    Clock,
    Zap,
    Target,
    Loader2,
    WifiOff,
    RefreshCw,
} from 'lucide-react';
import StatCard from '@/components/StatCard';
import { getModelStatus, getSelectorHistory, getLogs, getHealth, getHealingTrend } from '@/lib/api';

export default function DashboardPage() {
    const { data: health, isLoading: healthLoading, isError: healthError, refetch: refetchHealth } = useQuery({
        queryKey: ['health'],
        queryFn: getHealth,
        retry: 1,
        refetchInterval: 10000,
    });

    const { data: modelStatus, isLoading: modelLoading } = useQuery({
        queryKey: ['modelStatus'],
        queryFn: getModelStatus,
        enabled: !!health,
        refetchInterval: 30000,
    });

    const { data: trendData, isLoading: trendLoading } = useQuery({
        queryKey: ['healingTrend'],
        queryFn: () => getHealingTrend(7),
        enabled: !!health,
    });

    const { data: logsData, isLoading: logsLoading } = useQuery({
        queryKey: ['logs'],
        queryFn: () => getLogs(1, 5),
        enabled: !!health,
    });

    const isConnected = !!health && !healthError;
    const isLoading = healthLoading;

    const healingStats = modelStatus?.healing_stats || {
        total_attempts: 0,
        success_rate: 0,
        avg_confidence: 0,
        avg_healing_time_ms: 0,
    };

    const healingTrendData = trendData?.trend || [];

    const strategyData = modelStatus?.xpath_stats ?
        Object.entries(modelStatus.xpath_stats).map(([name, value], i) => ({
            name,
            value: Number(value) || 0,
            color: ['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B'][i % 4],
        })) : [
            { name: 'ID-based', value: 0, color: '#3B82F6' },
            { name: 'Class-based', value: 0, color: '#8B5CF6' },
            { name: 'Attribute', value: 0, color: '#10B981' },
            { name: 'Hierarchy', value: 0, color: '#F59E0B' },
        ];

    if (healthError) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center py-20">
                    <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mb-6">
                        <WifiOff className="w-10 h-10 text-red-500" />
                    </div>
                    <h2 className="text-2xl font-bold text-gray-900 mb-2">Backend Not Connected</h2>
                    <p className="text-gray-500 mb-6 text-center max-w-md">
                        Cannot connect to the API server at <code className="bg-gray-100 px-2 py-1 rounded">localhost:8000</code>
                    </p>
                    <div className="bg-gray-50 rounded-lg p-4 mb-6 text-left">
                        <p className="text-sm font-medium text-gray-700 mb-2">To start the backend:</p>
                        <code className="text-sm bg-gray-900 text-green-400 px-4 py-2 rounded block">
                            cd backend && pip3 install -r requirements.txt && uvicorn main:app --reload
                        </code>
                    </div>
                    <button
                        onClick={() => refetchHealth()}
                        className="flex items-center gap-2 px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                    >
                        <RefreshCw className="w-5 h-5" />
                        Retry Connection
                    </button>
                </div>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center py-20">
                    <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
                    <p className="text-gray-500">Connecting to backend...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6">
            {/* Connection Status Banner */}
            <div className={`flex items-center gap-3 px-4 py-3 rounded-lg ${isConnected ? 'bg-green-50 border border-green-200' : 'bg-yellow-50 border border-yellow-200'}`}>
                {isConnected ? (
                    <>
                        <CheckCircle className="w-5 h-5 text-green-600" />
                        <span className="text-sm font-medium text-green-800">
                            Connected to backend - v{health?.version || '1.0.0'}
                        </span>
                        <span className="text-xs text-green-600 ml-auto">
                            DB: {health?.database_connected ? '✓' : '✗'} | Model: {health?.model_loaded ? '✓' : '✗'}
                        </span>
                    </>
                ) : (
                    <>
                        <AlertCircle className="w-5 h-5 text-yellow-600" />
                        <span className="text-sm font-medium text-yellow-800">Connecting...</span>
                    </>
                )}
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard
                    title="Total Healings"
                    value={healingStats.total_attempts}
                    change={healingStats.total_attempts > 0 ? "From API" : "No data yet"}
                    changeType={healingStats.total_attempts > 0 ? "positive" : "neutral"}
                    icon={<Zap className="w-6 h-6" />}
                    color="blue"
                />
                <StatCard
                    title="Success Rate"
                    value={`${(healingStats.success_rate * 100).toFixed(1)}%`}
                    change={healingStats.success_rate > 0 ? "From API" : "No data yet"}
                    changeType={healingStats.success_rate > 0.8 ? "positive" : "neutral"}
                    icon={<Target className="w-6 h-6" />}
                    color="green"
                />
                <StatCard
                    title="Avg Confidence"
                    value={`${(healingStats.avg_confidence * 100).toFixed(0)}%`}
                    change="ML model accuracy"
                    changeType="neutral"
                    icon={<Brain className="w-6 h-6" />}
                    color="purple"
                />
                <StatCard
                    title="Avg Heal Time"
                    value={`${healingStats.avg_healing_time_ms.toFixed(0)}ms`}
                    change={healingStats.avg_healing_time_ms > 0 ? "From API" : "No data yet"}
                    changeType="neutral"
                    icon={<Clock className="w-6 h-6" />}
                    color="orange"
                />
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h3 className="text-lg font-semibold text-gray-900">Healing Trend</h3>
                            <p className="text-sm text-gray-500">Success vs Failed healings over time</p>
                        </div>
                        {trendLoading && <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />}
                    </div>
                    {healingTrendData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={280}>
                            <AreaChart data={healingTrendData}>
                                <defs>
                                    <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                                    </linearGradient>
                                    <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#F87171" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#F87171" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                                <XAxis dataKey="name" stroke="#9CA3AF" fontSize={12} />
                                <YAxis stroke="#9CA3AF" fontSize={12} />
                                <Tooltip contentStyle={{ backgroundColor: '#fff', border: '1px solid #E5E7EB', borderRadius: '8px' }} />
                                <Area type="monotone" dataKey="success" stroke="#3B82F6" strokeWidth={2} fillOpacity={1} fill="url(#colorSuccess)" />
                                <Area type="monotone" dataKey="failed" stroke="#F87171" strokeWidth={2} fillOpacity={1} fill="url(#colorFailed)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-[280px] text-gray-400">
                            <Activity className="w-12 h-12 mb-3" />
                            <p>No healing data yet</p>
                            <p className="text-sm">Run a scrape to see trends</p>
                        </div>
                    )}
                </div>

                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">XPath Strategies</h3>
                    <p className="text-sm text-gray-500 mb-4">Distribution by strategy type</p>
                    {strategyData.some(s => s.value > 0) ? (
                        <>
                            <ResponsiveContainer width="100%" height={200}>
                                <PieChart>
                                    <Pie data={strategyData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={2} dataKey="value">
                                        {strategyData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={entry.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="grid grid-cols-2 gap-2 mt-4">
                                {strategyData.map((item) => (
                                    <div key={item.name} className="flex items-center gap-2">
                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                                        <span className="text-xs text-gray-600">{item.name}</span>
                                        <span className="text-xs font-medium text-gray-900">{item.value}</span>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-[250px] text-gray-400">
                            <Target className="w-10 h-10 mb-2" />
                            <p className="text-sm">No strategy data</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Recent Activity & Model Status */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-gray-900">Recent Healing Events</h3>
                        {logsLoading && <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />}
                    </div>
                    <div className="space-y-4">
                        {logsData?.logs && logsData.logs.length > 0 ? (
                            logsData.logs.slice(0, 5).map((log, i) => (
                                <div key={log.id || i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                                    {log.level === 'INFO' ? (
                                        <CheckCircle className="w-5 h-5 text-green-500 mt-0.5" />
                                    ) : (
                                        <AlertCircle className="w-5 h-5 text-amber-500 mt-0.5" />
                                    )}
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-gray-900 truncate">{log.message || 'Healing event'}</p>
                                        <p className="text-xs text-gray-500 mt-1">{log.level}</p>
                                    </div>
                                    <span className="text-xs text-gray-400">
                                        {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                                    </span>
                                </div>
                            ))
                        ) : (
                            <div className="flex flex-col items-center justify-center py-8 text-gray-400">
                                <Activity className="w-10 h-10 mb-2" />
                                <p className="text-sm">No healing events yet</p>
                            </div>
                        )}
                    </div>
                </div>

                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-gray-900">ML Model Status</h3>
                        {modelLoading ? (
                            <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                        ) : modelStatus?.model?.is_trained ? (
                            <div className="flex items-center gap-2 px-3 py-1 bg-green-50 rounded-full">
                                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                                <span className="text-xs font-medium text-green-700">Trained</span>
                            </div>
                        ) : (
                            <div className="flex items-center gap-2 px-3 py-1 bg-yellow-50 rounded-full">
                                <div className="w-2 h-2 bg-yellow-500 rounded-full" />
                                <span className="text-xs font-medium text-yellow-700">Not Trained</span>
                            </div>
                        )}
                    </div>
                    <div className="p-4 bg-gradient-to-br from-blue-50 to-purple-50 rounded-lg">
                        <div className="flex items-center gap-3 mb-3">
                            <Brain className="w-8 h-8 text-blue-600" />
                            <div>
                                <p className="font-semibold text-gray-900">{modelStatus?.model?.model_type || 'Loading...'}</p>
                                <p className="text-xs text-gray-500">Primary Prediction Model</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4 mt-4">
                            <div>
                                <p className="text-xs text-gray-500">Accuracy</p>
                                <p className="text-lg font-bold text-gray-900">
                                    {modelStatus?.model?.accuracy ? `${(modelStatus.model.accuracy * 100).toFixed(1)}%` : '--'}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-500">F1 Score</p>
                                <p className="text-lg font-bold text-gray-900">
                                    {modelStatus?.model?.f1_score ? `${(modelStatus.model.f1_score * 100).toFixed(1)}%` : '--'}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
