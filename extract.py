"""
FuckingFast direct-link extractor.

Takes one or more fuckingfast.co share links and returns the real
dl.fuckingfast.co direct download URL for each.

Uses Playwright to get past Cloudflare, then clicks the DOWNLOAD button
and intercepts the htmx POST to /f/{id}/go — the server responds with
an HX-Redirect header pointing to the direct link.

Usage:
    python extract.py <url> [<url> ...]
    python extract.py -f links.txt          # one URL per line
    python extract.py -f urls.txt -o download_links.txt

With -o, each link is written as soon as it is found, and a
<output>.map.txt file pairs every source URL with its direct link
(or FAILED).

NOTE: runs a VISIBLE (headed) browser by default. The site's Cloudflare
bot protection refuses to hand back the direct link to a headless browser,
so headed mode is required for this to work reliably.
"""

import argparse
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


def wait_for_real_page(page, timeout_s: int = 45) -> bool:
    """Wait until Cloudflare clears and the real page is served."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        title = page.title()
        # Cloudflare challenge pages have "Just a moment..." as the title.
        if title and title != "Just a moment...":
            return True
        time.sleep(1)
    return False


def get_direct_link(page, url: str, timeout_s: int = 60) -> str | None:
    """Navigate to a share URL, click DOWNLOAD, and grab the direct link."""

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)

        if not wait_for_real_page(page, timeout_s=45):
            print("    Cloudflare did not clear.", file=sys.stderr)
            return None

        # Find the DOWNLOAD button (the htmx <a> element).
        download_btn = page.query_selector("a.link-button, a[hx-post*='/go']")
        if not download_btn:
            print("    DOWNLOAD button not found on page.", file=sys.stderr)
            return None

        # First click opens an ad tab — click and close it.
        try:
            download_btn.click()
        except Exception:
            pass  # The ad navigation may destroy the context briefly.
        time.sleep(2)

        # Close any new tabs/popups that the ad opened.
        all_pages = page.context.pages
        for p in all_pages:
            if p != page:
                p.close()

        # Re-query the button (DOM might have changed).
        download_btn = page.query_selector("a.link-button, a[hx-post*='/go']")
        if not download_btn:
            print("    DOWNLOAD button gone after first click.", file=sys.stderr)
            return None

        # Second click triggers the real /go POST with the HX-Redirect.
        with page.expect_response(
            lambda r: r.url.endswith("/go"), timeout=15000
        ) as resp_info:
            download_btn.click()

        response = resp_info.value
        headers = response.all_headers()
        redir = headers.get("hx-redirect") or headers.get("HX-Redirect")
        if redir:
            return redir

        print("    /go responded but no HX-Redirect header.", file=sys.stderr)
        return None

    except PWTimeout:
        print("    Timed out (page load or /go response).", file=sys.stderr)
        return None
    except Exception as e:
        print(f"    Error: {e}", file=sys.stderr)
        return None


def run(
    urls: list[str],
    headless: bool = False,
    output: str | None = None,
) -> dict[str, str | None]:
    results: dict[str, str | None] = {}

    # Open the output file up front and flush after every link, so a long
    # batch isn't lost if the browser crashes partway through.
    out_fh = open(output, "w", encoding="utf-8") if output else None
    map_fh = open(output + ".map.txt", "w", encoding="utf-8") if output else None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )

        # htmx will try to navigate to the dl.fuckingfast.co URL after the POST.
        # We only want the URL, so abort that navigation (we've already captured
        # the link from the HX-Redirect header by the time this fires).
        context.route(
            "https://dl.fuckingfast.co/**", lambda route: route.abort()
        )

        page = context.new_page()

        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {url}", file=sys.stderr)

            # Retry up to 2 extra times on failure, with increasing delay.
            link = None
            for attempt in range(3):
                if attempt > 0:
                    wait = 5 * attempt
                    print(f"    retry #{attempt} after {wait}s ...", file=sys.stderr)
                    time.sleep(wait)
                link = get_direct_link(page, url)
                if link:
                    break

            results[url] = link

            if link:
                print(f"    -> {link}", file=sys.stderr)
                if out_fh:
                    out_fh.write(link + "\n")
                    out_fh.flush()
            else:
                print("    -> FAILED (all retries exhausted)", file=sys.stderr)

            if map_fh:
                map_fh.write(f"{url}\t{link or 'FAILED'}\n")
                map_fh.flush()

            # Small delay between URLs to avoid rate limiting.
            if i < len(urls):
                time.sleep(2)

        browser.close()

    if out_fh:
        out_fh.close()
    if map_fh:
        map_fh.close()

    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Extract fuckingfast.co direct download links."
    )
    ap.add_argument("urls", nargs="*", help="One or more fuckingfast.co share URLs.")
    ap.add_argument("-f", "--file", help="Read URLs from a file (one per line).")
    ap.add_argument("-o", "--output", help="Write resulting direct links to this file.")
    ap.add_argument(
        "--headless",
        action="store_true",
        help=(
            "Run without a visible browser window. NOTE: the site's bot "
            "protection usually refuses the direct link in headless mode, so "
            "this often fails. Default is headed (visible) because it works."
        ),
    )
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    urls: list[str] = list(args.urls)
    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            urls.extend(line.strip() for line in fh if line.strip())

    if not urls:
        print(
            "No URLs provided. Pass URLs as arguments or use -f links.txt.",
            file=sys.stderr,
        )
        return 2

    results = run(urls, headless=args.headless, output=args.output)

    direct = [link for link in results.values() if link]
    failed = len(urls) - len(direct)

    if args.output:
        print(
            f"Wrote {len(direct)} link(s) to {args.output} "
            f"({failed} failed). Source->link map: {args.output}.map.txt",
            file=sys.stderr,
        )
    else:
        for link in direct:
            print(link)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
