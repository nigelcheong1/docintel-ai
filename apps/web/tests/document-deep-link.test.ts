import { describe, expect, it } from "vitest";

import { parseInitialChunk, parseInitialPage } from "@/lib/document-deep-link";

describe("document deep links", () => {
  it("parses valid page and chunk query values", () => {
    expect(parseInitialPage("3")).toBe(3);
    expect(parseInitialPage(["4", "5"])).toBe(4);
    expect(parseInitialChunk("chunk-123")).toBe("chunk-123");
    expect(parseInitialChunk(["chunk-456", "chunk-789"])).toBe("chunk-456");
  });

  it("ignores unusable page and chunk query values", () => {
    expect(parseInitialPage("0")).toBeUndefined();
    expect(parseInitialPage("not-a-page")).toBeUndefined();
    expect(parseInitialChunk("   ")).toBeUndefined();
  });
});
