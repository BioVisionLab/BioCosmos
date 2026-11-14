/**
 * Relay one image from the backend to the browser.
 *
 * The body is streamed rather than read into an ArrayBuffer first: buffering
 * held every image in the Node process's memory and made the browser wait
 * for the whole file before receiving its first byte.
 */
import { NextResponse } from "next/server";

// For a backend that sends no Cache-Control of its own. The backend sets the
// policy per route: a year and immutable for an image addressed by its id, a
// day for a species' representative image, which can change on re-ingestion.
const FALLBACK_CACHE_CONTROL = "public, max-age=86400";

export async function proxyImage(
  imageUri: string,
  request: Request,
): Promise<Response> {
  try {
    // A reader who scrolls past a tile cancels its request; passing the
    // signal stops the backend transfer too.
    const response = await fetch(imageUri, { signal: request.signal });

    if (!response.ok || !response.body) {
      return NextResponse.json(
        { error: `Failed to fetch image: ${response.statusText}` },
        {
          status: response.ok ? 502 : response.status,
          headers: { "Cache-Control": "no-store" },
        },
      );
    }

    // Only these two are forwarded. fetch has already decoded the body, so
    // passing on Content-Encoding or Content-Length could describe bytes
    // the browser never receives.
    return new Response(response.body, {
      headers: {
        "Content-Type": response.headers.get("content-type") || "image/webp",
        "Cache-Control":
          response.headers.get("cache-control") || FALLBACK_CACHE_CONTROL,
      },
    });
  } catch (error) {
    if (request.signal.aborted) return new Response(null, { status: 499 });

    console.error(`Error fetching image ${imageUri}:`, error);

    return NextResponse.json(
      { error: "Failed to fetch image" },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
