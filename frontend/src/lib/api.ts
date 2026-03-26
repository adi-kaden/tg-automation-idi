import type { Token, ApiError } from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

// Token storage
const TOKEN_KEY = 'tg_content_engine_token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
}

// API Error class
export class ApiRequestError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiRequestError';
    this.status = status;
    this.detail = detail;
  }
}

// Fetch wrapper with auth
async function fetchWithAuth<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle non-OK responses
  if (!response.ok) {
    let errorDetail = 'An error occurred';

    try {
      const errorData: ApiError = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      errorDetail = response.statusText;
    }

    // Handle 401 - clear token and redirect
    if (response.status === 401) {
      clearToken();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }

    throw new ApiRequestError(response.status, errorDetail);
  }

  // Handle empty responses
  const text = await response.text();
  if (!text) {
    return {} as T;
  }

  return JSON.parse(text) as T;
}

// API methods
export const api = {
  // Auth
  auth: {
    login: async (email: string, password: string): Promise<Token> => {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        let errorDetail = 'Invalid credentials';
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch {
          errorDetail = response.statusText;
        }
        throw new ApiRequestError(response.status, errorDetail);
      }

      const data: Token = await response.json();
      setToken(data.access_token);
      return data;
    },

    logout: (): void => {
      clearToken();
    },

    refresh: async (): Promise<Token> => {
      const response = await fetchWithAuth<Token>('/auth/refresh', {
        method: 'POST',
      });
      setToken(response.access_token);
      return response;
    },

    me: async () => {
      return fetchWithAuth<Token['user']>('/auth/me');
    },
  },

  // Dashboard
  dashboard: {
    getStats: async () => {
      return fetchWithAuth<import('@/types').DashboardStats>('/dashboard/stats');
    },

    getToday: async () => {
      return fetchWithAuth<import('@/types').TodaySchedule>('/dashboard/today');
    },

    getPending: async () => {
      return fetchWithAuth<import('@/types').PendingAction[]>('/dashboard/pending');
    },
  },

  // Users
  users: {
    list: async (page = 1, perPage = 20) => {
      return fetchWithAuth<import('@/types').PaginatedResponse<import('@/types').User>>(
        `/users?page=${page}&per_page=${perPage}`
      );
    },

    get: async (id: string) => {
      return fetchWithAuth<import('@/types').User>(`/users/${id}`);
    },

    create: async (data: {
      email: string;
      password: string;
      name: string;
      role: string;
    }) => {
      return fetchWithAuth<import('@/types').User>('/users', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    update: async (id: string, data: Partial<{
      name: string;
      role: string;
      is_active: boolean;
      password: string;
    }>) => {
      return fetchWithAuth<import('@/types').User>(`/users/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
    },

    delete: async (id: string) => {
      return fetchWithAuth<import('@/types').MessageResponse>(`/users/${id}`, {
        method: 'DELETE',
      });
    },
  },

  // Content Slots
  contentSlots: {
    list: async (params?: { date_from?: string; date_to?: string; status?: string }) => {
      const queryParams = new URLSearchParams();
      if (params?.date_from) queryParams.set('date_from', params.date_from);
      if (params?.date_to) queryParams.set('date_to', params.date_to);
      if (params?.status) queryParams.set('status', params.status);
      const query = queryParams.toString();
      return fetchWithAuth<import('@/types').ContentSlot[]>(
        `/content/slots${query ? `?${query}` : ''}`
      );
    },

    getToday: async () => {
      return fetchWithAuth<import('@/types').ContentSlot[]>('/content/slots/today');
    },

    get: async (id: string) => {
      return fetchWithAuth<import('@/types').ContentSlot>(`/content/slots/${id}`);
    },

    select: async (id: string, optionId: string, edits?: {
      title_en?: string;
      body_en?: string;
      title_ru?: string;
      body_ru?: string;
    }) => {
      return fetchWithAuth<import('@/types').ContentSlot>(`/content/slots/${id}/select`, {
        method: 'POST',
        body: JSON.stringify({ option_id: optionId, edits }),
      });
    },

    skip: async (id: string) => {
      return fetchWithAuth<import('@/types').ContentSlot>(`/content/slots/${id}/skip`, {
        method: 'POST',
      });
    },

    regenerate: async (id: string) => {
      return fetchWithAuth<import('@/types').ContentSlot>(`/content/slots/${id}/generate`, {
        method: 'POST',
      });
    },

    update: async (id: string, data: { album_mode?: boolean }) => {
      return fetchWithAuth<import('@/types').ContentSlot>(`/content/slots/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
    },
  },

  // Content (additional endpoints)
  content: {
    getQueue: async (date?: string) => {
      const query = date ? `?target_date=${date}` : '';
      return fetchWithAuth<import('@/types').ContentQueueResponse>(`/content/queue${query}`);
    },

    publish: async (slotId: string) => {
      return fetchWithAuth<import('@/types').PublishResponse>(`/content/slots/${slotId}/publish`, {
        method: 'POST',
      });
    },

    autoSelect: async (slotId: string) => {
      return fetchWithAuth<{ slot_id: string; task_id: string; status: string }>(
        `/content/slots/${slotId}/auto-select`,
        { method: 'POST' }
      );
    },
  },

  // Post Options
  postOptions: {
    get: async (id: string) => {
      return fetchWithAuth<import('@/types').PostOption>(`/post-options/${id}`);
    },

    update: async (id: string, data: Partial<import('@/types').PostOption>) => {
      return fetchWithAuth<import('@/types').PostOption>(`/post-options/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
    },

    regenerateImage: async (id: string) => {
      return fetchWithAuth<import('@/types').PostOption>(
        `/post-options/${id}/regenerate-image`,
        { method: 'POST' }
      );
    },
  },

  // Scraper
  scraper: {
    getSources: async () => {
      const response = await fetchWithAuth<{ items: import('@/types').ScrapeSource[] }>('/scraper/sources');
      return response.items;
    },

    createSource: async (data: Partial<import('@/types').ScrapeSource>) => {
      return fetchWithAuth<import('@/types').ScrapeSource>('/scraper/sources', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    updateSource: async (id: string, data: Partial<import('@/types').ScrapeSource>) => {
      return fetchWithAuth<import('@/types').ScrapeSource>(`/scraper/sources/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
    },

    deleteSource: async (id: string) => {
      return fetchWithAuth<import('@/types').MessageResponse>(`/scraper/sources/${id}`, {
        method: 'DELETE',
      });
    },

    testSource: async (id: string) => {
      return fetchWithAuth<import('@/types').ScrapedArticle[]>(
        `/scraper/sources/${id}/test`,
        { method: 'POST' }
      );
    },

    getRuns: async (page = 1, perPage = 20) => {
      return fetchWithAuth<import('@/types').PaginatedResponse<import('@/types').ScrapeRun>>(
        `/scraper/runs?page=${page}&per_page=${perPage}`
      );
    },

    runNow: async () => {
      return fetchWithAuth<import('@/types').ScrapeRun>('/scraper/run-now', {
        method: 'POST',
      });
    },

    getArticles: async (params?: {
      page?: number;
      per_page?: number;
      category?: string;
      is_used?: boolean;
    }) => {
      const queryParams = new URLSearchParams();
      if (params?.page) queryParams.set('page', params.page.toString());
      if (params?.per_page) queryParams.set('per_page', params.per_page.toString());
      if (params?.category) queryParams.set('category', params.category);
      if (params?.is_used !== undefined) queryParams.set('is_used', params.is_used.toString());
      const query = queryParams.toString();
      return fetchWithAuth<import('@/types').PaginatedResponse<import('@/types').ScrapedArticle>>(
        `/scraper/articles${query ? `?${query}` : ''}`
      );
    },
  },

  // Published Posts
  publishedPosts: {
    list: async (params?: {
      page?: number;
      per_page?: number;
      content_type?: string;
      language?: string;
      date_from?: string;
      date_to?: string;
      sort_by?: string;
      sort_order?: string;
    }) => {
      const queryParams = new URLSearchParams();
      if (params?.page) queryParams.set('page', params.page.toString());
      if (params?.per_page) queryParams.set('per_page', params.per_page.toString());
      if (params?.content_type) queryParams.set('content_type', params.content_type);
      if (params?.language) queryParams.set('language', params.language);
      if (params?.date_from) queryParams.set('date_from', params.date_from);
      if (params?.date_to) queryParams.set('date_to', params.date_to);
      if (params?.sort_by) queryParams.set('sort_by', params.sort_by);
      if (params?.sort_order) queryParams.set('sort_order', params.sort_order);
      const query = queryParams.toString();
      return fetchWithAuth<import('@/types').PaginatedResponse<import('@/types').PublishedPostDetail>>(
        `/published-posts${query ? `?${query}` : ''}`
      );
    },

    get: async (id: string) => {
      return fetchWithAuth<import('@/types').PublishedPostDetail>(`/published-posts/${id}`);
    },
  },

  // Analytics
  analytics: {
    getSummary: async (days = 7) => {
      return fetchWithAuth<import('@/types').AnalyticsSummary>(
        `/dashboard/analytics/summary?days=${days}`
      );
    },

    getGrowth: async (days = 30) => {
      return fetchWithAuth<import('@/types').ChannelGrowth[]>(
        `/dashboard/analytics/growth?days=${days}`
      );
    },

    getTopPosts: async (limit = 10) => {
      return fetchWithAuth<import('@/types').TopPost[]>(
        `/dashboard/analytics/top-posts?limit=${limit}`
      );
    },

    triggerCollection: async (hoursBack = 48) => {
      return fetchWithAuth<{ status: string; task_id: string }>(
        `/dashboard/analytics/collect?hours_back=${hoursBack}`,
        { method: 'POST' }
      );
    },
  },

  // Telegram
  telegram: {
    testConnection: async () => {
      return fetchWithAuth<{ success: boolean; message: string }>('/content/telegram/test');
    },

    getChannelInfo: async () => {
      return fetchWithAuth<{ success: boolean; channel?: object; message?: string }>(
        '/content/telegram/channel-info'
      );
    },
  },

  // Notifications
  notifications: {
    testConnection: async () => {
      return fetchWithAuth<{ success: boolean; message: string }>('/content/notifications/test');
    },

    sendTest: async (type: 'options_ready' | 'auto_selected' | 'publish_success' | 'publish_failed') => {
      return fetchWithAuth<{ success: boolean; message_id?: number; error?: string }>(
        `/content/notifications/send-test?notification_type=${type}`,
        { method: 'POST' }
      );
    },
  },

  // Prompt Config
  prompts: {
    getGlobalConfig: async () => {
      return fetchWithAuth<import('@/types').PromptConfig>('/prompts/config');
    },

    updateGlobalConfig: async (data: import('@/types').PromptConfigUpdate) => {
      return fetchWithAuth<import('@/types').PromptConfig>('/prompts/config', {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },

    getSlotOverrides: async () => {
      return fetchWithAuth<import('@/types').SlotOverride[]>('/prompts/slots');
    },

    getSlotOverride: async (slotNumber: number) => {
      return fetchWithAuth<import('@/types').PromptConfig>(`/prompts/slots/${slotNumber}`);
    },

    setSlotOverride: async (slotNumber: number, data: import('@/types').PromptConfigUpdate) => {
      return fetchWithAuth<import('@/types').PromptConfig>(`/prompts/slots/${slotNumber}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },

    deleteSlotOverride: async (slotNumber: number) => {
      return fetchWithAuth<import('@/types').MessageResponse>(`/prompts/slots/${slotNumber}`, {
        method: 'DELETE',
      });
    },

    testGenerate: async (data: import('@/types').TestGenerateRequest) => {
      return fetchWithAuth<import('@/types').TestGenerateResponse>('/prompts/test-generate', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
  },

  // Settings
  settings: {
    list: async () => {
      return fetchWithAuth<import('@/types').Setting[]>('/settings');
    },

    update: async (settings: { key: string; value: string }[]) => {
      return fetchWithAuth<import('@/types').Setting[]>('/settings', {
        method: 'PATCH',
        body: JSON.stringify({ settings }),
      });
    },

    testConnection: async (service: 'claude' | 'gemini' | 'telegram') => {
      return fetchWithAuth<{ success: boolean; message: string }>(
        '/settings/test-connection',
        {
          method: 'POST',
          body: JSON.stringify({ service }),
        }
      );
    },
  },
};
