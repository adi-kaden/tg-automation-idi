'use client';

import Link from 'next/link';
import { Play, RefreshCw, CheckCircle2, XCircle, Clock, ExternalLink, Loader2, AlertCircle, FileText, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { useScraperSources, useRunScraper, useToggleSource } from '@/hooks/use-api';
import { toast } from 'sonner';

export default function ScraperPage() {
  const { data: sources, isLoading, error, refetch } = useScraperSources();
  const runScraperMutation = useRunScraper();
  const toggleSourceMutation = useToggleSource();

  const handleToggleSource = (id: string, currentState: boolean) => {
    toggleSourceMutation.mutate(
      { id, isActive: !currentState },
      {
        onSuccess: () => {
          toast.success(`Source ${!currentState ? 'enabled' : 'disabled'}`);
        },
        onError: (error) => {
          toast.error(`Failed to toggle source: ${error.message}`);
        },
      }
    );
  };

  const handleRunScraper = () => {
    runScraperMutation.mutate(undefined, {
      onSuccess: () => {
        toast.success('Scraper started successfully');
      },
      onError: (error) => {
        toast.error(`Failed to start scraper: ${error.message}`);
      },
    });
  };

  const getStatusIcon = (source: { last_error: string | null; last_scraped_at: string | null }) => {
    if (source.last_error) {
      return <XCircle className="h-4 w-4 text-red-500" />;
    }
    if (source.last_scraped_at) {
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    }
    return <Clock className="h-4 w-4 text-slate-400" />;
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          {[...Array(3)].map((_, i) => (
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
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
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
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
        <h2 className="text-xl font-semibold mb-2">Failed to load scraper sources</h2>
        <p className="text-slate-500 mb-4">{error.message}</p>
        <Button onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
      </div>
    );
  }

  const sourceList = sources || [];
  const enabledCount = sourceList.filter((s) => s.is_active).length;
  const lastRun = sourceList.reduce((latest, s) => {
    if (!s.last_scraped_at) return latest;
    const scraped = new Date(s.last_scraped_at);
    return scraped > latest ? scraped : latest;
  }, new Date(0));

  return (
    <div className="space-y-6">
      {/* Status Overview */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">Active Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {enabledCount}/{sourceList.length}
            </div>
            <p className="text-xs text-slate-500">enabled sources</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">Last Run</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {lastRun.getTime() > 0
                ? lastRun.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
                : 'Never'}
            </div>
            <p className="text-xs text-slate-500">
              {lastRun.getTime() > 0
                ? lastRun.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                : 'No scrapes yet'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">Source Health</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {sourceList.filter((s) => !s.last_error && s.last_scraped_at).length}/{sourceList.length}
            </div>
            <p className="text-xs text-slate-500">healthy sources</p>
          </CardContent>
        </Card>

        <Link href="/scraper/articles">
          <Card className="cursor-pointer hover:bg-slate-50 transition-colors">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-600 flex items-center gap-2">
                <FileText className="h-4 w-4" />
                View Articles
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500">Browse all scraped articles</p>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </div>
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* Sources List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Scrape Sources
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh Status
              </Button>
              <Button
                size="sm"
                onClick={handleRunScraper}
                disabled={runScraperMutation.isPending}
              >
                {runScraperMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Run Scraper Now
                  </>
                )}
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {sourceList.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">No scrape sources configured</p>
              <p className="text-sm">Add sources to start collecting content</p>
            </div>
          ) : (
            <div className="space-y-4">
              {sourceList.map((source) => (
                <div
                  key={source.id}
                  className="flex items-center gap-4 rounded-lg border p-4"
                >
                  <Switch
                    checked={source.is_active}
                    onCheckedChange={() => handleToggleSource(source.id, source.is_active)}
                    disabled={toggleSourceMutation.isPending}
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{source.name}</span>
                      <Badge variant="outline" className="text-xs">
                        {source.source_type}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {source.category}
                      </Badge>
                    </div>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
                    >
                      {source.url.length > 50 ? `${source.url.substring(0, 50)}...` : source.url}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                  <div className="text-right">
                    <div className="flex items-center gap-2 justify-end">
                      {getStatusIcon(source)}
                      <span className="text-sm">
                        {source.last_scraped_at
                          ? new Date(source.last_scraped_at).toLocaleTimeString('en-US', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : 'Never'}
                      </span>
                    </div>
                    {source.last_error && (
                      <p className="text-xs text-red-500 mt-1 max-w-[200px] truncate">
                        {source.last_error}
                      </p>
                    )}
                    <p className="text-xs text-slate-500 mt-1">
                      Reliability: {(source.reliability_score * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Schedule Info */}
      <Card>
        <CardHeader>
          <CardTitle>Scraper Schedule</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-lg">
            <Clock className="h-8 w-8 text-slate-400" />
            <div>
              <p className="font-medium">Daily at 04:00 Dubai Time (GMT+4)</p>
              <p className="text-sm text-slate-500">
                The scraper automatically runs every day at 4:00 AM to collect fresh content for the day&apos;s posts.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
