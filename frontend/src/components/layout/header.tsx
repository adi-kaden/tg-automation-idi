'use client';

import { usePathname } from 'next/navigation';
import { ChevronRight, Home } from 'lucide-react';
import Link from 'next/link';

const routeTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/content-queue': 'Content Queue',
  '/calendar': 'Calendar',
  '/posts': 'Published Posts',
  '/scraper': 'Scraper',
  '/scraper/sources': 'Scraper Sources',
  '/analytics': 'Analytics',
  '/prompts': 'AI Prompts',
  '/settings': 'Settings',
};

export function Header() {
  const pathname = usePathname();

  // Build breadcrumb
  const segments = pathname.split('/').filter(Boolean);
  const breadcrumbs = segments.map((segment, index) => {
    const path = '/' + segments.slice(0, index + 1).join('/');
    const title = routeTitles[path] || segment.charAt(0).toUpperCase() + segment.slice(1);
    return { path, title };
  });

  // Get page title
  const pageTitle = routeTitles[pathname] || 'Page';

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b bg-white px-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm">
        <Link
          href="/"
          className="text-slate-500 hover:text-slate-900 transition-colors"
        >
          <Home className="h-4 w-4" />
        </Link>
        {breadcrumbs.map((crumb, index) => (
          <div key={crumb.path} className="flex items-center gap-2">
            <ChevronRight className="h-4 w-4 text-slate-400" />
            {index === breadcrumbs.length - 1 ? (
              <span className="font-medium text-slate-900">{crumb.title}</span>
            ) : (
              <Link
                href={crumb.path}
                className="text-slate-500 hover:text-slate-900 transition-colors"
              >
                {crumb.title}
              </Link>
            )}
          </div>
        ))}
        {breadcrumbs.length === 0 && (
          <>
            <ChevronRight className="h-4 w-4 text-slate-400" />
            <span className="font-medium text-slate-900">Dashboard</span>
          </>
        )}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Right side - could add notifications, etc */}
      <div className="flex items-center gap-4">
        <div className="text-sm text-slate-500">
          Dubai Time: {new Date().toLocaleTimeString('en-US', {
            timeZone: 'Asia/Dubai',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </header>
  );
}
