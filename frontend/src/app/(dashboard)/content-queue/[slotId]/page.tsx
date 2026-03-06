'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Check,
  Clock,
  Edit3,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  Send,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  useContentSlot,
  useSelectOption,
  usePublishSlot,
  useUpdateOption,
  useRegenerateSlot,
} from '@/hooks/use-api';
import { toast } from 'sonner';
import type { PostOption } from '@/types';

export default function SlotDetailPage() {
  const params = useParams();
  const router = useRouter();
  const slotId = params.slotId as string;

  const { data: slot, isLoading, error, refetch } = useContentSlot(slotId);
  const selectMutation = useSelectOption();
  const publishMutation = usePublishSlot();
  const updateMutation = useUpdateOption();
  const regenerateMutation = useRegenerateSlot();

  const [editingOption, setEditingOption] = useState<PostOption | null>(null);
  const [editForm, setEditForm] = useState({
    title_en: '',
    body_en: '',
    title_ru: '',
    body_ru: '',
  });
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  const handleSelectOption = (optionId: string) => {
    selectMutation.mutate(
      { slotId, optionId },
      {
        onSuccess: () => {
          toast.success('Option selected successfully');
          refetch();
        },
        onError: (error) => {
          toast.error(`Failed to select option: ${error.message}`);
        },
      }
    );
  };

  const handlePublish = () => {
    publishMutation.mutate(slotId, {
      onSuccess: (data) => {
        if (data.success) {
          toast.success('Post published to Telegram!');
          setPublishDialogOpen(false);
          refetch();
        } else {
          toast.error(`Failed to publish: ${data.error}`);
        }
      },
      onError: (error) => {
        toast.error(`Failed to publish: ${error.message}`);
      },
    });
  };

  const handleEditOption = (option: PostOption) => {
    setEditingOption(option);
    setEditForm({
      title_en: option.title_en,
      body_en: option.body_en,
      title_ru: option.title_ru,
      body_ru: option.body_ru,
    });
  };

  const handleSaveEdit = () => {
    if (!editingOption) return;

    updateMutation.mutate(
      {
        optionId: editingOption.id,
        data: editForm,
      },
      {
        onSuccess: () => {
          toast.success('Content updated successfully');
          setEditingOption(null);
          refetch();
        },
        onError: (error) => {
          toast.error(`Failed to update: ${error.message}`);
        },
      }
    );
  };

  const handleRegenerate = () => {
    setIsRegenerating(true);
    regenerateMutation.mutate(slotId, {
      onSuccess: () => {
        toast.success('Regeneration started - this may take a minute');
        // Poll for completion every 3 seconds
        const pollInterval = setInterval(async () => {
          const result = await refetch();
          if (result.data?.status !== 'generating') {
            setIsRegenerating(false);
            clearInterval(pollInterval);
            if (result.data?.status === 'options_ready') {
              toast.success('Content regenerated successfully');
            }
          }
        }, 3000);
        // Timeout after 2 minutes
        setTimeout(() => {
          setIsRegenerating(false);
          clearInterval(pollInterval);
        }, 120000);
      },
      onError: (error) => {
        setIsRegenerating(false);
        toast.error(`Failed to regenerate: ${error.message}`);
      },
    });
  };

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

  const getMinutesUntilDeadline = () => {
    if (!slot?.approval_deadline) return null;
    const deadline = new Date(slot.approval_deadline);
    const now = new Date();
    const diff = deadline.getTime() - now.getTime();
    if (diff <= 0) return 0;
    return Math.floor(diff / 60000);
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <div>
            <Skeleton className="h-8 w-48 mb-2" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-[600px]" />
          <Skeleton className="h-[600px]" />
        </div>
      </div>
    );
  }

  if (error || !slot) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
        <h2 className="text-xl font-semibold mb-2">Failed to load slot</h2>
        <p className="text-slate-500 mb-4">{error?.message || 'Slot not found'}</p>
        <div className="flex gap-4">
          <Button variant="outline" asChild>
            <Link href="/content-queue">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Queue
            </Link>
          </Button>
          <Button onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  // Filter to show only unique options by label (keep the latest one)
  const allOptions = slot.options || [];
  const uniqueOptionsMap = new Map<string, typeof allOptions[0]>();
  allOptions.forEach((opt) => {
    const existing = uniqueOptionsMap.get(opt.option_label);
    if (!existing || new Date(opt.created_at) > new Date(existing.created_at)) {
      uniqueOptionsMap.set(opt.option_label, opt);
    }
  });
  const options = Array.from(uniqueOptionsMap.values()).sort((a, b) =>
    a.option_label.localeCompare(b.option_label)
  );
  const selectedOption = options.find((o) => o.is_selected);
  const minutesUntilDeadline = getMinutesUntilDeadline();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/content-queue">
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{slot.scheduled_time} Slot</h1>
              <Badge variant="secondary">
                {slot.content_type === 'real_estate' ? 'Real Estate' : 'Dubai Trending'}
              </Badge>
              <div className={`h-3 w-3 rounded-full ${getStatusColor(slot.status)}`} />
              <span className="text-slate-600 capitalize">{slot.status.replace('_', ' ')}</span>
            </div>
            <p className="text-slate-500">
              {new Date(slot.scheduled_at).toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {minutesUntilDeadline !== null && slot.status === 'options_ready' && (
            <Badge variant={minutesUntilDeadline <= 30 ? 'destructive' : 'secondary'}>
              <Clock className="mr-1 h-3 w-3" />
              {minutesUntilDeadline}m until auto-select
            </Badge>
          )}

          {(slot.status === 'options_ready' || slot.status === 'approved' || slot.status === 'failed') && (
            <Button variant="outline" onClick={handleRegenerate} disabled={regenerateMutation.isPending}>
              {regenerateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Regenerate
            </Button>
          )}

          {slot.status === 'approved' && (
            <Button onClick={() => setPublishDialogOpen(true)} disabled={publishMutation.isPending}>
              {publishMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Publish Now
            </Button>
          )}
        </div>
      </div>

      {/* Status Messages */}
      {slot.status === 'published' && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="flex items-center gap-4 pt-6">
            <CheckCircle2 className="h-8 w-8 text-green-600" />
            <div>
              <h3 className="font-semibold text-green-800">Published Successfully</h3>
              <p className="text-green-700">
                This post was published to Telegram on{' '}
                {new Date(slot.updated_at).toLocaleString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: 'numeric',
                  minute: '2-digit',
                })}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {(slot.status === 'generating' || isRegenerating) && (
        <Card className="border-purple-200 bg-purple-50">
          <CardContent className="flex items-center gap-4 pt-6">
            <Loader2 className="h-8 w-8 text-purple-600 animate-spin" />
            <div>
              <h3 className="font-semibold text-purple-800">Generating Content</h3>
              <p className="text-purple-700">AI is generating post options. This may take a minute...</p>
            </div>
          </CardContent>
        </Card>
      )}

      {slot.status === 'failed' && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-4 pt-6">
            <AlertCircle className="h-8 w-8 text-red-600" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-800">Generation Failed</h3>
              <p className="text-red-700">Content generation failed. Try regenerating the content.</p>
            </div>
            <Button variant="outline" onClick={handleRegenerate} disabled={regenerateMutation.isPending}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Options Grid */}
      {options.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {options.map((option) => (
            <Card
              key={option.id}
              className={`relative ${
                option.is_selected ? 'ring-2 ring-blue-500 border-blue-500' : ''
              }`}
            >
              {option.is_selected && (
                <div className="absolute -top-3 left-4 bg-blue-500 text-white px-3 py-1 rounded-full text-sm font-medium flex items-center gap-1">
                  <Check className="h-4 w-4" />
                  Selected
                </div>
              )}

              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Option {option.option_label}</span>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">
                      Score: {(option.ai_quality_score * 100).toFixed(0)}%
                    </Badge>
                    {option.is_edited && (
                      <Badge variant="secondary">Edited</Badge>
                    )}
                  </div>
                </CardTitle>
              </CardHeader>

              <CardContent className="space-y-3 p-4">
                {/* Image Preview - smaller */}
                {(option.image_data || option.image_url) ? (
                  <div className="relative aspect-[16/9] max-h-40 rounded-lg overflow-hidden bg-slate-100">
                    <img
                      src={option.image_data
                        ? `data:image/png;base64,${option.image_data}`
                        : option.image_url || ''}
                      alt={`Option ${option.option_label}`}
                      className="w-full h-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="h-24 rounded-lg bg-slate-100 flex items-center justify-center">
                    <div className="text-center text-slate-400">
                      <ImageIcon className="h-8 w-8 mx-auto mb-1" />
                      <p className="text-xs">No image</p>
                    </div>
                  </div>
                )}

                {/* Russian Content Only */}
                <div className="space-y-2">
                  <h4 className="font-semibold text-base leading-tight">{option.title_ru}</h4>
                  <p className="text-sm text-slate-600 whitespace-pre-wrap line-clamp-6">{option.body_ru}</p>
                </div>

                {/* Actions */}
                <div className="flex gap-2 pt-3 border-t">
                  {slot.status === 'options_ready' && (
                    <>
                      <Button
                        className="flex-1"
                        onClick={() => handleSelectOption(option.id)}
                        disabled={selectMutation.isPending}
                      >
                        {selectMutation.isPending ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Check className="mr-2 h-4 w-4" />
                        )}
                        Select This Option
                      </Button>
                      <Button variant="outline" onClick={() => handleEditOption(option)}>
                        <Edit3 className="h-4 w-4" />
                      </Button>
                    </>
                  )}

                  {(slot.status === 'approved' || slot.status === 'published') && option.is_selected && (
                    <Button variant="outline" className="flex-1" onClick={() => handleEditOption(option)}>
                      <Edit3 className="mr-2 h-4 w-4" />
                      Edit Content
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-slate-500">
            <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <h3 className="text-lg font-medium mb-2">No options available</h3>
            <p>Content options will appear here once generated.</p>
          </CardContent>
        </Card>
      )}

      {/* Edit Dialog - Russian Only */}
      <Dialog open={!!editingOption} onOpenChange={() => setEditingOption(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Option {editingOption?.option_label}</DialogTitle>
            <DialogDescription>
              Make changes to the post content.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title_ru">Title</Label>
              <Input
                id="title_ru"
                value={editForm.title_ru}
                onChange={(e) => setEditForm({ ...editForm, title_ru: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="body_ru">Body</Label>
              <Textarea
                id="body_ru"
                value={editForm.body_ru}
                onChange={(e) => setEditForm({ ...editForm, body_ru: e.target.value })}
                rows={10}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingOption(null)}>
              Cancel
            </Button>
            <Button onClick={handleSaveEdit} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Publish Confirmation Dialog */}
      <Dialog open={publishDialogOpen} onOpenChange={setPublishDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Publish to Telegram</DialogTitle>
            <DialogDescription>
              This will publish the selected post to your Telegram channel. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>

          {selectedOption && (
            <div className="py-4">
              <div className="rounded-lg border p-4 space-y-2">
                <h4 className="font-semibold">{selectedOption.title_ru}</h4>
                <p className="text-sm text-slate-600 line-clamp-3">{selectedOption.body_ru}</p>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setPublishDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handlePublish} disabled={publishMutation.isPending}>
              {publishMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Publish Now
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
