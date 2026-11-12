/** Two letters for a person's badge: first and last word of a full name, or the first two letters. */
export function initialsOf(name: string): string {
  const words = name.split(/\s+/).filter((word) => /^\p{L}/u.test(word));
  const first = words[0] ?? "";
  const last = words.length > 1 ? (words[words.length - 1] ?? "") : "";
  const letters = last ? `${first.charAt(0)}${last.charAt(0)}` : first.slice(0, 2);
  return letters.toLocaleUpperCase() || "?";
}
