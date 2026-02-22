'use client';

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
    Globe,
    Play,
    Plus,
    Trash2,
    CheckCircle,
    XCircle,
    Loader2,
    Sparkles,
    ArrowRight,
    WifiOff,
    RefreshCw,
    Clock,
    Hash,
    Target,
    Zap,
    TrendingUp,
    Shield,
    Activity,
    ImageIcon,
    ExternalLink,
} from 'lucide-react';
import { scrapeUrl, getHealth, getSettings, ScrapeRequest, ScrapeResponse } from '@/lib/api';

interface SelectorField {
    id: string;
    name: string;
    selector: string;
}

/** Check if a value looks like an image URL */
function isImageUrl(value: string): boolean {
    if (!value) return false;
    const v = value.toLowerCase();
    // Check common image extensions
    if (/\.(jpg|jpeg|png|gif|webp|svg|ico|bmp|avif)/i.test(v)) return true;
    // Check common image CDN patterns
    if (v.includes('/image') || v.includes('img') || v.includes('photo') || v.includes('picture')) {
        if (v.startsWith('http') || v.startsWith('/') || v.startsWith('data:image')) return true;
    }
    if (v.startsWith('data:image')) return true;
    return false;
}

/** Resolve a potentially relative URL against a base URL */
function resolveUrl(value: string, baseUrl: string): string {
    if (!value) return value;
    // Already absolute
    if (value.startsWith('http://') || value.startsWith('https://') || value.startsWith('data:')) return value;
    try {
        return new URL(value, baseUrl).href;
    } catch {
        return value;
    }
}

export default function ScrapePage() {
    const [url, setUrl] = useState('https://example.com');
    const [selectors, setSelectors] = useState<SelectorField[]>([
        { id: '1', name: 'title', selector: 'h1' },
        { id: '2', name: 'description', selector: 'p' },
        { id: '3', name: 'price', selector: '.price, .product-price, [data-price]' },
        { id: '4', name: 'image', selector: 'img.product-image, .main-image img' },
    ]);
    const [enableHealing, setEnableHealing] = useState(true);
    const [extractAll, setExtractAll] = useState(false);
    const [result, setResult] = useState<ScrapeResponse | null>(null);

    const { data: health, isError: healthError, refetch } = useQuery({
        queryKey: ['health'],
        queryFn: getHealth,
        retry: 1,
    });

    const { data: settings } = useQuery({
        queryKey: ['settings'],
        queryFn: getSettings,
    });

    const scrapeMutation = useMutation({
        mutationFn: scrapeUrl,
        onSuccess: (data) => {
            setResult(data);
        },
    });

    const addSelector = () => {
        setSelectors([
            ...selectors,
            { id: Date.now().toString(), name: '', selector: '' },
        ]);
    };

    const removeSelector = (id: string) => {
        if (selectors.length > 1) {
            setSelectors(selectors.filter((s) => s.id !== id));
        }
    };

    const updateSelector = (id: string, field: 'name' | 'selector', value: string) => {
        setSelectors(
            selectors.map((s) => (s.id === id ? { ...s, [field]: value } : s))
        );
    };

    const handleScrape = () => {
        const selectorMap: Record<string, string> = {};
        selectors.forEach((s) => {
            if (s.name && s.selector) {
                selectorMap[s.name] = s.selector;
            }
        });

        const request: ScrapeRequest = {
            url,
            selectors: selectorMap,
            enable_healing: enableHealing,
            extract_all: extractAll,
            timeout: settings?.timeout || 15,
        };

        scrapeMutation.mutate(request);
    };

    if (healthError) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center py-20">
                    <WifiOff className="w-16 h-16 text-red-400 mb-4" />
                    <h2 className="text-xl font-bold text-gray-900 mb-2">Backend Not Connected</h2>
                    <p className="text-gray-500 mb-4">Start backend to use scraper</p>
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
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Configuration Panel */}
                <div className="space-y-6">
                    {/* URL Input */}
                    <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Target URL
                        </label>
                        <div className="relative">
                            <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                            <input
                                type="url"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                placeholder="https://example.com/page"
                                className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                    </div>

                    {/* Selectors */}
                    <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold text-gray-900">Selectors</h3>
                            <button onClick={addSelector} className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700">
                                <Plus className="w-4 h-4" />
                                Add Field
                            </button>
                        </div>
                        <div className="space-y-3">
                            {selectors.map((selector) => (
                                <div key={selector.id} className="flex gap-3">
                                    <input
                                        type="text"
                                        value={selector.name}
                                        onChange={(e) => updateSelector(selector.id, 'name', e.target.value)}
                                        placeholder="Field name"
                                        className="w-1/3 px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                    />
                                    <input
                                        type="text"
                                        value={selector.selector}
                                        onChange={(e) => updateSelector(selector.id, 'selector', e.target.value)}
                                        placeholder="CSS selector (e.g., .product-title)"
                                        className="flex-1 px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-mono"
                                    />
                                    <button
                                        onClick={() => removeSelector(selector.id)}
                                        className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                                        disabled={selectors.length === 1}
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Options */}
                    <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">Options</h3>
                        <label className="flex items-center gap-3 cursor-pointer">
                            <div className="relative">
                                <input
                                    type="checkbox"
                                    checked={enableHealing}
                                    onChange={(e) => setEnableHealing(e.target.checked)}
                                    className="sr-only"
                                />
                                <div className={`w-11 h-6 rounded-full transition-colors flex items-center px-1 ${enableHealing ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                    <div className={`w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${enableHealing ? 'translate-x-5' : 'translate-x-0'}`} />
                                </div>
                            </div>
                            <div>
                                <p className="font-medium text-gray-900">Enable Self-Healing</p>
                                <p className="text-sm text-gray-500">Automatically recover from selector failures</p>
                            </div>
                            <Sparkles className="w-5 h-5 text-purple-500 ml-auto" />
                        </label>

                        <div className="border-t border-gray-100 pt-4 mt-4">
                            <label className="flex items-center gap-3 cursor-pointer">
                                <div className="relative">
                                    <input
                                        type="checkbox"
                                        checked={extractAll}
                                        onChange={(e) => setExtractAll(e.target.checked)}
                                        className="sr-only"
                                    />
                                    <div className={`w-11 h-6 rounded-full transition-colors flex items-center px-1 ${extractAll ? 'bg-emerald-500' : 'bg-gray-200'}`}>
                                        <div className={`w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${extractAll ? 'translate-x-5' : 'translate-x-0'}`} />
                                    </div>
                                </div>
                                <div>
                                    <p className="font-medium text-gray-900">Extract All Matches</p>
                                    <p className="text-sm text-gray-500">Return all elements, not just the first</p>
                                </div>
                                <Target className="w-5 h-5 text-emerald-500 ml-auto" />
                            </label>
                        </div>
                    </div>

                    {/* Execute Button */}
                    <button
                        onClick={handleScrape}
                        disabled={!url || scrapeMutation.isPending || !health}
                        className="w-full flex items-center justify-center gap-2 px-6 py-4 bg-gradient-to-r from-blue-500 to-purple-600 text-white font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {scrapeMutation.isPending ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Scraping...
                            </>
                        ) : (
                            <>
                                <Play className="w-5 h-5" />
                                Start Scraping
                            </>
                        )}
                    </button>
                </div>

                {/* Results Panel */}
                <div className="space-y-6">
                    <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">Results</h3>

                        {!result && !scrapeMutation.isPending && (
                            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                                <Globe className="w-12 h-12 mb-4" />
                                <p>Configure and run a scrape to see results</p>
                            </div>
                        )}

                        {scrapeMutation.isPending && (
                            <div className="flex flex-col items-center justify-center py-12">
                                <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
                                <p className="text-gray-600">Fetching and analyzing page...</p>
                                <p className="text-sm text-gray-400 mt-2">Self-healing will activate if selectors fail</p>
                            </div>
                        )}

                        {result && (
                            <div className="space-y-4">
                                <div className={`p-4 rounded-lg ${result.status === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                                    <div className="flex items-center gap-2">
                                        {result.status === 'success' ? <CheckCircle className="w-5 h-5 text-green-600" /> : <XCircle className="w-5 h-5 text-red-600" />}
                                        <span className={`font-medium ${result.status === 'success' ? 'text-green-800' : 'text-red-800'}`}>
                                            {result.status === 'success' ? 'Scrape Successful' : 'Scrape Failed'}
                                        </span>
                                    </div>
                                    {result.error && (
                                        <p className="text-sm text-red-600 mt-1">{result.error}</p>
                                    )}
                                </div>

                                <div className="border border-gray-200 rounded-lg overflow-hidden">
                                    <table className="w-full">
                                        <thead className="bg-gray-50">
                                            <tr>
                                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Field</th>
                                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-200">
                                            {result.results.map((r) => {
                                                const isImg = r.field.toLowerCase().includes('image') || r.field.toLowerCase().includes('img') || r.field.toLowerCase().includes('photo') || r.field.toLowerCase().includes('logo') || r.field.toLowerCase().includes('thumbnail');
                                                const rawValue = r.value || '';
                                                // For extract_all, value may have "[N matches]\n" prefix followed by URLs
                                                const valueLines = rawValue.startsWith('[') && rawValue.includes('matches]')
                                                    ? rawValue.split('\n').slice(1).filter(Boolean)
                                                    : [rawValue];
                                                const shouldPreviewImages = isImg || valueLines.some((v: string) => isImageUrl(v));

                                                return (
                                                    <tr key={r.field}>
                                                        <td className="px-4 py-3 text-sm font-medium text-gray-900 align-top">{r.field}</td>
                                                        <td className="px-4 py-3 text-sm text-gray-600 max-w-md break-words whitespace-pre-wrap">
                                                            {shouldPreviewImages && valueLines.length > 0 ? (
                                                                <div className="space-y-3">
                                                                    {rawValue.startsWith('[') && rawValue.includes('matches]') && (
                                                                        <p className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md inline-block">
                                                                            {rawValue.split('\n')[0]}
                                                                        </p>
                                                                    )}
                                                                    <div className="flex flex-wrap gap-2">
                                                                        {valueLines.map((imgUrl: string, idx: number) => {
                                                                            const resolved = resolveUrl(imgUrl.trim(), url);
                                                                            return (
                                                                                <div key={idx} className="relative group">
                                                                                    <div className="w-20 h-20 rounded-lg border border-gray-200 overflow-hidden bg-gray-50 flex items-center justify-center">
                                                                                        <img
                                                                                            src={resolved}
                                                                                            alt={`${r.field} ${idx + 1}`}
                                                                                            className="w-full h-full object-cover"
                                                                                            onError={(e) => {
                                                                                                (e.target as HTMLImageElement).style.display = 'none';
                                                                                                (e.target as HTMLImageElement).parentElement!.querySelector('.img-fallback')?.classList.remove('hidden');
                                                                                            }}
                                                                                        />
                                                                                        <div className="img-fallback hidden flex flex-col items-center justify-center text-gray-400">
                                                                                            <ImageIcon className="w-5 h-5" />
                                                                                            <span className="text-[10px] mt-1">No preview</span>
                                                                                        </div>
                                                                                    </div>
                                                                                    <a
                                                                                        href={resolved}
                                                                                        target="_blank"
                                                                                        rel="noopener noreferrer"
                                                                                        className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                                                                                    >
                                                                                        <ExternalLink className="w-4 h-4 text-white" />
                                                                                    </a>
                                                                                </div>
                                                                            );
                                                                        })}
                                                                    </div>
                                                                    <p className="text-[11px] text-gray-400 font-mono truncate max-w-[300px]" title={rawValue}>
                                                                        {valueLines[0]?.trim()}{valueLines.length > 1 ? ` (+${valueLines.length - 1} more)` : ''}
                                                                    </p>
                                                                </div>
                                                            ) : (
                                                                <span>{r.value || '-'}</span>
                                                            )}
                                                        </td>
                                                        <td className="px-4 py-3 align-top">
                                                            {r.success ? (
                                                                <div className="flex items-center gap-1">
                                                                    <CheckCircle className="w-4 h-4 text-green-500" />
                                                                    {r.healed && (
                                                                        <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">Healed</span>
                                                                    )}
                                                                </div>
                                                            ) : (
                                                                <XCircle className="w-4 h-4 text-red-500" />
                                                            )}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>

                                {result.results.some((r) => r.healed) && (
                                    <div className="p-4 bg-purple-50 rounded-lg">
                                        <h4 className="font-medium text-purple-900 mb-2 flex items-center gap-2">
                                            <Sparkles className="w-4 h-4" />
                                            Healed Selectors
                                        </h4>
                                        <div className="space-y-3">
                                            {result.results.filter((r) => r.healed).map((r) => (
                                                <div key={r.field} className="flex items-center justify-between bg-white/50 p-2 rounded-lg">
                                                    <div className="flex items-center gap-2 text-sm text-purple-800">
                                                        <span className="font-medium text-xs uppercase tracking-wider text-purple-600 w-16">{r.field}</span>
                                                        <code className="bg-white px-2 py-1 rounded text-xs border border-purple-100 line-through text-gray-400">{r.selector}</code>
                                                        <ArrowRight className="w-4 h-4 text-purple-400" />
                                                        <code className="bg-white px-2 py-1 rounded text-xs border border-purple-200 font-semibold text-purple-700">{r.new_selector}</code>
                                                    </div>
                                                    <button
                                                        onClick={() => {
                                                            setSelectors(selectors.map(s =>
                                                                s.name === r.field ? { ...s, selector: r.new_selector! } : s
                                                            ));
                                                        }}
                                                        className="flex items-center gap-1 px-2 py-1 bg-purple-600 text-white text-xs rounded hover:bg-purple-700 transition-colors shadow-sm"
                                                    >
                                                        <CheckCircle className="w-3 h-3" />
                                                        Apply Fix
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Summary Card - appears after results */}
                    {result && (
                        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                            <div className="px-6 py-4 bg-gradient-to-r from-slate-800 to-slate-700">
                                <h3 className="text-white font-semibold flex items-center gap-2">
                                    <Activity className="w-4 h-4" />
                                    Job Summary
                                </h3>
                            </div>
                            <div className="p-6">
                                {/* Stat Grid */}
                                <div className="grid grid-cols-2 gap-4 mb-5">
                                    <div className="bg-gray-50 rounded-lg p-3">
                                        <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
                                            <Hash className="w-3 h-3" />
                                            Job ID
                                        </div>
                                        <p className="text-sm font-mono font-semibold text-gray-800 truncate">{result.job_id}</p>
                                    </div>
                                    <div className="bg-gray-50 rounded-lg p-3">
                                        <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
                                            <Clock className="w-3 h-3" />
                                            Execution Time
                                        </div>
                                        <p className="text-sm font-semibold text-gray-800">
                                            {result.execution_time_ms < 1000
                                                ? `${result.execution_time_ms.toFixed(0)}ms`
                                                : `${(result.execution_time_ms / 1000).toFixed(1)}s`}
                                        </p>
                                    </div>
                                    <div className="bg-gray-50 rounded-lg p-3">
                                        <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
                                            <Target className="w-3 h-3" />
                                            Fields Extracted
                                        </div>
                                        <p className="text-sm font-semibold text-gray-800">
                                            {result.results.filter(r => r.success).length}
                                            <span className="text-gray-400 font-normal"> / {result.results.length}</span>
                                        </p>
                                    </div>
                                    <div className="bg-gray-50 rounded-lg p-3">
                                        <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
                                            <TrendingUp className="w-3 h-3" />
                                            Success Rate
                                        </div>
                                        <p className="text-sm font-semibold text-gray-800">
                                            {result.results.length > 0
                                                ? `${((result.results.filter(r => r.success).length / result.results.length) * 100).toFixed(0)}%`
                                                : '0%'}
                                        </p>
                                    </div>
                                </div>

                                {/* Healing Summary */}
                                <div className={`rounded-lg p-4 ${result.healing_triggered ? 'bg-purple-50 border border-purple-100' : 'bg-gray-50 border border-gray-100'}`}>
                                    <div className="flex items-center gap-2 mb-3">
                                        <Shield className={`w-4 h-4 ${result.healing_triggered ? 'text-purple-600' : 'text-gray-400'}`} />
                                        <span className={`text-sm font-semibold ${result.healing_triggered ? 'text-purple-800' : 'text-gray-600'}`}>
                                            Self-Healing
                                        </span>
                                        {result.healing_triggered ? (
                                            <span className="px-2 py-0.5 bg-purple-200 text-purple-800 text-xs font-medium rounded-full">Active</span>
                                        ) : (
                                            <span className="px-2 py-0.5 bg-gray-200 text-gray-600 text-xs font-medium rounded-full">Not Needed</span>
                                        )}
                                    </div>
                                    {result.healing_triggered ? (
                                        <div className="space-y-2">
                                            <div className="flex justify-between text-xs">
                                                <span className="text-purple-600">Selectors Healed</span>
                                                <span className="font-semibold text-purple-800">{result.total_healed}</span>
                                            </div>
                                            {result.results.filter(r => r.healed).map((r) => (
                                                <div key={r.field} className="flex justify-between text-xs">
                                                    <span className="text-purple-600 flex items-center gap-1">
                                                        <Zap className="w-3 h-3" />
                                                        {r.field} — confidence
                                                    </span>
                                                    <span className="font-semibold text-purple-800">
                                                        {r.confidence != null ? `${(r.confidence * 100).toFixed(0)}%` : '-'}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="text-xs text-gray-500">All selectors matched successfully — no healing was needed.</p>
                                    )}
                                </div>

                                {/* URL */}
                                <div className="mt-4 pt-4 border-t border-gray-100">
                                    <div className="flex items-center gap-2 text-xs text-gray-400">
                                        <Globe className="w-3 h-3" />
                                        <span className="truncate">{result.url}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
