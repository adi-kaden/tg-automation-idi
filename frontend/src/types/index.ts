// User types
export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'smm' | 'viewer';
  telegram_user_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// Scrape Source types
export interface ScrapeSource {
  id: string;
  name: string;
  url: string;
  source_type: 'rss' | 'website' | 'api' | 'data_portal';
  category: ContentCategory;
  language: string;
  scrape_frequency_hours: number;
  css_selectors: string | null;
  is_active: boolean;
  last_scraped_at: string | null;
  last_error: string | null;
  reliability_score: number;
  created_at: string;
  updated_at: string;
}

// Scrape Run types
export interface ScrapeRun {
  id: string;
  source_id: string | null;
  run_type: 'scheduled' | 'manual' | 'retry';
  status: 'running' | 'completed' | 'failed' | 'partial';
  articles_found: number;
  articles_new: number;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

// Scraped Article types
export interface ScrapedArticle {
  id: string;
  source_id: string;
  url: string;
  title: string;
  summary: string | null;
  full_text: string | null;
  image_url: string | null;
  author: string | null;
  published_at: string | null;
  category: ContentCategory;
  relevance_score: number;
  engagement_potential: number;
  is_used: boolean;
  tags: string[] | null;
  scraped_at: string;
}

// Content Slot types
export interface ContentSlot {
  id: string;
  scheduled_date: string;
  scheduled_time: string;
  scheduled_at: string;
  slot_number: number;
  content_type: 'real_estate' | 'general_dubai';
  status: SlotStatus;
  approval_deadline: string;
  album_mode: boolean;
  selected_option_id: string | null;
  selected_by: 'human' | 'ai' | null;
  selected_by_user_id: string | null;
  published_post_id: string | null;
  options: PostOption[];
  created_at: string;
  updated_at: string;
}

export type SlotStatus = 'pending' | 'generating' | 'options_ready' | 'approved' | 'published' | 'failed' | 'skipped';

// Post Option types
export interface PostOption {
  id: string;
  slot_id: string;
  option_label: 'A' | 'B';
  title_en: string;
  body_en: string;
  title_ru: string;
  body_ru: string;
  hashtags: string[];
  image_prompt: string | null;
  image_url: string | null;
  image_data: string | null;  // Base64 encoded image
  image_style?: string;
  album_image_prompts: string | null;  // JSON array of image prompts
  album_images_data: string | null;  // JSON array of base64 images
  category: ContentCategory;
  ai_quality_score: number;
  content_type: string;
  is_selected: boolean;
  is_edited: boolean;
  created_at: string;
  updated_at: string;
}

// Published Post types
export interface PublishedPost {
  id: string;
  slot_id: string;
  option_id: string;
  posted_title: string;
  posted_body: string;
  posted_language: string;
  posted_image_url: string | null;
  telegram_message_id: number | null;
  telegram_channel_id: string | null;
  selected_by: 'human' | 'ai';
  selected_by_user_id: string | null;
  published_at: string;
  analytics?: PostAnalytics;
}

// Post Analytics types
export interface PostAnalytics {
  id: string;
  post_id: string;
  views: number;
  forwards: number;
  replies: number;
  reactions: Record<string, number> | null;
  engagement_rate: number;
  view_growth_1h: number | null;
  view_growth_24h: number | null;
  last_fetched_at: string;
}

// Published Post with computed fields from API
export interface PublishedPostDetail extends PublishedPost {
  content_type?: string;
  telegram_link?: string;
  image_url_served?: string;
}

// Channel Snapshot types
export interface ChannelSnapshot {
  id: string;
  snapshot_date: string;
  subscriber_count: number;
  subscriber_growth: number;
  posts_published: number;
  avg_views: number;
  avg_engagement_rate: number;
  top_post_id: string | null;
}

// Post Template types (legacy)
export interface PostTemplate {
  id: string;
  name: string;
  category: string;
  language: string;
  prompt_template: string;
  image_prompt_template: string | null;
  example_output: string | null;
  tone: string;
  max_length_chars: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Prompt Config types
export interface PromptConfig {
  id: string;
  scope: 'global' | 'slot_override';
  slot_number: number | null;
  system_prompt: string;
  generation_prompt: string;
  tone: string;
  voice_preset: string;
  max_length_chars: number;
  image_style_prompt: string;
  image_aspect_ratio: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PromptConfigUpdate {
  system_prompt?: string;
  generation_prompt?: string;
  tone?: string;
  voice_preset?: string;
  max_length_chars?: number;
  image_aspect_ratio?: string;
}

export interface SlotOverride {
  slot_number: number;
  has_override: boolean;
  config: PromptConfig | null;
}

export interface TestGenerateRequest {
  system_prompt: string;
  generation_prompt: string;
  tone: string;
  voice_preset?: string;
  max_length_chars: number;
  image_aspect_ratio: string;
  slot_number?: number;
}

export interface TestGenerateResponse {
  title_ru: string;
  body_ru: string;
  image_prompt: string;
  quality_score: number;
  image_base64: string | null;
  articles_used: number;
  image_style: string;
}

// Setting types
export interface Setting {
  id: string;
  key: string;
  value: string;
  is_encrypted: boolean;
  category: string;
  description: string | null;
}

// Content categories
export type ContentCategory =
  | 'real_estate'
  | 'economy'
  | 'tech'
  | 'construction'
  | 'regulation'
  | 'lifestyle'
  | 'events'
  | 'tourism'
  | 'food_dining'
  | 'sports'
  | 'transportation'
  | 'culture'
  | 'entertainment'
  | 'education'
  | 'health'
  | 'environment'
  | 'government'
  | 'business'
  | 'general';

// Dashboard types
export interface DashboardStats {
  posts_today: number;
  posts_published: number;
  pending_review: number;
  subscribers: number;
  subscriber_change: number;
  avg_engagement_rate: number;
}

export interface SlotSummary {
  id: string;
  scheduled_time: string;
  content_type: string;
  status: SlotStatus;
  has_options: boolean;
  selected_option_label: string | null;
  minutes_until_deadline: number | null;
}

export interface TodaySchedule {
  date: string;
  slots: SlotSummary[];
}

export interface PendingAction {
  id: string;
  type: string;
  title: string;
  description: string;
  deadline: string | null;
  urgency: 'low' | 'medium' | 'high' | 'critical';
}

// Pagination types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// API Response types
export interface ApiError {
  detail: string;
}

export interface MessageResponse {
  message: string;
  success: boolean;
}

// Analytics Summary types
export interface AnalyticsSummary {
  period_days: number;
  current_subscribers: number;
  subscriber_growth: number;
  total_posts: number;
  total_views: number;
  avg_engagement_rate: number;
}

export interface ChannelGrowth {
  date: string;
  subscribers: number;
  growth: number;
  posts_published: number;
  avg_views: number;
}

export interface TopPost {
  id: string;
  title: string;
  published_at: string;
  views: number;
  engagement_rate: number;
  content_type: string;
}

// Content Queue types
export interface ContentQueueResponse {
  date: string;
  slots: ContentSlot[];
  stats: {
    total_slots: number;
    pending: number;
    generating: number;
    options_ready: number;
    approved: number;
    published: number;
    failed: number;
  };
}

// Publish Response types
export interface PublishResponse {
  slot_id: string;
  success: boolean;
  message_id_en?: number;
  message_id_ru?: number;
  published_post_id?: string;
  channel_id?: string;
  error?: string;
}
