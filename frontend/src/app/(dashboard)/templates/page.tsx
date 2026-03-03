'use client';

import { useState } from 'react';
import { Plus, Edit2, Trash2, Copy, FileCode2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface Template {
  id: string;
  name: string;
  content_type: 'real_estate' | 'general_dubai';
  language: 'en' | 'ru' | 'both';
  description: string;
  used_count: number;
  last_used: string | null;
  is_active: boolean;
}

const mockTemplates: Template[] = [
  {
    id: '1',
    name: 'Property Launch Announcement',
    content_type: 'real_estate',
    language: 'both',
    description: 'Template for new property development launches with pricing and features.',
    used_count: 45,
    last_used: '2024-02-23T08:00:00Z',
    is_active: true,
  },
  {
    id: '2',
    name: 'Market Report Summary',
    content_type: 'real_estate',
    language: 'en',
    description: 'Weekly/monthly real estate market statistics and trends.',
    used_count: 12,
    last_used: '2024-02-20T16:00:00Z',
    is_active: true,
  },
  {
    id: '3',
    name: 'Dubai News Brief',
    content_type: 'general_dubai',
    language: 'both',
    description: 'General news and updates about Dubai events and announcements.',
    used_count: 89,
    last_used: '2024-02-23T12:00:00Z',
    is_active: true,
  },
  {
    id: '4',
    name: 'Weekend Events Guide',
    content_type: 'general_dubai',
    language: 'en',
    description: 'Weekly roundup of events, activities, and things to do in Dubai.',
    used_count: 24,
    last_used: '2024-02-22T12:00:00Z',
    is_active: true,
  },
  {
    id: '5',
    name: 'Investment Opportunity',
    content_type: 'real_estate',
    language: 'ru',
    description: 'Template targeting Russian-speaking investors with ROI focus.',
    used_count: 18,
    last_used: '2024-02-21T08:00:00Z',
    is_active: false,
  },
];

export default function TemplatesPage() {
  const [templates] = useState(mockTemplates);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCode2 className="h-5 w-5" />
              Post Templates
            </div>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-2" />
              New Template
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {templates.map((template) => (
              <div
                key={template.id}
                className={`flex items-center gap-4 rounded-lg border p-4 ${
                  !template.is_active ? 'opacity-60 bg-slate-50' : ''
                }`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">{template.name}</span>
                    <Badge variant={template.content_type === 'real_estate' ? 'default' : 'secondary'}>
                      {template.content_type === 'real_estate' ? 'Real Estate' : 'Trending'}
                    </Badge>
                    <Badge variant="outline">
                      {template.language === 'both' ? 'EN/RU' : template.language.toUpperCase()}
                    </Badge>
                    {!template.is_active && (
                      <Badge variant="outline" className="text-slate-500">
                        Inactive
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-slate-600">{template.description}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                    <span>Used {template.used_count} times</span>
                    {template.last_used && (
                      <span>
                        Last used:{' '}
                        {new Date(template.last_used).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon">
                    <Copy className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon">
                    <Edit2 className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="text-red-500 hover:text-red-600">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>

          {/* Template Structure Info */}
          <div className="mt-8 p-4 bg-slate-50 rounded-lg">
            <h3 className="font-medium mb-2">Template Variables</h3>
            <p className="text-sm text-slate-600 mb-3">
              Use these variables in your templates. They will be replaced with actual content during generation.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
              <code className="bg-white px-2 py-1 rounded border">{'{{title}}'}</code>
              <code className="bg-white px-2 py-1 rounded border">{'{{summary}}'}</code>
              <code className="bg-white px-2 py-1 rounded border">{'{{location}}'}</code>
              <code className="bg-white px-2 py-1 rounded border">{'{{price}}'}</code>
              <code className="bg-white px-2 py-1 rounded border">{'{{date}}'}</code>
              <code className="bg-white px-2 py-1 rounded border">{'{{source}}'}</code>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
