import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type {
  DashboardStats,
  TodaySchedule,
  PendingAction,
  ContentSlot,
  ScrapeSource,
  PublishedPost,
  ChannelSnapshot,
} from '@/types';

// Query Keys
export const queryKeys = {
  dashboard: {
    stats: ['dashboard', 'stats'] as const,
    today: ['dashboard', 'today'] as const,
    pending: ['dashboard', 'pending'] as const,
  },
  content: {
    slots: (params?: { date?: string; status?: string }) =>
      ['content', 'slots', params] as const,
    slot: (id: string) => ['content', 'slot', id] as const,
    queue: (date?: string) => ['content', 'queue', date] as const,
  },
  scraper: {
    sources: ['scraper', 'sources'] as const,
    runs: (page: number) => ['scraper', 'runs', page] as const,
    articles: (params?: object) => ['scraper', 'articles', params] as const,
  },
  analytics: {
    summary: (days: number) => ['analytics', 'summary', days] as const,
    growth: (days: number) => ['analytics', 'growth', days] as const,
    topPosts: (limit: number) => ['analytics', 'topPosts', limit] as const,
  },
  posts: {
    list: (params?: object) => ['posts', 'list', params] as const,
    detail: (id: string) => ['posts', 'detail', id] as const,
  },
  telegram: {
    test: ['telegram', 'test'] as const,
    channelInfo: ['telegram', 'channelInfo'] as const,
  },
};

// ==================== Dashboard Hooks ====================

export function useDashboardStats() {
  return useQuery({
    queryKey: queryKeys.dashboard.stats,
    queryFn: api.dashboard.getStats,
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useTodaySchedule() {
  return useQuery({
    queryKey: queryKeys.dashboard.today,
    queryFn: api.dashboard.getToday,
    refetchInterval: 30000,
  });
}

export function usePendingActions() {
  return useQuery({
    queryKey: queryKeys.dashboard.pending,
    queryFn: api.dashboard.getPending,
    refetchInterval: 30000,
  });
}

// ==================== Content Hooks ====================

export function useContentSlots(params?: { date_from?: string; date_to?: string; status?: string }) {
  return useQuery({
    queryKey: queryKeys.content.slots(params),
    queryFn: () => api.contentSlots.list(params),
  });
}

export function useContentSlot(id: string) {
  return useQuery({
    queryKey: queryKeys.content.slot(id),
    queryFn: () => api.contentSlots.get(id),
    enabled: !!id,
  });
}

export function useContentQueue(date?: string) {
  return useQuery({
    queryKey: queryKeys.content.queue(date),
    queryFn: () => api.content.getQueue(date),
    refetchInterval: 30000,
  });
}

export function useSelectOption() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ slotId, optionId }: { slotId: string; optionId: string }) =>
      api.contentSlots.select(slotId, optionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['content'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function usePublishSlot() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (slotId: string) => api.content.publish(slotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['content'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useUpdateOption() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      optionId,
      data,
    }: {
      optionId: string;
      data: {
        title_en?: string;
        body_en?: string;
        title_ru?: string;
        body_ru?: string;
        hashtags?: string[];
      };
    }) => api.postOptions.update(optionId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['content'] });
    },
  });
}

export function useRegenerateSlot() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (slotId: string) => api.contentSlots.regenerate(slotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['content'] });
    },
  });
}

// ==================== Scraper Hooks ====================

export function useScraperSources() {
  return useQuery({
    queryKey: queryKeys.scraper.sources,
    queryFn: api.scraper.getSources,
  });
}

export function useScraperRuns(page = 1) {
  return useQuery({
    queryKey: queryKeys.scraper.runs(page),
    queryFn: () => api.scraper.getRuns(page),
  });
}

export function useRunScraper() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.scraper.runNow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scraper'] });
    },
  });
}

export function useToggleSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      api.scraper.updateSource(id, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.scraper.sources });
    },
  });
}

export function useScraperArticles(params?: {
  page?: number;
  per_page?: number;
  category?: string;
  is_used?: boolean;
}) {
  return useQuery({
    queryKey: queryKeys.scraper.articles(params),
    queryFn: () => api.scraper.getArticles(params),
  });
}

// ==================== Analytics Hooks ====================

export function useAnalyticsSummary(days = 7) {
  return useQuery({
    queryKey: queryKeys.analytics.summary(days),
    queryFn: () => api.analytics.getSummary(days),
  });
}

export function useAnalyticsGrowth(days = 30) {
  return useQuery({
    queryKey: queryKeys.analytics.growth(days),
    queryFn: () => api.analytics.getGrowth(days),
  });
}

export function useTopPosts(limit = 10) {
  return useQuery({
    queryKey: queryKeys.analytics.topPosts(limit),
    queryFn: () => api.analytics.getTopPosts(limit),
  });
}

// ==================== Posts Hooks ====================

export function usePublishedPosts(params?: {
  page?: number;
  category?: string;
  language?: string;
}) {
  return useQuery({
    queryKey: queryKeys.posts.list(params),
    queryFn: () => api.publishedPosts.list(params),
  });
}

export function usePublishedPost(id: string) {
  return useQuery({
    queryKey: queryKeys.posts.detail(id),
    queryFn: () => api.publishedPosts.get(id),
    enabled: !!id,
  });
}

// ==================== Telegram Hooks ====================

export function useTelegramTest() {
  return useQuery({
    queryKey: queryKeys.telegram.test,
    queryFn: api.telegram.testConnection,
    enabled: false, // Only run when manually triggered
    retry: false,
  });
}

export function useTelegramChannelInfo() {
  return useQuery({
    queryKey: queryKeys.telegram.channelInfo,
    queryFn: api.telegram.getChannelInfo,
  });
}
