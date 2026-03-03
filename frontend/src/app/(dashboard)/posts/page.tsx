'use client';

import { useState } from 'react';
import { Eye, Heart, MessageCircle, Share2, ExternalLink, Calendar } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';

interface PublishedPost {
  id: string;
  title: string;
  content_preview: string;
  published_at: string;
  content_type: 'real_estate' | 'general_dubai';
  language: 'en' | 'ru';
  views: number;
  reactions: number;
  comments: number;
  shares: number;
  telegram_link: string;
}

const mockPosts: PublishedPost[] = [
  {
    id: '1',
    title: 'Dubai Marina Tower Launch - Premium Units Available',
    content_preview: 'Exclusive pre-launch opportunity for luxury apartments in the heart of Dubai Marina...',
    published_at: '2024-02-23T08:00:00Z',
    content_type: 'real_estate',
    language: 'en',
    views: 2450,
    reactions: 156,
    comments: 23,
    shares: 45,
    telegram_link: 'https://t.me/channel/123',
  },
  {
    id: '2',
    title: 'Dubai Metro Expansion: New Blue Line Announced',
    content_preview: 'Major infrastructure update: RTA announces new metro line connecting key residential areas...',
    published_at: '2024-02-23T04:00:00Z',
    content_type: 'general_dubai',
    language: 'en',
    views: 3200,
    reactions: 234,
    comments: 67,
    shares: 89,
    telegram_link: 'https://t.me/channel/122',
  },
  {
    id: '3',
    title: 'Новые апартаменты в Downtown Dubai',
    content_preview: 'Эксклюзивные апартаменты с видом на Burj Khalifa теперь доступны для предзаказа...',
    published_at: '2024-02-22T16:00:00Z',
    content_type: 'real_estate',
    language: 'ru',
    views: 1890,
    reactions: 98,
    comments: 15,
    shares: 34,
    telegram_link: 'https://t.me/channel/121',
  },
  {
    id: '4',
    title: 'Weekend Events in Dubai: February 24-25',
    content_preview: 'Top picks for this weekend including concerts, exhibitions, and family activities...',
    published_at: '2024-02-22T12:00:00Z',
    content_type: 'general_dubai',
    language: 'en',
    views: 4100,
    reactions: 312,
    comments: 45,
    shares: 120,
    telegram_link: 'https://t.me/channel/120',
  },
];

export default function PostsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'real_estate' | 'general_dubai'>('all');

  const filteredPosts = mockPosts.filter((post) => {
    const matchesSearch = post.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      post.content_preview.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = filterType === 'all' || post.content_type === filterType;
    return matchesSearch && matchesType;
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Published Posts
            <Badge variant="outline">{mockPosts.length} total posts</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex gap-4 mb-6">
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
                onClick={() => setFilterType('all')}
              >
                All
              </Button>
              <Button
                variant={filterType === 'real_estate' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('real_estate')}
              >
                Real Estate
              </Button>
              <Button
                variant={filterType === 'general_dubai' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('general_dubai')}
              >
                Dubai Trending
              </Button>
            </div>
          </div>

          {/* Posts List */}
          <div className="space-y-4">
            {filteredPosts.map((post) => (
              <div
                key={post.id}
                className="flex gap-4 rounded-lg border p-4 hover:bg-slate-50 transition-colors"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant={post.content_type === 'real_estate' ? 'default' : 'secondary'}>
                      {post.content_type === 'real_estate' ? 'Real Estate' : 'Trending'}
                    </Badge>
                    <Badge variant="outline">{post.language.toUpperCase()}</Badge>
                    <span className="text-sm text-slate-500 flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {new Date(post.published_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                  <h3 className="font-semibold mb-1">{post.title}</h3>
                  <p className="text-sm text-slate-600 line-clamp-2">{post.content_preview}</p>

                  {/* Stats */}
                  <div className="flex items-center gap-4 mt-3 text-sm text-slate-500">
                    <span className="flex items-center gap-1">
                      <Eye className="h-4 w-4" />
                      {post.views.toLocaleString()}
                    </span>
                    <span className="flex items-center gap-1">
                      <Heart className="h-4 w-4" />
                      {post.reactions}
                    </span>
                    <span className="flex items-center gap-1">
                      <MessageCircle className="h-4 w-4" />
                      {post.comments}
                    </span>
                    <span className="flex items-center gap-1">
                      <Share2 className="h-4 w-4" />
                      {post.shares}
                    </span>
                  </div>
                </div>
                <div>
                  <Button variant="outline" size="sm" asChild>
                    <a href={post.telegram_link} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="h-4 w-4 mr-1" />
                      View on Telegram
                    </a>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
