'use client';

import { useState } from 'react';
import { TrendingUp, TrendingDown, Users, Eye, Heart, MessageCircle, RefreshCw, AlertCircle, BarChart3 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnalyticsSummary, useTopPosts, useAnalyticsGrowth } from '@/hooks/use-api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

type TimeRange = 7 | 30 | 90;

// Color palette for charts
const COLORS = {
  primary: '#3b82f6',
  secondary: '#10b981',
  accent: '#8b5cf6',
  warning: '#f59e0b',
  muted: '#94a3b8',
};

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

// Custom tooltip for charts
interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name?: string;
    value?: number;
    color?: string;
  }>;
  label?: string;
}

const CustomTooltip = ({ active, payload, label }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 border rounded-lg shadow-lg">
        <p className="font-medium text-sm mb-1">
          {typeof label === 'string' && label.includes('-')
            ? new Date(label).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
            : label}
        </p>
        {payload.map((entry, index) => (
          <p key={index} className="text-sm" style={{ color: entry.color }}>
            {entry.name}: {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
            {entry.name?.toLowerCase().includes('rate') ? '%' : ''}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>(7);

  const { data: summary, isLoading: summaryLoading, error: summaryError, refetch } = useAnalyticsSummary(timeRange);
  const { data: topPosts, isLoading: postsLoading } = useTopPosts(10);
  const { data: growth, isLoading: growthLoading } = useAnalyticsGrowth(timeRange);

  const isLoading = summaryLoading || postsLoading || growthLoading;

  // Calculate content type breakdown from top posts
  const contentTypeBreakdown = topPosts?.reduce((acc, post) => {
    const type = post.content_type || 'other';
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const pieChartData = contentTypeBreakdown
    ? Object.entries(contentTypeBreakdown).map(([name, value]) => ({
        name: name === 'real_estate' ? 'Real Estate' : name === 'general_dubai' ? 'Dubai Trending' : name,
        value,
      }))
    : [];

  const StatCard = ({
    title,
    value,
    change,
    icon: Icon,
    suffix = '',
    loading = false,
  }: {
    title: string;
    value: number | string;
    change?: number;
    icon: React.ElementType;
    suffix?: string;
    loading?: boolean;
  }) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-slate-600">{title}</CardTitle>
        <Icon className="h-4 w-4 text-slate-400" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <>
            <Skeleton className="h-8 w-20 mb-1" />
            <Skeleton className="h-4 w-24" />
          </>
        ) : (
          <>
            <div className="text-2xl font-bold">
              {typeof value === 'number' ? value.toLocaleString() : value}
              {suffix}
            </div>
            {change !== undefined && (
              <div className={`flex items-center text-xs ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {change >= 0 ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
                {change >= 0 ? '+' : ''}{change} vs previous period
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );

  if (summaryError) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
        <h2 className="text-xl font-semibold mb-2">Failed to load analytics</h2>
        <p className="text-slate-500 mb-4">{summaryError.message}</p>
        <Button onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Time Range Selector */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Channel Analytics</h2>
        <div className="flex gap-2">
          {([7, 30, 90] as TimeRange[]).map((range) => (
            <Button
              key={range}
              variant={timeRange === range ? 'default' : 'outline'}
              size="sm"
              onClick={() => setTimeRange(range)}
            >
              {range} Days
            </Button>
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Subscribers"
          value={summary?.current_subscribers || 0}
          change={summary?.subscriber_growth}
          icon={Users}
          loading={summaryLoading}
        />
        <StatCard
          title="Total Views"
          value={summary?.total_views || 0}
          icon={Eye}
          loading={summaryLoading}
        />
        <StatCard
          title="Avg Engagement"
          value={summary?.avg_engagement_rate?.toFixed(1) || '0'}
          icon={Heart}
          suffix="%"
          loading={summaryLoading}
        />
        <StatCard
          title="Total Posts"
          value={summary?.total_posts || 0}
          icon={MessageCircle}
          loading={summaryLoading}
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-500" />
              Subscriber Growth
            </CardTitle>
          </CardHeader>
          <CardContent>
            {growthLoading ? (
              <Skeleton className="h-[300px] w-full" />
            ) : growth && growth.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={growth}>
                  <defs>
                    <linearGradient id="subscriberGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={COLORS.primary} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={COLORS.primary} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    stroke="#94a3b8"
                    fontSize={12}
                  />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="subscribers"
                    stroke={COLORS.primary}
                    strokeWidth={2}
                    fill="url(#subscriberGradient)"
                    name="Subscribers"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center bg-slate-50 rounded-lg">
                <p className="text-slate-500">No growth data available yet</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-green-500" />
              Daily Posts & Views
            </CardTitle>
          </CardHeader>
          <CardContent>
            {growthLoading ? (
              <Skeleton className="h-[300px] w-full" />
            ) : growth && growth.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={growth}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    stroke="#94a3b8"
                    fontSize={12}
                  />
                  <YAxis yAxisId="left" orientation="left" stroke={COLORS.primary} fontSize={12} />
                  <YAxis yAxisId="right" orientation="right" stroke={COLORS.secondary} fontSize={12} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ paddingTop: '10px' }} />
                  <Bar yAxisId="left" dataKey="posts_published" fill={COLORS.primary} name="Posts Published" radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="right" dataKey="avg_views" fill={COLORS.secondary} name="Avg Views" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center bg-slate-50 rounded-lg">
                <p className="text-slate-500">No post data available yet</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Engagement Rate Trend */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Heart className="h-5 w-5 text-pink-500" />
              Engagement Rate Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            {growthLoading ? (
              <Skeleton className="h-[250px] w-full" />
            ) : growth && growth.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={growth}>
                  <defs>
                    <linearGradient id="engagementGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={COLORS.accent} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={COLORS.accent} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    stroke="#94a3b8"
                    fontSize={12}
                  />
                  <YAxis
                    stroke="#94a3b8"
                    fontSize={12}
                    tickFormatter={(value) => `${value}%`}
                  />
                  <Tooltip
                    content={<CustomTooltip />}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg_views"
                    stroke={COLORS.accent}
                    strokeWidth={2}
                    dot={{ fill: COLORS.accent, strokeWidth: 2, r: 3 }}
                    activeDot={{ r: 5, stroke: COLORS.accent, strokeWidth: 2 }}
                    name="Engagement Rate"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center bg-slate-50 rounded-lg">
                <p className="text-slate-500">No engagement data available yet</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Content Type Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageCircle className="h-5 w-5 text-amber-500" />
              Content Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            {postsLoading ? (
              <Skeleton className="h-[250px] w-full" />
            ) : pieChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={pieChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {pieChartData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center bg-slate-50 rounded-lg">
                <p className="text-slate-500">No content data yet</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Performance Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="bg-gradient-to-br from-blue-50 to-white">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 rounded-full">
                <TrendingUp className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-slate-600">Best Performing Day</p>
                <p className="text-lg font-bold">
                  {growth && growth.length > 0
                    ? new Date(
                        growth.reduce((max, day) =>
                          (day.avg_views || 0) > (max.avg_views || 0) ? day : max
                        ).date
                      ).toLocaleDateString('en-US', { weekday: 'long' })
                    : 'N/A'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-50 to-white">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-100 rounded-full">
                <Eye className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-slate-600">Peak Views</p>
                <p className="text-lg font-bold">
                  {growth && growth.length > 0
                    ? Math.max(...growth.map(d => d.avg_views || 0)).toLocaleString()
                    : 'N/A'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-50 to-white">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-purple-100 rounded-full">
                <MessageCircle className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-slate-600">Posts This Period</p>
                <p className="text-lg font-bold">
                  {growth && growth.length > 0
                    ? growth.reduce((sum, d) => sum + (d.posts_published || 0), 0)
                    : 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Performing Posts */}
      <Card>
        <CardHeader>
          <CardTitle>Top Performing Posts</CardTitle>
        </CardHeader>
        <CardContent>
          {postsLoading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : topPosts && topPosts.length > 0 ? (
            <div className="space-y-4">
              {topPosts.map((post, index) => (
                <div
                  key={post.id}
                  className="flex items-center gap-4 p-3 rounded-lg border"
                >
                  <div className="text-lg font-bold text-slate-400 w-6">
                    {index + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{post.title}</span>
                      <Badge variant="secondary">
                        {post.content_type}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-500">
                      {new Date(post.published_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                  <div className="flex items-center gap-6 text-sm text-slate-600">
                    <span className="flex items-center gap-1">
                      <Eye className="h-4 w-4" />
                      {post.views.toLocaleString()}
                    </span>
                    <span className="flex items-center gap-1">
                      <TrendingUp className="h-4 w-4" />
                      {post.engagement_rate.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">
              <MessageCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No published posts yet</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
