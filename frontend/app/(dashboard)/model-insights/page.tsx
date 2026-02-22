'use client';

import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Brain, Cpu, Database, TrendingUp, Layers, Gauge, Activity, Loader2, WifiOff, RefreshCw } from 'lucide-react';
import { getModelStatus, getHealth } from '@/lib/api';

interface ModelData {
    model_type?: string;
    is_trained?: boolean;
    accuracy?: number;
    precision?: number;
    recall?: number;
    f1_score?: number;
    training_samples?: number;
    feature_importance?: Record<string, number>;
}

interface HealingStats {
    successful_healings?: number;
    failed_healings?: number;
}

export default function ModelInsightsPage() {
    const { data: health, isError: healthError, refetch } = useQuery({
        queryKey: ['health'],
        queryFn: getHealth,
        retry: 1,
    });

    const { data: modelStatus, isLoading } = useQuery({
        queryKey: ['modelStatus'],
        queryFn: getModelStatus,
        enabled: !!health,
        refetchInterval: 30000,
    });

    if (healthError) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center py-20">
                    <WifiOff className="w-16 h-16 text-red-400 mb-4" />
                    <h2 className="text-xl font-bold text-gray-900 mb-2">Backend Not Connected</h2>
                    <p className="text-gray-500 mb-4">Start the backend server to view model insights</p>
                    <button onClick={() => refetch()} className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg">
                        <RefreshCw className="w-4 h-4" />
                        Retry
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
                    <p className="text-gray-500">Loading model data...</p>
                </div>
            </div>
        );
    }

    const model: ModelData = modelStatus?.model || {};
    const healingStats: HealingStats = modelStatus?.healing_stats || {};

    const featureImportance = model.feature_importance
        ? Object.entries(model.feature_importance)
            .map(([name, value], i) => ({
                name,
                value: Number(value),
                color: ['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#6366F1'][i % 7],
            }))
            .sort((a, b) => b.value - a.value)
            .slice(0, 7)
        : [];

    const accuracy = model.accuracy ? `${(model.accuracy * 100).toFixed(1)}%` : '--';
    const precision = model.precision ? `${(model.precision * 100).toFixed(1)}%` : '--';
    const recall = model.recall ? `${(model.recall * 100).toFixed(1)}%` : '--';
    const f1Score = model.f1_score ? `${(model.f1_score * 100).toFixed(1)}%` : '--';

    return (
        <div className="p-6 space-y-6">
            {/* Metrics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                            <Gauge className="w-5 h-5 text-blue-600" />
                        </div>
                        <span className="text-sm font-medium text-gray-500">Accuracy</span>
                    </div>
                    <p className="text-3xl font-bold text-gray-900">{accuracy}</p>
                </div>
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                            <TrendingUp className="w-5 h-5 text-green-600" />
                        </div>
                        <span className="text-sm font-medium text-gray-500">Precision</span>
                    </div>
                    <p className="text-3xl font-bold text-gray-900">{precision}</p>
                </div>
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                            <Activity className="w-5 h-5 text-purple-600" />
                        </div>
                        <span className="text-sm font-medium text-gray-500">Recall</span>
                    </div>
                    <p className="text-3xl font-bold text-gray-900">{recall}</p>
                </div>
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                            <Layers className="w-5 h-5 text-orange-600" />
                        </div>
                        <span className="text-sm font-medium text-gray-500">F1 Score</span>
                    </div>
                    <p className="text-3xl font-bold text-gray-900">{f1Score}</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Feature Importance */}
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">Feature Importance</h3>
                    <p className="text-sm text-gray-500 mb-6">Contribution of each feature to predictions</p>
                    {featureImportance.length > 0 ? (
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={featureImportance} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                                <XAxis type="number" domain={[0, 'auto']} stroke="#9CA3AF" fontSize={12} />
                                <YAxis type="category" dataKey="name" stroke="#9CA3AF" fontSize={11} width={100} />
                                <Tooltip formatter={(value) => [`${(Number(value) * 100).toFixed(1)}%`, 'Importance']} />
                                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                                    {featureImportance.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-[300px] text-gray-400">
                            <Brain className="w-12 h-12 mb-3" />
                            <p>No feature data available</p>
                        </div>
                    )}
                </div>

                {/* Model Config */}
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <h3 className="text-lg font-semibold text-gray-900 mb-6">Model Configuration</h3>
                    <div className="space-y-6">
                        <div className="flex items-center gap-4 p-4 bg-gradient-to-br from-blue-50 to-purple-50 rounded-lg">
                            <Brain className="w-12 h-12 text-blue-600" />
                            <div>
                                <p className="font-semibold text-gray-900">{model.model_type || 'Not configured'}</p>
                                <p className="text-sm text-gray-500">Primary Classification Model</p>
                            </div>
                            <div className="ml-auto">
                                {model.is_trained ? (
                                    <span className="px-3 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full">Trained</span>
                                ) : (
                                    <span className="px-3 py-1 bg-yellow-100 text-yellow-700 text-xs font-medium rounded-full">Not Trained</span>
                                )}
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="p-4 bg-gray-50 rounded-lg">
                                <div className="flex items-center gap-2 text-gray-500 mb-2">
                                    <Database className="w-4 h-4" />
                                    <span className="text-sm">Training Samples</span>
                                </div>
                                <p className="text-2xl font-bold text-gray-900">{model.training_samples?.toLocaleString() || '--'}</p>
                            </div>
                            <div className="p-4 bg-gray-50 rounded-lg">
                                <div className="flex items-center gap-2 text-gray-500 mb-2">
                                    <Cpu className="w-4 h-4" />
                                    <span className="text-sm">Feature Count</span>
                                </div>
                                <p className="text-2xl font-bold text-gray-900">71</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                            <div className="p-3 bg-green-50 rounded-lg text-center">
                                <p className="text-xs text-green-600">Successful</p>
                                <p className="text-lg font-bold text-green-700">{healingStats.successful_healings || 0}</p>
                            </div>
                            <div className="p-3 bg-red-50 rounded-lg text-center">
                                <p className="text-xs text-red-600">Failed</p>
                                <p className="text-lg font-bold text-red-700">{healingStats.failed_healings || 0}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
