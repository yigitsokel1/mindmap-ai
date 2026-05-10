import { afterEach, describe, expect, it, vi } from "vitest";
import {
  AppError,
  fetchJson,
  stableGraphFilterKey,
  toRenderData,
  toUserMessage,
} from "./api";

// ── toUserMessage ─────────────────────────────────────────────────────────────

describe("toUserMessage", () => {
  it("returns network message for network error", () => {
    expect(toUserMessage(new AppError("x", "network"))).toBe(
      "Network issue. Check your connection and try again."
    );
  });

  it("returns timeout message for timeout error", () => {
    expect(toUserMessage(new AppError("x", "timeout"))).toBe(
      "Request timed out. Please retry."
    );
  });

  it("returns server message for server error", () => {
    expect(toUserMessage(new AppError("x", "server"))).toBe(
      "Backend is currently unavailable. Please try again shortly."
    );
  });

  it("returns not_found message", () => {
    expect(toUserMessage(new AppError("x", "not_found"))).toBe(
      "Requested data was not found."
    );
  });

  it("returns validation message", () => {
    expect(toUserMessage(new AppError("x", "validation"))).toBe(
      "Request could not be processed. Please review your input."
    );
  });

  it("returns partial_data message", () => {
    expect(toUserMessage(new AppError("x", "partial_data"))).toBe(
      "Partial data returned. Some details may be missing."
    );
  });

  it("falls back to error.message for unknown AppError type", () => {
    expect(toUserMessage(new AppError("Custom msg", "unknown"))).toBe(
      "Custom msg"
    );
  });

  it("returns message for plain Error", () => {
    expect(toUserMessage(new Error("oops"))).toBe("oops");
  });

  it("returns fallback for non-Error value", () => {
    expect(toUserMessage("string error")).toBe("Unexpected error occurred.");
  });

  it("returns fallback for null", () => {
    expect(toUserMessage(null)).toBe("Unexpected error occurred.");
  });
});

// ── stableGraphFilterKey ──────────────────────────────────────────────────────

describe("stableGraphFilterKey", () => {
  it("produces same key regardless of node_types order", () => {
    const a = stableGraphFilterKey({ node_types: ["Method", "Concept"] });
    const b = stableGraphFilterKey({ node_types: ["Concept", "Method"] });
    expect(a).toBe(b);
  });

  it("treats undefined document_id and omitted document_id as equal", () => {
    const a = stableGraphFilterKey({});
    const b = stableGraphFilterKey({ document_id: undefined });
    expect(a).toBe(b);
  });

  it("distinguishes different document_ids", () => {
    const a = stableGraphFilterKey({ document_id: "doc-1" });
    const b = stableGraphFilterKey({ document_id: "doc-2" });
    expect(a).not.toBe(b);
  });

  it("treats empty node_types and omitted node_types as equal", () => {
    const a = stableGraphFilterKey({ node_types: [] });
    const b = stableGraphFilterKey({});
    expect(a).toBe(b);
  });
});

// ── toRenderData ──────────────────────────────────────────────────────────────

describe("toRenderData", () => {
  it("maps nodes and edges to nodes and links", () => {
    const result = toRenderData({
      nodes: [{ id: "1" } as never],
      edges: [{ id: "e1" } as never],
      meta: { counts: {}, filters_applied: {} },
    });
    expect(result.nodes).toHaveLength(1);
    expect(result.links).toHaveLength(1);
  });

  it("handles missing nodes and edges gracefully", () => {
    const result = toRenderData({} as never);
    expect(result.nodes).toEqual([]);
    expect(result.links).toEqual([]);
  });

  it("preserves all node entries", () => {
    const nodes = [{ id: "a" }, { id: "b" }, { id: "c" }] as never[];
    const result = toRenderData({ nodes, edges: [], meta: { counts: {}, filters_applied: {} } });
    expect(result.nodes).toHaveLength(3);
  });
});

// ── fetchJson ─────────────────────────────────────────────────────────────────

describe("fetchJson", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: "test" }),
      })
    );
    const result = await fetchJson<{ data: string }>("http://test.local/api");
    expect(result).toEqual({ data: "test" });
  });

  it("throws AppError with server type on 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({ detail: "boom" }),
      })
    );
    await expect(fetchJson("http://test.local/api")).rejects.toMatchObject({
      type: "server",
    });
  });

  it("throws AppError with not_found type on 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({}),
      })
    );
    await expect(fetchJson("http://test.local/api")).rejects.toMatchObject({
      type: "not_found",
    });
  });

  it("throws AppError with validation type on 422", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        statusText: "Unprocessable Entity",
        json: async () => ({}),
      })
    );
    await expect(fetchJson("http://test.local/api")).rejects.toMatchObject({
      type: "validation",
    });
  });

  it("uses detail from error body when available", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Error",
        json: async () => ({ detail: "specific backend error" }),
      })
    );
    await expect(fetchJson("http://test.local/api")).rejects.toMatchObject({
      message: "specific backend error",
    });
  });

  it("throws AppError with timeout type on AbortError", async () => {
    const abortError = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));
    await expect(fetchJson("http://test.local/api")).rejects.toMatchObject({
      type: "timeout",
    });
  });

  it("throws AppError with network type on fetch failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    await expect(fetchJson("http://test.local/api")).rejects.toMatchObject({
      type: "network",
    });
  });

  it("rethrows AppError without wrapping", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({}),
      })
    );
    const error = await fetchJson("http://test.local/api").catch((e) => e);
    expect(error).toBeInstanceOf(AppError);
  });
});
