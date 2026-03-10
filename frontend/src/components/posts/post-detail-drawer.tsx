'use client';

import { Eye, Forward, MessageCircle, ExternalLink, TrendingUp, Clock, User } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { usePublishedPost } from '@/hooks/use-api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

interface PostDetailDrawerProps {
  postId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatDubaiDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('en-US', {
    timeZone: 'Asia/Dubai',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function PostDetailDrawer({ postId, open, onOpenChange }: PostDetailDrawerProps) {
  const { data: post, isLoading } = usePublishedPost(postId || '');

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Post Details</SheetTitle>
        </SheetHeader>

        {isLoading ? (
          <div className="space-y-4 mt-4">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : !post ? (
          <p className="text-sm text-muted-foreground mt-4">Post not found.</p>
        ) : (
          <ScrollArea className="h-[calc(100vh-100px)] mt-4 pr-4">
            <div className="space-y-4">
              {/* Image */}
              {post.image_url_served && (
                <div className="rounded-lg overflow-hidden border bg-muted">
                  <img
                    src={`${API_BASE_URL.replace('/api', '')}${post.image_url_served}`}
                    alt={post.posted_title}
                    className="w-full h-auto object-cover max-h-64"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
              )}

              {/* Title */}
              <h3 className="text-lg font-semibold leading-tight">{post.posted_title}</h3>

              {/* Badges */}
              <div className="flex items-center gap-2 flex-wrap">
                {post.content_type && (
                  <Badge variant={post.content_type === 'real_estate' ? 'default' : 'secondary'}>
                    {post.content_type === 'real_estate' ? 'Real Estate' : 'Trending'}
                  </Badge>
                )}
                <Badge variant="outline">{post.posted_language.toUpperCase()}</Badge>
                <span className="text-sm text-muted-foreground flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDubaiDate(post.published_at)}
                </span>
              </div>

              {/* Selection info */}
              <div className="flex items-center gap-1 text-sm text-muted-foreground">
                <User className="h-3 w-3" />
                Selected by: <Badge variant="outline" className="text-xs">{post.selected_by.toUpperCase()}</Badge>
              </div>

              <Separator />

              {/* Body */}
              <div className="text-sm whitespace-pre-wrap leading-relaxed">
                {post.posted_body}
              </div>

              <Separator />

              {/* Analytics */}
              {post.analytics ? (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold">Analytics</h4>

                  {/* Core metrics */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-lg border p-3 text-center">
                      <Eye className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                      <p className="text-lg font-semibold">{post.analytics.views.toLocaleString()}</p>
                      <p className="text-xs text-muted-foreground">Views</p>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <Forward className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                      <p className="text-lg font-semibold">{post.analytics.forwards.toLocaleString()}</p>
                      <p className="text-xs text-muted-foreground">Forwards</p>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <MessageCircle className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                      <p className="text-lg font-semibold">{post.analytics.replies.toLocaleString()}</p>
                      <p className="text-xs text-muted-foreground">Replies</p>
                    </div>
                  </div>

                  {/* Reactions */}
                  {post.analytics.reactions && Object.keys(post.analytics.reactions).length > 0 && (
                    <div>
                      <p className="text-sm text-muted-foreground mb-2">Reactions</p>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(post.analytics.reactions)
                          .sort(([, a], [, b]) => b - a)
                          .map(([emoji, count]) => (
                            <div
                              key={emoji}
                              className="flex items-center gap-1 rounded-full border px-3 py-1 text-sm"
                            >
                              <span>{emoji}</span>
                              <span className="font-medium">{count}</span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Engagement & Growth */}
                  <div className="rounded-lg border p-3 space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Engagement Rate</span>
                      <span className="font-medium">{post.analytics.engagement_rate.toFixed(2)}%</span>
                    </div>
                    {post.analytics.view_growth_1h !== null && (
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <TrendingUp className="h-3 w-3" /> Growth (1h)
                        </span>
                        <span className={`font-medium ${post.analytics.view_growth_1h >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {post.analytics.view_growth_1h >= 0 ? '+' : ''}{post.analytics.view_growth_1h.toFixed(1)}%
                        </span>
                      </div>
                    )}
                    {post.analytics.view_growth_24h !== null && (
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <TrendingUp className="h-3 w-3" /> Growth (24h)
                        </span>
                        <span className={`font-medium ${post.analytics.view_growth_24h >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {post.analytics.view_growth_24h >= 0 ? '+' : ''}{post.analytics.view_growth_24h.toFixed(1)}%
                        </span>
                      </div>
                    )}
                    {post.analytics.last_fetched_at && (
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Last Updated</span>
                        <span className="text-xs text-muted-foreground">
                          {formatDubaiDate(post.analytics.last_fetched_at)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No analytics data yet. Data will appear after the next collection cycle.</p>
              )}

              <Separator />

              {/* Telegram Link */}
              {post.telegram_link && (
                <Button variant="outline" className="w-full" asChild>
                  <a href={post.telegram_link} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4 mr-2" />
                    View on Telegram
                  </a>
                </Button>
              )}
            </div>
          </ScrollArea>
        )}
      </SheetContent>
    </Sheet>
  );
}
