'use client';

import { useState, useRef, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
    ShoppingBag, Search, Loader2, Package, Star, ExternalLink,
    Clock, Hash, ChevronDown, Image as ImageIcon, Tag, Grid3X3,
    AlertCircle, CheckCircle2, Sparkles, ScrollText, MousePointerClick,
    Zap, Shield, ScanSearch, Globe, ScanLine, Layers, Download, Timer
} from 'lucide-react';
import {
    scrapeProducts,
    getScrapeSessions,
    getSessionById,
    validateXpath,
    ProductScrapeRequest,
    ProductScrapeResponse,
    ProductItem,
    ScrapeSession,
    XpathValidation,
} from '@/lib/api';

const SCRAPE_STEPS = [
    { key: 'initializing', label: 'Initializing scraper', icon: Zap, duration: 3 },
    { key: 'navigating', label: 'Loading page', icon: Globe, duration: 15 },
    { key: 'searching', label: 'Searching for product containers', icon: ScanSearch, duration: 8 },
    { key: 'scrolling', label: 'Scrolling to load more products', icon: ScrollText, duration: 10 },
    { key: 'drill_down', label: 'Analyzing container structure', icon: Layers, duration: 5 },
    { key: 'extracting', label: 'Extracting product data', icon: Download, duration: 20 },
    { key: 'done', label: 'Completed', icon: CheckCircle2, duration: 0 },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const STEP_MAP: Record<string, number> = {
    initializing: 0, navigating: 1, searching: 2, found: 2,
    paginating: 3, scrolling: 3, counting: 4, drill_down: 4,
    extracting: 5, done: 6, error: 6,
};

export default function ProductsPage() {
    // --- Config State ---
    const [url, setUrl] = useState('');
    const [containerXpath, setContainerXpath] = useState('');
    const [maxProducts, setMaxProducts] = useState(20);
    const [paginationType, setPaginationType] = useState<'scroll' | 'next_button' | 'none'>('scroll');
    const [nextButtonXpath, setNextButtonXpath] = useState('');
    const [timeout, setTimeout_] = useState(30);
    const [enableHealing, setEnableHealing] = useState(true);

    // --- Result State ---
    const [result, setResult] = useState<ProductScrapeResponse | null>(null);
    const [selectedSession, setSelectedSession] = useState<any>(null);
    const [validation, setValidation] = useState<XpathValidation | null>(null);

    // --- Progress State ---
    const [currentStep, setCurrentStep] = useState(0);
    const [currentStepLabel, setCurrentStepLabel] = useState('');
    const [elapsed, setElapsed] = useState(0);
    const [streamedProducts, setStreamedProducts] = useState<ProductItem[]>([]);
    const [progressPct, setProgressPct] = useState(0);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const sseRef = useRef<EventSource | null>(null);

    // --- Sessions History ---
    const { data: sessionsData, refetch: refetchSessions } = useQuery({
        queryKey: ['scrape-sessions'],
        queryFn: getScrapeSessions,
    });

    // --- Abort Controller ---
    const abortRef = useRef<AbortController | null>(null);

    const scrapeMutation = useMutation({
        mutationFn: scrapeProducts,
        onSuccess: (data) => {
            setResult(data);
            setSelectedSession(null);
            refetchSessions();
            stopSSE();
            setCurrentStep(SCRAPE_STEPS.length - 1);
        },
        onError: () => {
            stopSSE();
        },
    });

    const startSSE = (trackingId: string) => {
        setCurrentStep(0);
        setCurrentStepLabel('Initializing scraper');
        setElapsed(0);
        setStreamedProducts([]);
        setProgressPct(0);

        // Elapsed timer
        timerRef.current = setInterval(() => {
            setElapsed(prev => prev + 1);
        }, 1000);

        // SSE connection
        const es = new EventSource(`${API_BASE}/product-scrape/progress/${trackingId}`);
        sseRef.current = es;

        es.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const stepKey = data.step || '';
                const stepIdx = STEP_MAP[stepKey] ?? currentStep;
                setCurrentStep(stepIdx);
                setCurrentStepLabel(data.detail || stepKey);
                if (data.progress) setProgressPct(data.progress);

                // Stream products if available
                if (data.products && Array.isArray(data.products)) {
                    setStreamedProducts(data.products as ProductItem[]);
                }

                if (stepKey === 'done' || stepKey === 'error') {
                    es.close();
                }
            } catch (e) {
                console.warn('SSE parse error:', e);
            }
        };

        es.onerror = () => {
            // SSE connection errors are normal when scrape finishes
            es.close();
        };
    };

    const stopSSE = () => {
        if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
        if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    };

    useEffect(() => {
        return () => { stopSSE(); };
    }, []);

    const handleScrape = () => {
        if (!url || !containerXpath) return;
        abortRef.current?.abort();
        abortRef.current = new AbortController();

        const trackingId = `ps_${Math.random().toString(36).slice(2, 14)}`;

        const request: ProductScrapeRequest = {
            url,
            container_xpath: containerXpath,
            max_products: maxProducts,
            pagination_type: paginationType,
            next_button_xpath: paginationType === 'next_button' ? nextButtonXpath : undefined,
            enable_healing: enableHealing,
            timeout: timeout,
            tracking_id: trackingId,
        };
        setResult(null);
        startSSE(trackingId);
        scrapeMutation.mutate(request);
    };

    const handleCancelScrape = () => {
        abortRef.current?.abort();
        scrapeMutation.reset();
        stopSSE();
    };

    const validateMutation = useMutation({
        mutationFn: () => validateXpath(url, containerXpath),
        onSuccess: (data) => setValidation(data),
    });

    const handleValidate = () => {
        if (!url || !containerXpath) return;
        setValidation(null);
        validateMutation.mutate();
    };

    const loadSession = async (session: ScrapeSession) => {
        try {
            const data = await getSessionById(session.id);
            setSelectedSession(data);
            setResult(null);
        } catch (e) {
            console.error('Failed to load session', e);
        }
    };

    const isLoading = scrapeMutation.isPending;
    const displayProducts: ProductItem[] = result?.products || selectedSession?.products || (isLoading ? streamedProducts : []);

    const productCounts = [10, 20, 40, 60, 80, 100];

    const formatElapsed = (s: number) => {
        const min = Math.floor(s / 60);
        const sec = s % 60;
        return min > 0 ? `${min}m ${sec}s` : `${sec}s`;
    };

    return (
        <div className="p-6 max-w-[1600px] mx-auto">
            {/* Header */}
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 bg-gradient-to-br from-pink-500 to-rose-600 rounded-xl flex items-center justify-center">
                        <ShoppingBag className="w-5 h-5 text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">Product Scraper</h1>
                        <p className="text-sm text-gray-500">Auto-extract products with images, prices &amp; details</p>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-12 gap-6">
                {/* Left: Config Panel + Session History */}
                <div className="col-span-3 space-y-4">
                    {/* Config Panel */}
                    <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm space-y-4">
                        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                            <Search className="w-4 h-4 text-pink-500" />
                            Scrape Config
                        </h3>

                        {/* URL */}
                        <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">Target URL</label>
                            <input
                                type="url"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                placeholder="https://www.nykaa.com/skin/moisturizers/..."
                                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-pink-500/20 focus:border-pink-400"
                            />
                        </div>

                        {/* Container XPath */}
                        <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">
                                Product Container XPath
                            </label>
                            <div className="flex gap-1.5">
                                <input
                                    type="text"
                                    value={containerXpath}
                                    onChange={(e) => { setContainerXpath(e.target.value); setValidation(null); }}
                                    placeholder='//div[@class="productWrapper"]'
                                    className="flex-1 px-3 py-2.5 text-sm border border-gray-200 rounded-lg font-mono focus:outline-none focus:ring-2 focus:ring-pink-500/20 focus:border-pink-400"
                                />
                                <button
                                    onClick={handleValidate}
                                    disabled={!url || !containerXpath || validateMutation.isPending}
                                    className="px-3 py-2 bg-indigo-500 text-white text-xs font-medium rounded-lg hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1 whitespace-nowrap transition-colors"
                                    title="Validate XPath against the target URL"
                                >
                                    {validateMutation.isPending ? (
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    ) : (
                                        <ScanSearch className="w-3.5 h-3.5" />
                                    )}
                                    Test
                                </button>
                            </div>
                            <p className="text-xs text-gray-400 mt-1">XPath to each product card. Fields auto-detected.</p>

                            {/* Validation Result */}
                            {validation && (
                                <div className={`mt-2 p-2.5 rounded-lg border text-xs ${validation.valid
                                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                                    : 'bg-red-50 border-red-200 text-red-700'
                                    }`}>
                                    <div className="flex items-center gap-1.5 font-medium">
                                        {validation.valid ? (
                                            <><CheckCircle2 className="w-3.5 h-3.5" /> {validation.match_count} element{validation.match_count !== 1 ? 's' : ''} found</>
                                        ) : (
                                            <><AlertCircle className="w-3.5 h-3.5" /> No matches{validation.error ? `: ${validation.error}` : ''}</>
                                        )}
                                    </div>
                                    {validation.previews?.length > 0 && (
                                        <div className="mt-1.5 space-y-1">
                                            {validation.previews.slice(0, 3).map((p, i) => (
                                                <div key={i} className="bg-white/60 rounded px-2 py-1 font-mono text-[10px]">
                                                    &lt;{p.tag}{p.attributes?.class ? ` class="${p.attributes.class.substring(0, 50)}"` : ''}&gt;
                                                    {p.text && <span className="text-gray-500 ml-1">{p.text.substring(0, 60)}{p.text.length > 60 ? '…' : ''}</span>}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Product Count */}
                        <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">
                                Max Products
                            </label>
                            <div className="flex flex-wrap gap-1.5">
                                {productCounts.map((count) => (
                                    <button
                                        key={count}
                                        onClick={() => setMaxProducts(count)}
                                        className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-all ${maxProducts === count
                                            ? 'bg-pink-500 text-white shadow-sm'
                                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                            }`}
                                    >
                                        {count}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Pagination Type */}
                        <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">
                                Pagination
                            </label>
                            <div className="flex gap-1.5">
                                {[
                                    { value: 'scroll' as const, label: 'Scroll', icon: ScrollText },
                                    { value: 'next_button' as const, label: 'Button', icon: MousePointerClick },
                                    { value: 'none' as const, label: 'None', icon: Grid3X3 },
                                ].map(({ value, label, icon: Icon }) => (
                                    <button
                                        key={value}
                                        onClick={() => setPaginationType(value)}
                                        className={`flex-1 flex items-center justify-center gap-1 px-2 py-2 text-xs rounded-lg font-medium transition-all ${paginationType === value
                                            ? 'bg-pink-500 text-white shadow-sm'
                                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                            }`}
                                    >
                                        <Icon className="w-3.5 h-3.5" />
                                        {label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Next Button XPath (conditional) */}
                        {paginationType === 'next_button' && (
                            <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">
                                    Next Button XPath
                                </label>
                                <input
                                    type="text"
                                    value={nextButtonXpath}
                                    onChange={(e) => setNextButtonXpath(e.target.value)}
                                    placeholder='//a[@class="next-page"]'
                                    className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg font-mono focus:outline-none focus:ring-2 focus:ring-pink-500/20 focus:border-pink-400"
                                />
                            </div>
                        )}

                        {/* Timeout */}
                        <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">
                                Timeout: {timeout}s
                            </label>
                            <input
                                type="range"
                                min={10}
                                max={120}
                                value={timeout}
                                onChange={(e) => setTimeout_(parseInt(e.target.value))}
                                className="w-full accent-pink-500"
                            />
                        </div>

                        {/* Self-Healing Toggle */}
                        <div className="flex items-center justify-between py-2 px-1">
                            <div className="flex items-center gap-2">
                                <Shield className="w-4 h-4 text-emerald-500" />
                                <span className="text-xs font-medium text-gray-700">Self-Healing</span>
                            </div>
                            <button
                                onClick={() => setEnableHealing(!enableHealing)}
                                className={`relative w-10 h-5 rounded-full transition-colors ${enableHealing ? 'bg-emerald-500' : 'bg-gray-300'
                                    }`}
                            >
                                <div className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${enableHealing ? 'translate-x-5' : ''
                                    }`} />
                            </button>
                        </div>

                        {/* Scrape Button */}
                        <button
                            onClick={handleScrape}
                            disabled={!url || !containerXpath || isLoading}
                            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-pink-500 to-rose-600 text-white font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Scraping Products...
                                </>
                            ) : (
                                <>
                                    <ShoppingBag className="w-4 h-4" />
                                    Scrape Products
                                </>
                            )}
                        </button>
                        {isLoading && (
                            <button
                                onClick={handleCancelScrape}
                                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-200 transition-colors mt-2"
                            >
                                Cancel
                            </button>
                        )}
                    </div>

                    {/* Session History */}
                    <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
                        <h3 className="font-semibold text-gray-900 flex items-center gap-2 mb-3">
                            <Clock className="w-4 h-4 text-gray-400" />
                            Scrape History
                        </h3>
                        <div className="space-y-1.5 max-h-[400px] overflow-y-auto">
                            {sessionsData?.sessions?.length ? (
                                sessionsData.sessions.map((session: ScrapeSession) => (
                                    <button
                                        key={session.id}
                                        onClick={() => loadSession(session)}
                                        className={`w-full text-left px-3 py-2.5 rounded-lg transition-all hover:bg-gray-50 ${selectedSession?.id === session.id
                                            ? 'bg-pink-50 border border-pink-200'
                                            : 'border border-transparent'
                                            }`}
                                    >
                                        <div className="flex items-center gap-2">
                                            <div className="w-6 h-6 bg-gradient-to-br from-pink-400 to-rose-500 rounded-md flex items-center justify-center flex-shrink-0">
                                                <Package className="w-3 h-3 text-white" />
                                            </div>
                                            <div className="min-w-0">
                                                <p className="text-xs font-medium text-gray-900 truncate">
                                                    {session.domain}
                                                </p>
                                                <p className="text-[10px] text-gray-400">
                                                    {session.product_count} products · {new Date(session.created_at).toLocaleDateString()}
                                                </p>
                                            </div>
                                        </div>
                                    </button>
                                ))
                            ) : (
                                <p className="text-xs text-gray-400 text-center py-4">No scrape history yet</p>
                            )}
                        </div>
                    </div>
                </div>

                {/* Right: Results Grid */}
                <div className="col-span-9">
                    {/* Summary Bar */}
                    {(result || selectedSession) && (
                        <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm mb-4">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="flex items-center gap-2">
                                        <div className={`w-2 h-2 rounded-full ${(result?.status === 'healed') ? 'bg-emerald-400' :
                                            (result?.status || selectedSession?.status) === 'success' ? 'bg-green-400' : 'bg-red-400'
                                            }`} />
                                        <span className="text-sm font-medium text-gray-900">
                                            {result?.domain || selectedSession?.domain}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-1 text-xs text-gray-500">
                                        <Package className="w-3.5 h-3.5" />
                                        {displayProducts.length} products extracted
                                    </div>
                                    {(result?.total_found || selectedSession?.total_found) && (
                                        <div className="flex items-center gap-1 text-xs text-gray-500">
                                            <Hash className="w-3.5 h-3.5" />
                                            {result?.total_found || selectedSession?.total_found} found on page
                                        </div>
                                    )}
                                    <div className="flex items-center gap-1 text-xs text-gray-500">
                                        <Clock className="w-3.5 h-3.5" />
                                        {((result?.execution_time_ms || selectedSession?.execution_time_ms || 0) / 1000).toFixed(1)}s
                                    </div>
                                </div>
                                {result?.error && (
                                    <div className="flex items-center gap-1 text-xs text-red-500">
                                        <AlertCircle className="w-3.5 h-3.5" />
                                        {result.error}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Healing Success Banner */}
                    {result?.healed && (
                        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-4 flex items-start gap-3">
                            <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                                <Zap className="w-4 h-4 text-emerald-600" />
                            </div>
                            <div>
                                <h4 className="text-sm font-semibold text-emerald-800">Self-Healing Activated</h4>
                                <p className="text-xs text-emerald-700 mt-0.5">
                                    Original XPath was broken. The AI engine found a working alternative
                                    {result.healing_confidence != null && (
                                        <> with <strong>{(result.healing_confidence * 100).toFixed(0)}% confidence</strong></>
                                    )}.
                                </p>
                                {result.healed_xpath && (
                                    <code className="text-[10px] bg-emerald-100 px-2 py-0.5 rounded mt-1 inline-block text-emerald-800 font-mono">
                                        {result.healed_xpath}
                                    </code>
                                )}
                            </div>
                        </div>
                    )}

                    {/* ===== PROGRESS TRACKER (replaces skeleton) ===== */}
                    {isLoading && (
                        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-8 mb-4">
                            {/* Header */}
                            <div className="flex items-center justify-between mb-6">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-gradient-to-br from-pink-500 to-rose-600 rounded-xl flex items-center justify-center">
                                        <Loader2 className="w-5 h-5 text-white animate-spin" />
                                    </div>
                                    <div>
                                        <h3 className="text-base font-semibold text-gray-900">Scraping in Progress</h3>
                                        <p className="text-xs text-gray-500">
                                            This may take 30–60 seconds depending on the page complexity
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 bg-gray-50 px-3 py-1.5 rounded-lg">
                                    <Timer className="w-4 h-4 text-gray-400" />
                                    <span className="font-mono text-sm font-medium text-gray-700">
                                        {formatElapsed(elapsed)}
                                    </span>
                                </div>
                            </div>

                            {/* Progress Bar */}
                            <div className="w-full bg-gray-100 rounded-full h-2 mb-6 overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-pink-500 to-rose-500 rounded-full transition-all duration-1000 ease-out"
                                    style={{
                                        width: `${progressPct || Math.min(
                                            ((currentStep + 1) / SCRAPE_STEPS.length) * 100,
                                            95
                                        )}%`
                                    }}
                                />
                            </div>

                            {/* Steps */}
                            <div className="space-y-2">
                                {SCRAPE_STEPS.slice(0, -1).map((step, idx) => {
                                    const StepIcon = step.icon;
                                    const isActive = idx === currentStep;
                                    const isDone = idx < currentStep;
                                    const isPending = idx > currentStep;

                                    return (
                                        <div
                                            key={step.key}
                                            className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-300 ${isActive
                                                ? 'bg-pink-50 border border-pink-200'
                                                : isDone
                                                    ? 'bg-gray-50 border border-transparent'
                                                    : 'border border-transparent opacity-40'
                                                }`}
                                        >
                                            <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${isActive
                                                ? 'bg-pink-500'
                                                : isDone
                                                    ? 'bg-emerald-500'
                                                    : 'bg-gray-200'
                                                }`}>
                                                {isDone ? (
                                                    <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                                                ) : isActive ? (
                                                    <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
                                                ) : (
                                                    <StepIcon className="w-3.5 h-3.5 text-gray-400" />
                                                )}
                                            </div>
                                            <span className={`text-sm font-medium ${isActive
                                                ? 'text-pink-700'
                                                : isDone
                                                    ? 'text-gray-500'
                                                    : 'text-gray-400'
                                                }`}>
                                                {step.label}
                                                {isActive && currentStepLabel && (
                                                    <span className="text-xs font-normal ml-2 text-gray-400">
                                                        — {currentStepLabel}
                                                    </span>
                                                )}
                                                {isActive && (
                                                    <span className="inline-flex ml-1">
                                                        <span className="animate-pulse">.</span>
                                                        <span className="animate-pulse" style={{ animationDelay: '0.2s' }}>.</span>
                                                        <span className="animate-pulse" style={{ animationDelay: '0.4s' }}>.</span>
                                                    </span>
                                                )}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Warning */}
                            <div className="mt-5 flex items-center gap-2 text-xs text-amber-600 bg-amber-50 px-4 py-2.5 rounded-lg border border-amber-100">
                                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                                <span>
                                    Complex pages (like Nykaa, Amazon) with lazy-loading and heavy JS may take longer.
                                    The scraper scrolls, waits, and analyzes the DOM to find all products.
                                </span>
                            </div>
                        </div>
                    )}

                    {/* Product Grid — shows during loading (streamed) and after result */}
                    {displayProducts.length > 0 && (
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                            {displayProducts.map((product, idx) => (
                                <div
                                    key={idx}
                                    className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden hover:shadow-md transition-shadow group"
                                    style={{ animationDelay: `${idx * 50}ms` }}
                                >
                                    {/* Product Image */}
                                    <div className="relative h-52 bg-gray-50 flex items-center justify-center overflow-hidden">
                                        {product.image_url ? (
                                            <img
                                                src={product.image_url}
                                                alt={product.title || 'Product'}
                                                className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-300"
                                                onError={(e) => {
                                                    (e.target as HTMLImageElement).style.display = 'none';
                                                    (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                                                }}
                                            />
                                        ) : null}
                                        <div className={`flex flex-col items-center gap-1 text-gray-300 ${product.image_url ? 'hidden' : ''}`}>
                                            <ImageIcon className="w-10 h-10" />
                                            <span className="text-xs">No Image</span>
                                        </div>
                                        {product.discount && (
                                            <span className="absolute top-2 right-2 bg-red-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                                                {product.discount}
                                            </span>
                                        )}
                                    </div>

                                    {/* Product Info */}
                                    <div className="p-3 space-y-1.5">
                                        {product.title && (
                                            <h4 className="text-sm font-medium text-gray-900 line-clamp-2 leading-snug">
                                                {product.product_url ? (
                                                    <a
                                                        href={product.product_url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="hover:text-pink-600 transition-colors"
                                                    >
                                                        {product.title}
                                                    </a>
                                                ) : (
                                                    product.title
                                                )}
                                            </h4>
                                        )}

                                        {product.description && (
                                            <p className="text-xs text-gray-500 line-clamp-1">{product.description}</p>
                                        )}

                                        <div className="flex items-center gap-2 pt-0.5">
                                            {product.price && (
                                                <span className="text-sm font-bold text-gray-900">{product.price}</span>
                                            )}
                                            {product.original_price && product.original_price !== product.price && (
                                                <span className="text-xs text-gray-400 line-through">{product.original_price}</span>
                                            )}
                                        </div>

                                        {product.rating && (
                                            <div className="flex items-center gap-1">
                                                <Star className="w-3 h-3 text-yellow-400 fill-yellow-400" />
                                                <span className="text-xs text-gray-600">{product.rating}</span>
                                            </div>
                                        )}

                                        {product.product_url && (
                                            <a
                                                href={product.product_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-1 text-[11px] text-pink-500 hover:text-pink-700 transition-colors mt-1"
                                            >
                                                <ExternalLink className="w-3 h-3" />
                                                View Product
                                            </a>
                                        )}
                                    </div>
                                </div>
                            ))}

                            {/* Skeleton placeholders for remaining products during loading */}
                            {isLoading && streamedProducts.length > 0 && streamedProducts.length < maxProducts && (
                                Array.from({ length: Math.min(maxProducts - streamedProducts.length, 8) }).map((_, idx) => (
                                    <div
                                        key={`skeleton-${idx}`}
                                        className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden animate-pulse"
                                    >
                                        <div className="h-52 bg-gray-100 relative">
                                            <div className="absolute inset-0 bg-gradient-to-r from-gray-100 via-gray-50 to-gray-100 animate-pulse" />
                                        </div>
                                        <div className="p-3 space-y-2">
                                            <div className="h-3.5 bg-gray-100 rounded w-4/5" />
                                            <div className="h-3 bg-gray-100 rounded w-3/5" />
                                            <div className="h-4 bg-gray-100 rounded w-1/3 mt-1" />
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}

                    {/* Empty State */}
                    {!isLoading && !displayProducts.length && !result && !selectedSession && (
                        <div className="bg-white rounded-xl border border-gray-100 shadow-sm flex flex-col items-center justify-center py-24">
                            <div className="w-20 h-20 bg-gradient-to-br from-pink-100 to-rose-100 rounded-2xl flex items-center justify-center mb-4">
                                <ShoppingBag className="w-10 h-10 text-pink-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-1">No Products Yet</h3>
                            <p className="text-sm text-gray-500 max-w-sm text-center">
                                Enter a product listing URL and the container XPath to auto-extract products with images, prices, and details.
                            </p>
                        </div>
                    )}

                    {/* Error State */}
                    {!isLoading && result?.status === 'failed' && (
                        <div className="bg-red-50 border border-red-200 rounded-xl p-6 mt-4">
                            <div className="flex items-center gap-2 mb-2">
                                <AlertCircle className="w-5 h-5 text-red-500" />
                                <span className="font-medium text-red-700">Scrape Failed</span>
                            </div>
                            <p className="text-sm text-red-600">{result.error}</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
