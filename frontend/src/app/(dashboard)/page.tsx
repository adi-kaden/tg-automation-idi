'use client';

import Link from 'next/link';
import {
  FileText,
  Clock,
  Users,
  TrendingUp,
  Rss,
  BarChart3,
  ArrowRight,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useDashboardStats,
  useTodaySchedule,
  usePendingActions,
} from '@/hooks/use-api';

export default function DashboardPage() {
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useDashboardStats();

  const {
    data: schedule,
    isLoading: scheduleLoading,
    error: scheduleError,
  } = useTodaySchedule();

  const {
    data: pending,
    isLoading: pendingLoading,
    error: pendingError,
  } = usePendingActions();

  const isLoading = statsLoading || scheduleLoading || pendingLoading;
  const hasError = statsError || scheduleError || pendingError;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'published':
        return 'bg-green-500';
      case 'approved':
        return 'bg-blue-500';
      case 'options_ready':
        return 'bg-amber-500';
      case 'generating':
        return 'bg-purple-500';
      case 'pending':
        return 'bg-slate-400';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-slate-400';
    }
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'critical':
        return 'destructive';
      case 'high':
        return 'destructive';
      case 'medium':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <Skeleton className="h-6 w-40" />
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-32" />
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-24 w-full" />
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
        <h2 className="text-xl font-semibold mb-2">Failed to load dashboard</h2>
        <p className="text-slate-500 mb-4">
          {statsError?.message || scheduleError?.message || pendingError?.message || 'An error occurred'}
        </p>
        <Button onClick={() => refetchStats()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">
              Posts Today
            </CardTitle>
            <FileText className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.posts_published || 0}/{stats?.posts_today || 5}
            </div>
            <p className="text-xs text-slate-500">published</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">
              Pending Review
            </CardTitle>
            <Clock className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">
              {stats?.pending_review || 0}
            </div>
            <p className="text-xs text-slate-500">need attention</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">
              Subscribers
            </CardTitle>
            <Users className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.subscribers?.toLocaleString() || '0'}
            </div>
            <p className={`text-xs ${(stats?.subscriber_change || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {(stats?.subscriber_change || 0) >= 0 ? '+' : ''}{stats?.subscriber_change || 0} today
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">
              Avg Engagement
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.avg_engagement_rate?.toFixed(1) || '0'}%
            </div>
            <p className="text-xs text-slate-500">last 7 days</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Today's Schedule */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Today&apos;s Schedule
              <Badge variant="outline">
                {new Date().toLocaleDateString('en-US', {
                  weekday: 'long',
                  month: 'short',
                  day: 'numeric',
                })}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {schedule?.slots && schedule.slots.length > 0 ? (
              <div className="space-y-3">
                {schedule.slots.map((slot) => (
                  <div
                    key={slot.id}
                    className="flex items-center gap-4 rounded-lg border p-3"
                  >
                    <div className={`h-3 w-3 rounded-full ${getStatusColor(slot.status)}`} />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{slot.scheduled_time}</span>
                        <Badge variant="secondary" className="text-xs">
                          {slot.content_type === 'real_estate' ? 'Real Estate' : 'Trending'}
                        </Badge>
                      </div>
                      <p className="text-sm text-slate-500">
                        {slot.status === 'published'
                          ? `Published - Option ${slot.selected_option_label}`
                          : slot.status === 'approved'
                          ? `Approved - Option ${slot.selected_option_label}`
                          : slot.status === 'options_ready'
                          ? `Awaiting selection${slot.minutes_until_deadline ? ` (${slot.minutes_until_deadline}m until auto-select)` : ''}`
                          : slot.status === 'generating'
                          ? 'Generating content...'
                          : slot.status === 'failed'
                          ? 'Generation failed'
                          : 'Pending'}
                      </p>
                    </div>
                    {slot.status === 'options_ready' && (
                      <Button asChild size="sm">
                        <Link href={`/content-queue/${slot.id}`}>
                          Review
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </Link>
                      </Button>
                    )}
                    {slot.status === 'approved' && (
                      <Button asChild size="sm" variant="outline">
                        <Link href={`/content-queue/${slot.id}`}>
                          View
                        </Link>
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No slots scheduled for today</p>
                <p className="text-sm">Slots are created automatically at 05:00 Dubai time</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Pending Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-amber-500" />
              Pending Actions
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!pending || pending.length === 0 ? (
              <p className="text-center text-slate-500 py-4">
                All caught up! No pending actions.
              </p>
            ) : (
              <div className="space-y-3">
                {pending.map((action) => (
                  <div
                    key={action.id}
                    className="rounded-lg border p-3 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{action.title}</span>
                      <Badge variant={getUrgencyColor(action.urgency) as 'default' | 'secondary' | 'destructive' | 'outline'}>
                        {action.urgency}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-500">{action.description}</p>
                    <Button asChild size="sm" className="w-full">
                      <Link href={`/content-queue/${action.id}`}>
                        Take Action
                      </Link>
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/content-queue">
                <FileText className="mr-2 h-4 w-4" />
                Review Content Queue
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/scraper">
                <Rss className="mr-2 h-4 w-4" />
                Run Scraper
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/analytics">
                <BarChart3 className="mr-2 h-4 w-4" />
                View Analytics
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
