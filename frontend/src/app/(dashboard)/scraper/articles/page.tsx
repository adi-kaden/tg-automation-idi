'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  RefreshCw,
  ExternalLink,
  Calendar,
  Tag,
  CheckCircle2,
  Clock,
  Filter,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useScraperArticles } from '@/hooks/use-api';
import { formatDistanceToNow } from 'date-fns';

const CATEGORIES = [
  { value: 'all', label: 'All Categories' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'economy', label: 'Economy' },
  { value: 'business', label: 'Business' },
  { value: 'tech', label: 'Technology' },
  { value: 'lifestyle', label: 'Lifestyle' },
  { value: 'tourism', label: 'Tourism' },
  { value: 'general', label: 'General' },
];

export default function ArticlesPage() {
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<string>('all');
  const [usedFilter, setUsedFilter] = useState<string>('all');

  const { data, isLoading, error, refetch } = useScraperArticles({
    page,
    per_page: 20,
    category: category !== 'all' ? category : undefined,
    is_used: usedFilter === 'all' ? undefined : usedFilter === 'used',
  });

  const articles = data?.items || [];
  const totalPages = data?.pages || 1;
  const total = data?.total || 0;

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Unknown date';
    try {
      const date = new Date(dateStr);
      return formatDistanceToNow(date, { addSuffix: true });
    } catch {
      return dateStr;
    }
  };

  const getCategoryColor = (cat: string) => {
    const colors: Record<string, string> = {
      real_estate: 'bg-blue-100 text-blue-800',
      economy: 'bg-green-100 text-green-800',
      business: 'bg-purple-100 text-purple-800',
      tech: 'bg-cyan-100 text-cyan-800',
      lifestyle: 'bg-pink-100 text-pink-800',
      tourism: 'bg-orange-100 text-orange-800',
      general: 'bg-slate-100 text-slate-800',
    };
    return colors[cat] || 'bg-slate-100 text-slate-800';
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <p className="text-red-500 mb-4">Failed to load articles: {error.message}</p>
        <Button onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/scraper">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Sources
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Scraped Articles</h1>
            <p className="text-sm text-slate-500">
              {total} articles collected from all sources
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-slate-500" />
              <span className="text-sm font-medium">Filters:</span>
            </div>

            <Select value={category} onValueChange={(v) => { setCategory(v); setPage(1); }}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((cat) => (
                  <SelectItem key={cat.value} value={cat.value}>
                    {cat.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={usedFilter} onValueChange={(v) => { setUsedFilter(v); setPage(1); }}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Usage status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Articles</SelectItem>
                <SelectItem value="unused">Unused Only</SelectItem>
                <SelectItem value="used">Used in Posts</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Articles List */}
      <Card>
        <CardHeader>
          <CardTitle>Articles</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="border rounded-lg p-4">
                  <Skeleton className="h-5 w-3/4 mb-2" />
                  <Skeleton className="h-4 w-full mb-2" />
                  <Skeleton className="h-4 w-1/2" />
                </div>
              ))}
            </div>
          ) : articles.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">No articles found</p>
              <p className="text-sm">Try adjusting your filters or run the scraper</p>
            </div>
          ) : (
            <div className="space-y-4">
              {articles.map((article) => (
                <div
                  key={article.id}
                  className="border rounded-lg p-4 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        {article.is_used ? (
                          <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                        ) : (
                          <Clock className="h-4 w-4 text-slate-400 flex-shrink-0" />
                        )}
                        <h3 className="font-medium text-sm line-clamp-2">
                          {article.title}
                        </h3>
                      </div>

                      {article.summary && (
                        <p className="text-sm text-slate-600 line-clamp-2 mb-2 ml-6">
                          {article.summary}
                        </p>
                      )}

                      <div className="flex flex-wrap items-center gap-2 ml-6">
                        <Badge
                          variant="secondary"
                          className={getCategoryColor(article.category)}
                        >
                          {article.category.replace('_', ' ')}
                        </Badge>

                        <span className="text-xs text-slate-500 flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatDate(article.published_at)}
                        </span>

                        {article.is_used && (
                          <Badge variant="outline" className="text-green-600 border-green-300">
                            Used in post
                          </Badge>
                        )}

                        {article.relevance_score > 0 && (
                          <span className="text-xs text-slate-500">
                            Relevance: {(article.relevance_score * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                    </div>

                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-shrink-0"
                    >
                      <Button variant="ghost" size="sm">
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t">
              <p className="text-sm text-slate-500">
                Page {page} of {totalPages} ({total} total)
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
