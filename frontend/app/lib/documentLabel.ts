import type { GraphNode } from "./types";

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function looksLikeGraphId(value?: string): boolean {
  if (!value) return false;
  return /^\d+:[a-f0-9-]+:\d+$/i.test(value.trim());
}

export function resolveDocumentDisplayName(
  fileName?: string | null,
  title?: string | null,
  fallback?: string | null
): string {
  return fileName?.trim() || title?.trim() || fallback?.trim() || "Untitled document";
}

export function resolveNodeDisplayName(node: GraphNode): string {
  const props = node.properties || {};
  const fileName = asString(props.file_name) || asString(props.saved_file_name);
  const title = asString(props.title) || asString(props.document_title);
  const graphDisplay = asString(node.display_name);

  if (node.label === "Document") {
    return resolveDocumentDisplayName(fileName, title, graphDisplay || node.id);
  }

  if (graphDisplay && !looksLikeGraphId(graphDisplay)) {
    return graphDisplay;
  }

  return title || fileName || graphDisplay || node.id;
}
