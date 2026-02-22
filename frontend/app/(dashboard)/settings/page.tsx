'use client'
'use client';

import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    Settings as SettingsIcon,
    Server,
    Brain,
    Database,
    Save,
    RefreshCw,
    Loader2,
    CheckCircle,
    AlertCircle,
} from 'lucide-react';
import { getSettings, saveSettings, Settings } from '@/lib/api';

export default function SettingsPage() {
    const queryClient = useQueryClient();
    const [localSettings, setLocalSettings] = useState<Settings>({
        api_url: 'http://localhost:8000',
        timeout: 15,
        headless: true,
        confidence_threshold: 0.6,
        max_candidates: 100,
        retention_days: 30,
        auto_retrain: false,
    });
    const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');

    const { data: settings, isLoading, isError } = useQuery({
        queryKey: ['settings'],
        queryFn: getSettings,
    });

    useEffect(() => {
        if (settings) {
            setLocalSettings(settings);
        }
    }, [settings]);

    const saveMutation = useMutation({
        mutationFn: saveSettings,
        onSuccess: (data) => {
            setLocalSettings(data);
            queryClient.invalidateQueries({ queryKey: ['settings'] });
            setSaveStatus('success');
            setTimeout(() => setSaveStatus('idle'), 3000);
        },
        onError: () => {
            setSaveStatus('error');
            setTimeout(() => setSaveStatus('idle'), 3000);
        },
    });

    const handleSave = () => {
        saveMutation.mutate(localSettings);
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-[50vh]">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
        );
    }

    if (isError) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center py-20 bg-red-50 rounded-xl border border-red-100">
                    <AlertCircle className="w-16 h-16 text-red-400 mb-4" />
                    <h2 className="text-xl font-bold text-gray-900 mb-2">Failed to Load Settings</h2>
                    <p className="text-gray-500 mb-4">Could not connect to backend</p>
                    <button onClick={() => window.location.reload()} className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-sm font-medium">
                        Reload Page
                    </button>
                </div>
            </div>
        );
    }

        return (
            <div className="p-6 max-w-4xl">
                <div className="space-y-6">
                    {/* API Configuration */}
                    <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                                <Server className="w-5 h-5 text-blue-600" />
                            </div>
                            <div>
                                <h3 className="text-lg font-semibold text-gray-900">API Configuration</h3>
                                <p className="text-sm text-gray-500">Backend server settings</p>
                            </div>
                        </div>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">API Base URL</label>
                            <input
                                type="url"
                                value={localSettings.api_url}
                                onChange={(e) => setLocalSettings({ ...localSettings, api_url: e.target.value })}
                                className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Request Timeout (seconds)</label>
                            <input
                                type="number"
                                value={localSettings.timeout}
                                onChange={(e) => setLocalSettings({ ...localSettings, timeout: parseInt(e.target.value) })}
                                min={5}
                                max={60}
                                className="w-32 px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                    </div>
                </div>

                {/* Browser Settings */}
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                            <SettingsIcon className="w-5 h-5 text-purple-600" />
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-gray-900">Browser Settings</h3>
                            <p className="text-sm text-gray-500">Selenium WebDriver configuration</p>
                        </div>
                    </div>
                    <label className="flex items-center justify-between p-4 bg-gray-50 rounded-lg cursor-pointer">
                        <div>
                            <p className="font-medium text-gray-900">Headless Mode</p>
                            <p className="text-sm text-gray-500">Run browser without GUI</p>
                        </div>
                        <div className="relative">
                            <input
                                type="checkbox"
                                checked={localSettings.headless}
                                onChange={(e) => setLocalSettings({ ...localSettings, headless: e.target.checked })}
                                className="sr-only"
                            />
                            <div className={`w-11 h-6 rounded-full transition-colors flex items-center px-1 ${localSettings.headless ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                <div className={`w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${localSettings.headless ? 'translate-x-5' : 'translate-x-0'}`} />
                            </div>
                        </div>
                    </label>
                </div>

                {/* ML Settings */}
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                            <Brain className="w-5 h-5 text-green-600" />
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-gray-900">ML Settings</h3>
                            <p className="text-sm text-gray-500">Self-healing model parameters</p>
                        </div>
                    </div>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Confidence Threshold</label>
                            <div className="flex items-center gap-4">
                                <input
                                    type="range"
                                    value={localSettings.confidence_threshold}
                                    onChange={(e) => setLocalSettings({ ...localSettings, confidence_threshold: parseFloat(e.target.value) })}
                                    min={0.3}
                                    max={0.95}
                                    step={0.05}
                                    className="flex-1"
                                />
                                <span className="w-16 text-center font-medium text-gray-900">
                                    {(localSettings.confidence_threshold * 100).toFixed(0)}%
                                </span>
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Max Candidates</label>
                            <input
                                type="number"
                                value={localSettings.max_candidates}
                                onChange={(e) => setLocalSettings({ ...localSettings, max_candidates: parseInt(e.target.value) })}
                                min={10}
                                max={500}
                                className="w-32 px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                        <label className="flex items-center justify-between p-3 border border-gray-100 rounded-lg cursor-pointer">
                            <span className="text-sm font-medium text-gray-700">Auto-Retrain Model</span>
                            <div className="relative">
                                <input
                                    type="checkbox"
                                    checked={localSettings.auto_retrain}
                                    onChange={(e) => setLocalSettings({ ...localSettings, auto_retrain: e.target.checked })}
                                    className="sr-only"
                                />
                                <div className={`w-9 h-5 rounded-full transition-colors flex items-center px-0.5 ${localSettings.auto_retrain ? 'bg-green-500' : 'bg-gray-200'}`}>
                                    <div className={`w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${localSettings.auto_retrain ? 'translate-x-4' : 'translate-x-0'}`} />
                                </div>
                            </div>
                        </label>
                    </div>
                </div>

                {/* Data Retention */}
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                            <Database className="w-5 h-5 text-orange-600" />
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-gray-900">Data Retention</h3>
                            <p className="text-sm text-gray-500">History and log storage</p>
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">Retention Period (days)</label>
                        <input
                            type="number"
                            value={localSettings.retention_days}
                            onChange={(e) => setLocalSettings({ ...localSettings, retention_days: parseInt(e.target.value) })}
                            min={7}
                            max={365}
                            className="w-32 px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-4 sticky bottom-6 bg-white/80 backdrop-blur p-4 rounded-xl border border-gray-200 shadow-lg mb-6">
                    <button
                        onClick={handleSave}
                        disabled={saveMutation.isPending}
                        className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white font-semibold rounded-lg hover:opacity-90 disabled:opacity-50 transition-all"
                    >
                        {saveMutation.isPending ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Saving...
                            </>
                        ) : saveStatus === 'success' ? (
                            <>
                                <CheckCircle className="w-5 h-5" />
                                Saved!
                            </>
                        ) : (
                            <>
                                <Save className="w-5 h-5" />
                                Save Settings
                            </>
                        )}
                    </button>
                    <button
                        onClick={() => settings && setLocalSettings(settings)}
                        className="flex items-center gap-2 px-6 py-3 border border-gray-200 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors"
                        disabled={saveMutation.isPending}
                    >
                        <RefreshCw className={`w-5 h-5 ${saveMutation.isPending ? 'animate-spin' : ''}`} />
                        Reset
                    </button>
                    {saveStatus === 'error' && (
                        <span className="text-red-500 text-sm font-medium flex items-center gap-1 animate-pulse">
                            <AlertCircle className="w-4 h-4" />
                            Failed to save
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}
