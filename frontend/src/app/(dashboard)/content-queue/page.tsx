'use client';

import Link from 'next/link';
import { Clock, CheckCircle2, AlertCircle, Loader2, ArrowRight, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useContentQueue } from '@/hooks/use-api';
import type { ContentSlot } from '@/types';

export default function ContentQueuePage() {
  const { data: queue, isLoading, error, refetch } = useContentQueue();

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'published':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case 'approved':
        return <CheckCircle2 className="h-5 w-5 text-blue-500" />;
      case 'options_ready':
        return <AlertCircle className="h-5 w-5 text-amber-500" />;
      case 'generating':
        return <Loader2 className="h-5 w-5 text-purple-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      default:
        return <Clock className="h-5 w-5 text-slate-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      published: 'default',
      approved: 'secondary',
      options_ready: 'outline',
      generating: 'secondary',
      pending: 'outline',
      failed: 'destructive',
    };
    return variants[status] || 'outline';
  };

  const getMinutesUntilDeadline = (slot: ContentSlot) => {
    if (!slot.approval_deadline) return null;
    const deadline = new Date(slot.approval_deadline);
    const now = new Date();
    const diff = deadline.getTime() - now.getTime();
    if (diff <= 0) return 0;
    return Math.floor(diff / 60000);
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Content Queue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Content Queue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center py-12">
              <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Failed to load content queue</h3>
              <p className="text-slate-500 mb-4">{error.message}</p>
              <Button onClick={() => refetch()}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Try Again
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const slots = queue?.slots || [];

  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      {queue?.stats && (
        <div className="grid gap-4 md:grid-cols-6">
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold">{queue.stats.total_slots}</div>
              <p className="text-xs text-slate-500">Total Slots</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-green-600">{queue.stats.published}</div>
              <p className="text-xs text-slate-500">Published</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-blue-600">{queue.stats.approved}</div>
              <p className="text-xs text-slate-500">Approved</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-amber-600">{queue.stats.options_ready}</div>
              <p className="text-xs text-slate-500">Ready for Review</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-purple-600">{queue.stats.generating}</div>
              <p className="text-xs text-slate-500">Generating</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-slate-400">{queue.stats.pending}</div>
              <p className="text-xs text-slate-500">Pending</p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Content Queue
            <Badge variant="outline">
              {queue?.date
                ? new Date(queue.date).toLocaleDateString('en-US', {
                    weekday: 'long',
                    month: 'short',
                    day: 'numeric',
                  })
                : new Date().toLocaleDateString('en-US', {
                    weekday: 'long',
                    month: 'short',
                    day: 'numeric',
                  })}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {slots.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">No slots scheduled for today</p>
              <p className="text-sm">Slots are created automatically at 05:00 Dubai time</p>
            </div>
          ) : (
            <div className="space-y-4">
              {slots.map((slot) => {
                const minutesUntilDeadline = getMinutesUntilDeadline(slot);
                const selectedOption = slot.options?.find((o) => o.is_selected);

                return (
                  <div
                    key={slot.id}
                    className="flex items-center gap-4 rounded-lg border p-4 hover:bg-slate-50 transition-colors"
                  >
                    {getStatusIcon(slot.status)}
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-semibold">{slot.scheduled_time}</span>
                        <Badge variant="secondary">
                          {slot.content_type === 'real_estate' ? 'Real Estate' : 'Dubai Trending'}
                        </Badge>
                        <Badge variant={getStatusBadge(slot.status)}>
                          {slot.status.replace('_', ' ')}
                        </Badge>
                      </div>
                      <p className="text-sm text-slate-500 mt-1">
                        {slot.status === 'published'
                          ? `Published - Option ${selectedOption?.option_label || 'N/A'}`
                          : slot.status === 'approved'
                          ? `Approved - Option ${selectedOption?.option_label || 'N/A'}`
                          : slot.status === 'options_ready'
                          ? `${slot.options?.length || 0} options ready for review${minutesUntilDeadline !== null ? ` \u2022 ${minutesUntilDeadline}m until auto-select` : ''}`
                          : slot.status === 'generating'
                          ? 'Generating content options...'
                          : slot.status === 'failed'
                          ? 'Content generation failed'
                          : 'Waiting for content generation'}
                      </p>
                    </div>
                    {slot.status === 'options_ready' && (
                      <Button asChild>
                        <Link href={`/content-queue/${slot.id}`}>
                          Review Options
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </Link>
                      </Button>
                    )}
                    {slot.status === 'approved' && (
                      <Button variant="outline" asChild>
                        <Link href={`/content-queue/${slot.id}`}>
                          View & Publish
                        </Link>
                      </Button>
                    )}
                    {slot.status === 'published' && slot.published_post_id && (
                      <Button variant="outline" asChild>
                        <Link href={`/posts/${slot.published_post_id}`}>
                          View Post
                        </Link>
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
