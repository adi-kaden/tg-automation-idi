'use client';

// ---------------------------------------------------------------------------
// TelegramCharCounter
//
// Computes the full Telegram message length the same way the backend does
// and displays a character counter with colour-coded warnings.
// ---------------------------------------------------------------------------

interface TelegramCharCounterProps {
  title: string;
  bodyHtml: string;
  hashtags?: string[];
  channelUsername?: string;
}

/**
 * Escape HTML special characters the same way the backend does for the
 * title inside the <b> tag.
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Strip all HTML tags from a string to measure raw visible character count.
 * Telegram counts characters after rendering, not raw HTML length.
 */
function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '');
}

/**
 * Build the full Telegram caption string, matching the backend format:
 *
 *   <b>{title}</b>\n\n{body}\n\n{hashtags}\n\nПодписывайтесь на наш канал: <a href="...">@channel</a>
 */
function buildFullCaption(
  title: string,
  bodyHtml: string,
  hashtags: string[],
  channelUsername: string
): string {
  const parts: string[] = [];

  if (title) {
    parts.push(`<b>${escapeHtml(title)}</b>`);
  }

  if (bodyHtml) {
    parts.push(bodyHtml);
  }

  if (hashtags.length > 0) {
    parts.push(hashtags.join(' '));
  }

  if (channelUsername) {
    const clean = channelUsername.startsWith('@') ? channelUsername : `@${channelUsername}`;
    const url = `https://t.me/${clean.replace('@', '')}`;
    parts.push(`Подписывайтесь на наш канал: <a href="${url}">${clean}</a>`);
  }

  return parts.join('\n\n');
}

/**
 * Count visible characters in a Telegram-HTML string.
 * We strip tags and count the remaining text length.
 */
function countTelegramChars(caption: string): number {
  return stripHtml(caption).length;
}

export function TelegramCharCounter({
  title,
  bodyHtml,
  hashtags = [],
  channelUsername = '',
}: TelegramCharCounterProps) {
  const caption = buildFullCaption(title, bodyHtml, hashtags, channelUsername);
  const count = countTelegramChars(caption);
  const limit = 1024;

  const isOk = count < 900;
  const isWarning = count >= 900 && count <= 1000;
  const isError = count > 1000;

  const colorClass = isError
    ? 'text-red-600'
    : isWarning
    ? 'text-amber-600'
    : 'text-slate-500';

  return (
    <div className="flex flex-col gap-1 mt-1">
      <div className={`text-xs font-medium tabular-nums text-right ${colorClass}`}>
        {count} / {limit}
      </div>

      {/* Progress bar */}
      <div className="h-1 w-full rounded-full bg-slate-100 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            isError ? 'bg-red-500' : isWarning ? 'bg-amber-400' : 'bg-green-500'
          }`}
          style={{ width: `${Math.min((count / limit) * 100, 100)}%` }}
        />
      </div>

      {isError && (
        <p className="text-xs text-red-600 mt-0.5">
          Превышен лимит символов для Telegram. Сократите текст на {count - limit} симв.
        </p>
      )}
    </div>
  );
}

export default TelegramCharCounter;
