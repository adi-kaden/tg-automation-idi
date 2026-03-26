'use client';

import { useState, useEffect } from 'react';
import { Sparkles, Save, Play, RotateCcw, Check, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  usePromptGlobalConfig,
  usePromptSlotOverrides,
  useUpdateGlobalConfig,
  useSetSlotOverride,
  useDeleteSlotOverride,
  useTestGenerate,
} from '@/hooks/use-api';
import type { PromptConfig, PromptConfigUpdate, TestGenerateResponse } from '@/types';

const TONE_OPTIONS = ['professional', 'exciting', 'analytical', 'informative', 'urgent'];
const VOICE_PRESET_OPTIONS = [
  { value: 'professional', label: 'Professional', desc: 'Measured, authoritative, industry terminology' },
  { value: 'punchy', label: 'Punchy / Tabloid', desc: 'Short sentences, bold stats, Mash-style energy' },
  { value: 'analytical', label: 'Analytical', desc: 'Data-first, numbers lead, comparative analysis' },
];
const ASPECT_RATIO_OPTIONS = ['16:9', '1:1', '9:16'];
const SLOT_INFO = [
  { number: 1, time: '08:00', type: 'Real Estate' },
  { number: 2, time: '12:00', type: 'Dubai Trending' },
  { number: 3, time: '16:00', type: 'Real Estate' },
  { number: 4, time: '20:00', type: 'Dubai Trending' },
  { number: 5, time: '00:00', type: 'Dubai Trending' },
];
const TEMPLATE_VARIABLES = [
  { name: '{{articles}}', desc: 'Formatted article list (title, summary, URL)' },
  { name: '{{content_type}}', desc: '"real_estate" or "general_dubai"' },
  { name: '{{category}}', desc: 'Specific category string' },
  { name: '{{tone}}', desc: 'Tone from config' },
  { name: '{{max_length}}', desc: 'Max length from config' },
  { name: '{{guidance}}', desc: 'Content type guidance text' },
];

function PromptForm({
  config,
  onSave,
  onTestGenerate,
  isSaving,
  isTesting,
  testResult,
  slotNumber,
}: {
  config: PromptConfig | null;
  onSave: (data: PromptConfigUpdate) => void;
  onTestGenerate: (data: PromptConfigUpdate) => void;
  isSaving: boolean;
  isTesting: boolean;
  testResult: TestGenerateResponse | null;
  slotNumber?: number;
}) {
  const [systemPrompt, setSystemPrompt] = useState('');
  const [generationPrompt, setGenerationPrompt] = useState('');
  const [tone, setTone] = useState('professional');
  const [voicePreset, setVoicePreset] = useState('professional');
  const [maxLength, setMaxLength] = useState(1500);
  const [imageAspectRatio, setImageAspectRatio] = useState('16:9');

  useEffect(() => {
    if (config) {
      setSystemPrompt(config.system_prompt);
      setGenerationPrompt(config.generation_prompt);
      setTone(config.tone);
      setVoicePreset(config.voice_preset || 'professional');
      setMaxLength(config.max_length_chars);
      setImageAspectRatio(config.image_aspect_ratio);
    }
  }, [config]);

  const getFormData = (): PromptConfigUpdate => ({
    system_prompt: systemPrompt,
    generation_prompt: generationPrompt,
    tone,
    voice_preset: voicePreset,
    max_length_chars: maxLength,
    image_aspect_ratio: imageAspectRatio,
  });

  return (
    <div className="space-y-6">
      {/* Content Generation (Claude) */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
          Content Generation (Claude)
        </h3>

        {/* Voice Preset */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Voice Preset</label>
          <div className="grid grid-cols-3 gap-3">
            {VOICE_PRESET_OPTIONS.map((vp) => (
              <button
                key={vp.value}
                type="button"
                onClick={() => setVoicePreset(vp.value)}
                className={`rounded-lg border-2 p-3 text-left transition-colors ${
                  voicePreset === vp.value
                    ? 'border-indigo-500 bg-indigo-50'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <p className="text-sm font-medium">{vp.label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{vp.desc}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Tone</label>
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {TONE_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Max Length (chars)
            </label>
            <input
              type="number"
              value={maxLength}
              onChange={(e) => setMaxLength(Number(e.target.value))}
              min={200}
              max={5000}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">System Prompt</label>
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={6}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Generation Prompt Template
          </label>
          <textarea
            value={generationPrompt}
            onChange={(e) => setGenerationPrompt(e.target.value)}
            rows={12}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <div className="mt-2 p-3 bg-slate-50 rounded-lg">
            <p className="text-xs font-medium text-slate-500 mb-2">Available variables:</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
              {TEMPLATE_VARIABLES.map((v) => (
                <div key={v.name} className="flex items-start gap-2 text-xs">
                  <code className="bg-white px-1.5 py-0.5 rounded border text-indigo-600 shrink-0">
                    {v.name}
                  </code>
                  <span className="text-slate-500">{v.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Image Generation (Imagen) */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
          Image Generation (Imagen)
        </h3>

        <p className="text-xs text-slate-500">
          Image style is automatically selected by Claude based on post content. Six visual styles are available: conceptual photography, architectural visualization, editorial still life, abstract artistic, aerial cinematic, and surreal dreamlike.
        </p>

        <div className="max-w-xs">
          <label className="block text-sm font-medium text-slate-700 mb-1">Aspect Ratio</label>
          <select
            value={imageAspectRatio}
            onChange={(e) => setImageAspectRatio(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {ASPECT_RATIO_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2 border-t">
        <Button
          onClick={() => onTestGenerate(getFormData())}
          disabled={isTesting}
          variant="outline"
        >
          {isTesting ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Play className="h-4 w-4 mr-2" />
          )}
          {isTesting ? 'Generating...' : 'Test Generate'}
        </Button>
        <Button onClick={() => onSave(getFormData())} disabled={isSaving}>
          {isSaving ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Save
        </Button>
      </div>

      {/* Test Result Preview */}
      {testResult && (
        <div className="border rounded-lg p-4 bg-slate-50 space-y-3">
          <h4 className="text-sm font-semibold flex items-center gap-2 flex-wrap">
            <Check className="h-4 w-4 text-green-500" />
            Test Generation Preview
            <Badge variant="outline">{testResult.articles_used} articles used</Badge>
            <Badge variant="secondary">
              Score: {(testResult.quality_score * 100).toFixed(0)}%
            </Badge>
            {testResult.image_style && (
              <Badge variant="outline" className="text-violet-600 border-violet-300">
                {testResult.image_style.replace(/_/g, ' ')}
              </Badge>
            )}
          </h4>
          <div>
            <p className="text-xs text-slate-500 mb-1">Title</p>
            <p className="font-medium">{testResult.title_ru}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Body</p>
            <div
              className="text-sm whitespace-pre-wrap [&_b]:font-bold [&_i]:italic [&_blockquote]:border-l-2 [&_blockquote]:border-slate-300 [&_blockquote]:pl-3 [&_blockquote]:text-slate-600"
              dangerouslySetInnerHTML={{ __html: testResult.body_ru }}
            />
          </div>
          {testResult.image_base64 && (
            <div>
              <p className="text-xs text-slate-500 mb-1">Generated Image</p>
              <img
                src={`data:image/png;base64,${testResult.image_base64}`}
                alt="Generated preview"
                className="max-w-md rounded-lg border"
              />
            </div>
          )}
          <div>
            <p className="text-xs text-slate-500 mb-1">Image Prompt</p>
            <p className="text-xs text-slate-600 font-mono">{testResult.image_prompt}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PromptsPage() {
  const [activeTab, setActiveTab] = useState('global');
  const [editingSlot, setEditingSlot] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<TestGenerateResponse | null>(null);
  const [slotTestResult, setSlotTestResult] = useState<TestGenerateResponse | null>(null);

  const { data: globalConfig, isLoading: isLoadingGlobal } = usePromptGlobalConfig();
  const { data: slotOverrides, isLoading: isLoadingSlots } = usePromptSlotOverrides();

  const updateGlobal = useUpdateGlobalConfig();
  const setSlotOverride = useSetSlotOverride();
  const deleteOverride = useDeleteSlotOverride();
  const testGenerate = useTestGenerate();

  const handleSaveGlobal = (data: PromptConfigUpdate) => {
    updateGlobal.mutate(data);
  };

  const handleTestGlobal = (data: PromptConfigUpdate) => {
    setTestResult(null);
    testGenerate.mutate(
      {
        system_prompt: data.system_prompt!,
        generation_prompt: data.generation_prompt!,
        tone: data.tone!,
        voice_preset: data.voice_preset,
        max_length_chars: data.max_length_chars!,
        image_aspect_ratio: data.image_aspect_ratio!,
      },
      { onSuccess: (result) => setTestResult(result) }
    );
  };

  const handleSaveSlot = (slotNumber: number, data: PromptConfigUpdate) => {
    setSlotOverride.mutate({ slotNumber, data });
  };

  const handleTestSlot = (slotNumber: number, data: PromptConfigUpdate) => {
    setSlotTestResult(null);
    testGenerate.mutate(
      {
        system_prompt: data.system_prompt!,
        generation_prompt: data.generation_prompt!,
        tone: data.tone!,
        voice_preset: data.voice_preset,
        max_length_chars: data.max_length_chars!,
        image_aspect_ratio: data.image_aspect_ratio!,
        slot_number: slotNumber,
      },
      { onSuccess: (result) => setSlotTestResult(result) }
    );
  };

  const handleResetSlot = (slotNumber: number) => {
    deleteOverride.mutate(slotNumber);
    setEditingSlot(null);
    setSlotTestResult(null);
  };

  // Find override for a slot
  const getOverrideForSlot = (slotNumber: number) =>
    slotOverrides?.find((s) => s.slot_number === slotNumber);

  if (isLoadingGlobal) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            AI Prompts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="global">Global Config</TabsTrigger>
              <TabsTrigger value="slots">Slot Overrides</TabsTrigger>
            </TabsList>

            {/* Global Config Tab */}
            <TabsContent value="global" className="mt-6">
              <PromptForm
                config={globalConfig ?? null}
                onSave={handleSaveGlobal}
                onTestGenerate={handleTestGlobal}
                isSaving={updateGlobal.isPending}
                isTesting={testGenerate.isPending && activeTab === 'global'}
                testResult={testResult}
              />
            </TabsContent>

            {/* Slot Overrides Tab */}
            <TabsContent value="slots" className="mt-6">
              {isLoadingSlots ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                </div>
              ) : editingSlot ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium">
                        Slot {editingSlot} ({SLOT_INFO[editingSlot - 1].time}{' '}
                        {SLOT_INFO[editingSlot - 1].type})
                      </h3>
                      {getOverrideForSlot(editingSlot)?.has_override && (
                        <Badge>Custom</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {getOverrideForSlot(editingSlot)?.has_override && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleResetSlot(editingSlot)}
                          disabled={deleteOverride.isPending}
                        >
                          <RotateCcw className="h-3 w-3 mr-1" />
                          Reset to Global
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditingSlot(null);
                          setSlotTestResult(null);
                        }}
                      >
                        Back to list
                      </Button>
                    </div>
                  </div>
                  <PromptForm
                    config={
                      getOverrideForSlot(editingSlot)?.config ?? globalConfig ?? null
                    }
                    onSave={(data) => handleSaveSlot(editingSlot, data)}
                    onTestGenerate={(data) => handleTestSlot(editingSlot, data)}
                    isSaving={setSlotOverride.isPending}
                    isTesting={testGenerate.isPending && activeTab === 'slots'}
                    testResult={slotTestResult}
                    slotNumber={editingSlot}
                  />
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-slate-500 mb-4">
                    Click a slot to set a custom prompt override. Slots without overrides
                    use the global config.
                  </p>
                  {SLOT_INFO.map((slot) => {
                    const override = getOverrideForSlot(slot.number);
                    const hasOverride = override?.has_override ?? false;

                    return (
                      <button
                        key={slot.number}
                        onClick={() => setEditingSlot(slot.number)}
                        className="w-full flex items-center justify-between rounded-lg border p-4 hover:bg-slate-50 transition-colors text-left"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 text-sm font-bold">
                            {slot.number}
                          </div>
                          <div>
                            <p className="font-medium text-sm">
                              {slot.time} &mdash; {slot.type}
                            </p>
                            <p className="text-xs text-slate-500">
                              Slot {slot.number}
                            </p>
                          </div>
                        </div>
                        <div>
                          {hasOverride ? (
                            <Badge>Custom</Badge>
                          ) : (
                            <Badge variant="outline" className="text-slate-400">
                              Using Global
                            </Badge>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
