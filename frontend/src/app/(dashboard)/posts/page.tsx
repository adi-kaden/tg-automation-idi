'use client';

import { useState } from 'react';
import {
  Eye,
  Forward,
  ExternalLink,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { usePublishedPosts } from '@/hooks/use-api';
import { PostDetailDrawer } from '@/components/posts/post-detail-drawer';
import type { PublishedPostDetail } from '@/types';

type SortField = 'published_at' | 'views' | 'engagement_rate' | 'forwards';
type ContentFilter = 'all' | 'real_estate' | 'general_dubai';

function formatDubaiDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('en-US', {
    timeZone: 'Asia/Dubai',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getTotalReactions(reactions: Record<string, number> | null | undefined): number {
  if (!reactions) return 0;
  return Object.values(reactions).reduce((sum, count) => sum + count, 0);
}

function SortIcon({ field, currentSort, currentOrder }: { field: SortField; currentSort: SortField; currentOrder: string }) {
  if (field !== currentSort) return <ArrowUpDown className="h-3 w-3 ml-1 opacity-40" />;
  return currentOrder === 'desc'
    ? <ArrowDown className="h-3 w-3 ml-1" />
    : <ArrowUp className="h-3 w-3 ml-1" />;
}

export default function PostsPage() {
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [sortBy, setSortBy] = useState<SortField>('published_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [filterType, setFilterType] = useState<ContentFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const { data, isLoading, isError } = usePublishedPosts({
    page,
    per_page: perPage,
    content_type: filterType === 'all' ? undefined : filterType,
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const handleFilterType = (type: ContentFilter) => {
    setFilterType(type);
    setPage(1);
  };

  const handleRowClick = (post: PublishedPostDetail) => {
    setSelectedPostId(post.id);
    setDrawerOpen(true);
  };

  // Client-side search filter on loaded data
  const filteredItems = data?.items?.filter((post) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      post.posted_title.toLowerCase().includes(q) ||
      post.posted_body.toLowerCase().includes(q)
    );
  }) ?? [];

  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Published Posts
            <Badge variant="outline">{total} total posts</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex gap-4 mb-6 flex-wrap">
            <Input
              placeholder="Search posts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="max-w-xs"
            />
            <div className="flex gap-2">
              <Button
                variant={filterType === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleFilterType('all')}
              >
                All
              </Button>
              <Button
                variant={filterType === 'real_estate' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleFilterType('real_estate')}
              >
                Real Estate
              </Button>
              <Button
                variant={filterType === 'general_dubai' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleFilterType('general_dubai')}
              >
                Dubai Trending
              </Button>
            </div>
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : isError ? (
            <p className="text-sm text-red-500 text-center py-8">
              Failed to load published posts. Please try again.
            </p>
          ) : filteredItems.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No published posts found.
            </p>
          ) : (
            <>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        <button
                          className="flex items-center font-medium hover:text-foreground"
                          onClick={() => handleSort('published_at')}
                        >
                          Date
                          <SortIcon field="published_at" currentSort={sortBy} currentOrder={sortOrder} />
                        </button>
                      </TableHead>
                      <TableHead className="min-w-[200px]">Title</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>
                        <button
                          className="flex items-center font-medium hover:text-foreground"
                          onClick={() => handleSort('views')}
                        >
                          <Eye className="h-3.5 w-3.5 mr-1" />
                          Views
                          <SortIcon field="views" currentSort={sortBy} currentOrder={sortOrder} />
                        </button>
                      </TableHead>
                      <TableHead>Reactions</TableHead>
                      <TableHead>
                        <button
                          className="flex items-center font-medium hover:text-foreground"
                          onClick={() => handleSort('forwards')}
                        >
                          <Forward className="h-3.5 w-3.5 mr-1" />
                          Fwd
                          <SortIcon field="forwards" currentSort={sortBy} currentOrder={sortOrder} />
                        </button>
                      </TableHead>
                      <TableHead>
                        <button
                          className="flex items-center font-medium hover:text-foreground"
                          onClick={() => handleSort('engagement_rate')}
                        >
                          Eng%
                          <SortIcon field="engagement_rate" currentSort={sortBy} currentOrder={sortOrder} />
                        </button>
                      </TableHead>
                      <TableHead className="w-10"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredItems.map((post) => (
                      <TableRow
                        key={post.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => handleRowClick(post)}
                      >
                        <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                          {formatDubaiDate(post.published_at)}
                        </TableCell>
                        <TableCell>
                          <div className="max-w-[300px]">
                            <p className="text-sm font-medium truncate">{post.posted_title}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {post.content_type && (
                              <Badge
                                variant={post.content_type === 'real_estate' ? 'default' : 'secondary'}
                                className="text-xs"
                              >
                                {post.content_type === 'real_estate' ? 'RE' : 'TR'}
                              </Badge>
                            )}
                            <Badge variant="outline" className="text-xs">
                              {post.posted_language.toUpperCase()}
                            </Badge>
                          </div>
                        </TableCell>
                        <TableCell className="font-medium">
                          {post.analytics?.views?.toLocaleString() ?? '—'}
                        </TableCell>
                        <TableCell>
                          {post.analytics ? getTotalReactions(post.analytics.reactions).toLocaleString() : '—'}
                        </TableCell>
                        <TableCell>
                          {post.analytics?.forwards?.toLocaleString() ?? '—'}
                        </TableCell>
                        <TableCell>
                          {post.analytics
                            ? `${post.analytics.engagement_rate.toFixed(1)}%`
                            : '—'}
                        </TableCell>
                        <TableCell>
                          {post.telegram_link && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              asChild
                              onClick={(e) => e.stopPropagation()}
                            >
                              <a href={post.telegram_link} target="_blank" rel="noopener noreferrer">
                                <ExternalLink className="h-4 w-4" />
                              </a>
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {pages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {pages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage(page - 1)}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= pages}
                      onClick={() => setPage(page + 1)}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Detail Drawer */}
      <PostDetailDrawer
        postId={selectedPostId}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </div>
  );
}
