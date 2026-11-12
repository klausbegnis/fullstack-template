import type { ReactNode } from "react";

export interface EmptyStateProps {
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
}

/**
 * Presents an honest absence (nothing created yet, nothing matches) without inventing data, with
 * an optional `action` such as a link to create the first item. The title is an `h2`, so it sits
 * under the page's own `h1`.
 */
export function EmptyState({ eyebrow, title, description, action }: EmptyStateProps) {
  return (
    <section className="mx-auto max-w-2xl rounded-2xl border border-gray-200 bg-white p-8 shadow-sm sm:p-10">
      {eyebrow ? (
        <p className="text-[0.6875rem] font-bold tracking-[0.14em] text-brand uppercase">
          {eyebrow}
        </p>
      ) : null}
      <h2 className="mt-2 text-2xl font-semibold tracking-tight text-gray-900">{title}</h2>
      <p className="mt-3 max-w-xl text-sm leading-6 text-gray-500">{description}</p>
      {action ? <div className="mt-6">{action}</div> : null}
    </section>
  );
}
