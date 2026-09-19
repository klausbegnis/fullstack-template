/**
 * A visually hidden link that becomes visible on focus, letting keyboard
 * and screen-reader users jump past repeated navigation straight to the
 * page content.
 */
export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:shadow-md"
    >
      Skip to main content
    </a>
  );
}
