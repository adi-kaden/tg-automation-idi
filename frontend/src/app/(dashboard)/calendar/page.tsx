'use client';

import { useState } from 'react';
import { ChevronLeft, ChevronRight, Circle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

interface DaySlot {
  date: number;
  slots: Array<{
    time: string;
    status: 'published' | 'scheduled' | 'pending';
    type: 'real_estate' | 'trending';
  }>;
}

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState(new Date());

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

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

  // Mock slot data
  const getSlotData = (day: number): DaySlot['slots'] => {
    if (day < today.getDate() && month === today.getMonth()) {
      return [
        { time: '08:00', status: 'published', type: 'real_estate' },
        { time: '12:00', status: 'published', type: 'trending' },
        { time: '16:00', status: 'published', type: 'real_estate' },
        { time: '20:00', status: 'published', type: 'trending' },
        { time: '00:00', status: 'published', type: 'trending' },
      ];
    }
    if (day === today.getDate() && month === today.getMonth()) {
      return [
        { time: '08:00', status: 'published', type: 'real_estate' },
        { time: '12:00', status: 'scheduled', type: 'trending' },
        { time: '16:00', status: 'pending', type: 'real_estate' },
        { time: '20:00', status: 'pending', type: 'trending' },
        { time: '00:00', status: 'pending', type: 'trending' },
      ];
    }
    return [
      { time: '08:00', status: 'pending', type: 'real_estate' },
      { time: '12:00', status: 'pending', type: 'trending' },
      { time: '16:00', status: 'pending', type: 'real_estate' },
      { time: '20:00', status: 'pending', type: 'trending' },
      { time: '00:00', status: 'pending', type: 'trending' },
    ];
  };

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
                <span>Scheduled</span>
              </div>
              <div className="flex items-center gap-1">
                <Circle className="h-3 w-3 fill-slate-300 text-slate-300" />
                <span>Pending</span>
              </div>
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
            {days.map((day, index) => (
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
                    <div className="space-y-1">
                      {getSlotData(day).slice(0, 3).map((slot, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-1 text-xs"
                        >
                          <Circle
                            className={`h-2 w-2 ${
                              slot.status === 'published'
                                ? 'fill-green-500 text-green-500'
                                : slot.status === 'scheduled'
                                ? 'fill-blue-500 text-blue-500'
                                : 'fill-slate-300 text-slate-300'
                            }`}
                          />
                          <span className="text-slate-600">{slot.time}</span>
                        </div>
                      ))}
                      {getSlotData(day).length > 3 && (
                        <div className="text-xs text-slate-400">
                          +{getSlotData(day).length - 3} more
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
