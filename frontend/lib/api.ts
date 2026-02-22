import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use((config) => {
  console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API Error]', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Types
export interface ScrapeRequest {
  url: string;
  selectors: Record<string, string>;
  wait_for_selector?: string;
  timeout?: number;
  enable_healing?: boolean;
  extract_all?: boolean;
  take_screenshot?: boolean;
}

export interface ScrapeResult {
  field: string;
  selector: string;
  value: string | null;
  success: boolean;
  healed: boolean;
  new_selector?: string;
  confidence?: number;
}

export interface ScrapeResponse {
  job_id: string;
  url: string;
  status: 'pending' | 'running' | 'success' | 'failed' | 'healing';
  results: ScrapeResult[];
  healing_triggered: boolean;
  total_healed: number;
  execution_time_ms: number;
  screenshot_path?: string;
  error?: string;
}

export interface HealRequest {
  url: string;
  selector: string;
  element_context?: Record<string, unknown>;
}

export interface HealResponse {
  success: boolean;
  original_selector: string;
  new_selector: string | null;
  confidence: number;
  strategy_used: string;
  candidates_analyzed: number;
  healing_time_ms: number;
  error?: string;
}

export interface LogEntry {
  id: number;
  timestamp: string;
  level: string;
  message: string;
  job_id?: string;
  selector?: string;
  metadata?: Record<string, unknown>;
}

export interface ModelStatus {
  model: {
    model_type: string;
    is_trained: boolean;
    accuracy?: number;
    precision?: number;
    recall?: number;
    f1_score?: number;
    training_samples?: number;
    last_trained?: string;
    feature_importance?: Record<string, number>;
  };
  healing_stats: {
    total_attempts: number;
    success_rate: number;
    avg_confidence: number;
    avg_healing_time_ms: number;
    successful_healings: number;
    failed_healings: number;
  };
  xpath_stats: Record<string, unknown>;
}

export interface SelectorHistoryEntry {
  id: number;
  url: string;
  original_selector: string;
  new_selector?: string;
  confidence?: number;
  strategy?: string;
  status: string;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  database_connected: boolean;
  model_loaded: boolean;
}

// API Functions
export const scrapeUrl = async (request: ScrapeRequest): Promise<ScrapeResponse> => {
  const response = await api.post<ScrapeResponse>('/scrape', request);
  return response.data;
};

export const healSelector = async (request: HealRequest): Promise<HealResponse> => {
  const response = await api.post<HealResponse>('/heal', request);
  return response.data;
};

export const getLogs = async (page = 1, pageSize = 50): Promise<{ logs: LogEntry[]; total_count: number }> => {
  const response = await api.get('/logs', { params: { page, page_size: pageSize } });
  return response.data;
};

export const getModelStatus = async (): Promise<ModelStatus> => {
  const response = await api.get<ModelStatus>('/models/status');
  return response.data;
};

export const getSelectorHistory = async (url?: string, limit = 50): Promise<{ history: SelectorHistoryEntry[]; patterns: Record<string, unknown> }> => {
  const response = await api.get('/selectors/history', { params: { url, limit } });
  return response.data;
};

export const getHealth = async (): Promise<HealthStatus> => {
  const response = await api.get<HealthStatus>('/health');
  return response.data;
};

export const getHealingTrend = async (days = 7): Promise<{ trend: { date: string; name: string; success: number; failed: number }[] }> => {
  const response = await api.get('/stats/trend', { params: { days } });
  return response.data;
};

export interface Settings {
  api_url: string;
  timeout: number;
  headless: boolean;
  confidence_threshold: number;
  max_candidates: number;
  retention_days: number;
  auto_retrain: boolean;
  updated_at?: string;
}

export const getSettings = async (): Promise<Settings> => {
  const response = await api.get<Settings>('/settings');
  return response.data;
};

export const saveSettings = async (settings: Settings): Promise<Settings> => {
  const response = await api.post<Settings>('/settings', settings);
  return response.data;
};

export const updateSettings = async (settings: Partial<Settings>): Promise<Settings> => {
  const response = await api.put<Settings>('/settings', settings);
  return response.data;
};


// ============ PRODUCT SCRAPER ============

export interface ProductScrapeRequest {
  url: string;
  container_xpath: string;
  max_products?: number;
  pagination_type?: 'scroll' | 'next_button' | 'none';
  next_button_xpath?: string;
  enable_healing?: boolean;
  timeout?: number;
  tracking_id?: string;
}

export interface ProductItem {
  title?: string;
  price?: string;
  original_price?: string;
  discount?: string;
  image_url?: string;
  product_url?: string;
  description?: string;
  rating?: string;
  extra?: Record<string, string>;
}

export interface ProductScrapeResponse {
  session_id: string;
  url: string;
  domain: string;
  status: string;
  products: ProductItem[];
  total_found: number;
  total_extracted: number;
  execution_time_ms: number;
  error?: string;
  healed?: boolean;
  healed_xpath?: string;
  healing_confidence?: number;
}

export interface ScrapeSession {
  id: string;
  domain: string;
  url: string;
  session_name: string;
  product_count: number;
  created_at: string;
}

export const scrapeProducts = async (request: ProductScrapeRequest): Promise<ProductScrapeResponse> => {
  const response = await api.post<ProductScrapeResponse>('/product-scrape', request);
  return response.data;
};

export const getScrapeSessions = async (): Promise<{ sessions: ScrapeSession[] }> => {
  const response = await api.get('/scrape-sessions');
  return response.data;
};

export const getSessionById = async (id: string): Promise<any> => {
  const response = await api.get(`/scrape-sessions/${id}`);
  return response.data;
};

export interface XpathValidation {
  valid: boolean;
  match_count: number;
  previews: Array<{
    tag: string;
    text: string;
    attributes: Record<string, string>;
  }>;
  xpath: string;
  error?: string;
}

export const validateXpath = async (url: string, xpath: string): Promise<XpathValidation> => {
  const response = await api.post<XpathValidation>('/validate-xpath', { url, xpath });
  return response.data;
};

export default api;
