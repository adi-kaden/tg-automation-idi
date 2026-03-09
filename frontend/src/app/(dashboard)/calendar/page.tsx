'use client';

import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Circle, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useContentSlots } from '@/hooks/use-api';
import type { ContentSlot } from '@/types';

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function getStatusColor(status: string) {
  switch (status) {
    case 'published':
      return 'fill-green-500 text-green-500';
    case 'approved':
    case 'options_ready':
      return 'fill-blue-500 text-blue-500';
    case 'failed':
      return 'fill-red-500 text-red-500';
    default: // pending, generating, skipped
      return 'fill-slate-300 text-slate-300';
  }
}

function formatContentType(type: string) {
  return type === 'real_estate' ? 'real_estate' : 'trending';
}

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState(new Date());

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Compute date range for API query
  const dateFrom = `${year}-${String(month + 1).padStart(2, '0')}-01`;
  const dateTo = `${year}-${String(month + 1).padStart(2, '0')}-${String(daysInMonth).padStart(2, '0')}`;

  const { data: slots, isLoading } = useContentSlots({ date_from: dateFrom, date_to: dateTo });

  // Group slots by scheduled_date
  const slotsByDate = useMemo(() => {
    const map = new Map<number, ContentSlot[]>();
    if (!slots) return map;
    for (const slot of slots) {
      const date = new Date(slot.scheduled_date + 'T00:00:00');
      const day = date.getDate();
      const slotMonth = date.getMonth();
      const slotYear = date.getFullYear();
      // Only include slots that match the displayed month
      if (slotMonth === month && slotYear === year) {
        if (!map.has(day)) map.set(day, []);
        map.get(day)!.push(slot);
      }
    }
    // Sort each day's slots by slot_number
    for (const [, daySlots] of map) {
      daySlots.sort((a, b) => a.slot_number - b.slot_number);
    }
    return map;
  }, [slots, month, year]);

  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const today = new Date();
  const isToday = (day: number) =>
    day === today.getDate() &&
    month === today.getMonth() &&
    year === today.getFullYear();

  const days: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) {
    days.push(null);
  }
  for (let i = 1; i <= daysInMonth; i++) {
    days.push(i);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="outline" size="icon" onClick={prevMonth}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-xl font-semibold min-w-[200px] text-center">
                {MONTHS[month]} {year}
              </span>
              <Button variant="outline" size="icon" onClick={nextMonth}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-1">
                <Circle className="h-3 w-3 fill-green-500 text-green-500" />
                <span>Published</span>
              </div>
              <div className="flex items-center gap-1">
                <Circle className="h-3 w-3 fill-blue-500 text-blue-500" />
                <span>Ready / Approved</span>
              </div>
              <div className="flex items-center gap-1">
                <Circle className="h-3 w-3 fill-red-500 text-red-500" />
                <span>Failed</span>
              </div>
              <div className="flex items-center gap-1">
                <Circle className="h-3 w-3 fill-slate-300 text-slate-300" />
                <span>Pending</span>
              </div>
              {isLoading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-1">
            {/* Header */}
            {DAYS.map((day) => (
              <div
                key={day}
                className="p-2 text-center text-sm font-medium text-slate-500"
              >
                {day}
              </div>
            ))}

            {/* Days */}
            {days.map((day, index) => {
              const daySlots = day ? slotsByDate.get(day) || [] : [];

              return (
                <div
                  key={index}
                  className={`min-h-[120px] border rounded-lg p-2 ${
                    day === null
                      ? 'bg-slate-50'
                      : isToday(day)
                      ? 'bg-indigo-50 border-indigo-200'
                      : 'hover:bg-slate-50'
                  }`}
                >
                  {day !== null && (
                    <>
                      <div className={`text-sm font-medium mb-2 ${isToday(day) ? 'text-indigo-600' : ''}`}>
                        {day}
                        {isToday(day) && (
                          <Badge variant="secondary" className="ml-2 text-xs">Today</Badge>
                        )}
                      </div>
                      {isLoading ? (
                        <div className="space-y-1">
                          <Skeleton className="h-3 w-16" />
                          <Skeleton className="h-3 w-14" />
                          <Skeleton className="h-3 w-16" />
                        </div>
                      ) : (
                        <div className="space-y-1">
                          {daySlots.slice(0, 3).map((slot) => (
                            <div
                              key={slot.id}
                              className="flex items-center gap-1 text-xs"
                            >
                              <Circle className={`h-2 w-2 ${getStatusColor(slot.status)}`} />
                              <span className="text-slate-600">{slot.scheduled_time}</span>
                            </div>
                          ))}
                          {daySlots.length > 3 && (
                            <div className="text-xs text-slate-400">
                              +{daySlots.length - 3} more
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
