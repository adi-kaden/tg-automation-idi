'use client';

import { useState } from 'react';
import { Save, Bell, Clock, Zap, Shield, Globe, Loader2, CheckCircle2, XCircle, Send } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api';
import { toast } from 'sonner';

export default function SettingsPage() {
  const [isSaving, setIsSaving] = useState(false);
  const [notificationStatus, setNotificationStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [notificationMessage, setNotificationMessage] = useState('');
  const [sendingTestType, setSendingTestType] = useState<string | null>(null);

  const handleSave = () => {
    setIsSaving(true);
    setTimeout(() => setIsSaving(false), 1000);
  };

  const handleTestNotification = async () => {
    setNotificationStatus('testing');
    try {
      const result = await api.notifications.testConnection();
      if (result.success) {
        setNotificationStatus('success');
        setNotificationMessage(result.message);
        toast.success('Notification system connected!');
      } else {
        setNotificationStatus('error');
        setNotificationMessage(result.message);
        toast.error(`Connection failed: ${result.message}`);
      }
    } catch (error) {
      setNotificationStatus('error');
      setNotificationMessage(error instanceof Error ? error.message : 'Unknown error');
      toast.error('Failed to test notification connection');
    }
  };

  const handleSendTestNotification = async (type: 'options_ready' | 'auto_selected' | 'publish_success' | 'publish_failed') => {
    setSendingTestType(type);
    try {
      const result = await api.notifications.sendTest(type);
      if (result.success) {
        toast.success(`Test notification sent (ID: ${result.message_id})`);
      } else {
        toast.error(`Failed to send: ${result.error}`);
      }
    } catch (error) {
      toast.error('Failed to send test notification');
    } finally {
      setSendingTestType(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Telegram Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Telegram Configuration
          </CardTitle>
          <CardDescription>
            Configure your Telegram bot and channel settings.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="bot-token">Bot Token</Label>
              <Input
                id="bot-token"
                type="password"
                placeholder="Enter your Telegram bot token"
                defaultValue="••••••••••••••••••••"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="channel-id">Channel ID</Label>
              <Input
                id="channel-id"
                placeholder="@your_channel"
                defaultValue="@idigov_dubai"
              />
            </div>
          </div>
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <div>
              <p className="font-medium">Bot Status</p>
              <p className="text-sm text-slate-500">Connected and authorized</p>
            </div>
            <Badge className="bg-green-500">Connected</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Posting Schedule */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Posting Schedule
          </CardTitle>
          <CardDescription>
            Configure daily posting times (Dubai Time, GMT+4).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[
              { slot: 1, time: '08:00', type: 'Real Estate' },
              { slot: 2, time: '12:00', type: 'Dubai Trending' },
              { slot: 3, time: '16:00', type: 'Real Estate' },
              { slot: 4, time: '20:00', type: 'Dubai Trending' },
              { slot: 5, time: '00:00', type: 'Dubai Trending' },
            ].map((item) => (
              <div
                key={item.slot}
                className="flex items-center gap-4 p-3 border rounded-lg"
              >
                <Badge variant="outline">Slot {item.slot}</Badge>
                <Input
                  type="time"
                  defaultValue={item.time}
                  className="w-32"
                />
                <span className="text-sm text-slate-500 flex-1">{item.type}</span>
                <Switch defaultChecked />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* AI Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            AI Configuration
          </CardTitle>
          <CardDescription>
            Configure AI content generation settings.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="claude-key">Claude API Key</Label>
              <Input
                id="claude-key"
                type="password"
                placeholder="sk-ant-..."
                defaultValue="••••••••••••••••••••"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="gemini-key">Gemini API Key (Images)</Label>
              <Input
                id="gemini-key"
                type="password"
                placeholder="AIza..."
                defaultValue="••••••••••••••••••••"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="options-count">Options per Slot</Label>
            <Input
              id="options-count"
              type="number"
              min="1"
              max="5"
              defaultValue="2"
              className="w-24"
            />
            <p className="text-xs text-slate-500">
              Number of content options to generate for each time slot.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Auto-Selection Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Auto-Selection
          </CardTitle>
          <CardDescription>
            Configure automatic content selection when no human review is made.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Enable Auto-Selection</p>
              <p className="text-sm text-slate-500">
                Automatically select best option if no manual selection is made.
              </p>
            </div>
            <Switch defaultChecked />
          </div>
          <div className="space-y-2">
            <Label htmlFor="auto-select-minutes">Minutes Before Slot</Label>
            <Input
              id="auto-select-minutes"
              type="number"
              min="5"
              max="60"
              defaultValue="30"
              className="w-24"
            />
            <p className="text-xs text-slate-500">
              Auto-select will trigger this many minutes before the scheduled posting time.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            SMM Notifications
          </CardTitle>
          <CardDescription>
            Configure Telegram notifications for the SMM specialist.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* SMM Chat ID */}
          <div className="space-y-2">
            <Label htmlFor="smm-chat-id">SMM Telegram Chat ID</Label>
            <Input
              id="smm-chat-id"
              placeholder="123456789"
              defaultValue=""
            />
            <p className="text-xs text-slate-500">
              Get your chat ID by messaging @userinfobot on Telegram.
            </p>
          </div>

          {/* Connection Test */}
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <div>
              <p className="font-medium">Notification Connection</p>
              <p className="text-sm text-slate-500">
                {notificationStatus === 'success' ? notificationMessage :
                 notificationStatus === 'error' ? notificationMessage :
                 'Test connection to SMM notifications'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {notificationStatus === 'success' && (
                <Badge className="bg-green-500">Connected</Badge>
              )}
              {notificationStatus === 'error' && (
                <Badge variant="destructive">Failed</Badge>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestNotification}
                disabled={notificationStatus === 'testing'}
              >
                {notificationStatus === 'testing' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : notificationStatus === 'success' ? (
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                ) : notificationStatus === 'error' ? (
                  <XCircle className="h-4 w-4 text-red-500" />
                ) : (
                  'Test'
                )}
              </Button>
            </div>
          </div>

          {/* Notification Preferences */}
          <div className="space-y-3 pt-2 border-t">
            <p className="font-medium text-sm text-slate-700">Notification Types</p>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Content Ready for Review</p>
                <p className="text-sm text-slate-500">
                  Notify when new content options are ready.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Switch defaultChecked />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSendTestNotification('options_ready')}
                  disabled={sendingTestType === 'options_ready'}
                >
                  {sendingTestType === 'options_ready' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Auto-Selection Alert</p>
                <p className="text-sm text-slate-500">
                  Notify when AI auto-selects content.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Switch defaultChecked />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSendTestNotification('auto_selected')}
                  disabled={sendingTestType === 'auto_selected'}
                >
                  {sendingTestType === 'auto_selected' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Publish Success</p>
                <p className="text-sm text-slate-500">
                  Notify when a post is published.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Switch />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSendTestNotification('publish_success')}
                  disabled={sendingTestType === 'publish_success'}
                >
                  {sendingTestType === 'publish_success' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Publish Failed</p>
                <p className="text-sm text-slate-500">
                  Alert when publishing fails.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Switch defaultChecked />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSendTestNotification('publish_failed')}
                  disabled={sendingTestType === 'publish_failed'}
                >
                  {sendingTestType === 'publish_failed' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={isSaving}>
          <Save className="h-4 w-4 mr-2" />
          {isSaving ? 'Saving...' : 'Save Settings'}
        </Button>
      </div>
    </div>
  );
}
