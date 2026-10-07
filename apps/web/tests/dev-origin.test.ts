// @vitest-environment node
import { IncomingMessage, ServerResponse } from "node:http";
import { Socket } from "node:net";
import { blockCrossSiteDEV } from "next/dist/server/lib/router-utils/block-cross-site-dev";
import { describe, expect, it } from "vitest";

import nextConfig from "../next.config";

function checkDevRequest(headers: IncomingMessage["headers"], url: string) {
  const socket = new Socket();
  const request = new IncomingMessage(socket);
  request.url = url;
  request.headers = headers;
  const response = new ServerResponse(request);

  try {
    const blocked = blockCrossSiteDEV(request, response, nextConfig.allowedDevOrigins, "localhost");
    return { blocked, status: response.statusCode };
  } finally {
    socket.destroy();
  }
}

describe("local development origins", () => {
  it.each(["localhost", "127.0.0.1"])("loads development scripts through %s", (hostname) => {
    const result = checkDevRequest(
      {
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "cross-site",
        referer: `http://${hostname}:3001/documents`,
      },
      "/_next/static/chunks/app.js",
    );

    expect(result).toEqual({ blocked: false, status: 200 });
  });

  it("allows hot reload from the IPv4 loopback address", () => {
    const result = checkDevRequest({ origin: "http://127.0.0.1:3001" }, "/_next/hmr");

    expect(result).toEqual({ blocked: false, status: 200 });
  });

  it("continues blocking development assets from unrelated origins", () => {
    const result = checkDevRequest({ origin: "https://untrusted.example" }, "/_next/hmr");

    expect(result).toEqual({ blocked: true, status: 403 });
  });
});
