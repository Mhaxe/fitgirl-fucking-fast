# fuckingfast-link-extractor

Turn `fuckingfast.co` share links into direct `dl.fuckingfast.co` download links, in bulk.

A share link like

```
https://fuckingfast.co/td7k3c32mmwz#FIFA_22_--_fitgirl-repacks.site_--_.part01.rar
```

becomes a direct link like

```
https://dl.fuckingfast.co/dl/arJW5ZSRBXaUnQMWAuEVOZYcq8PJU_...
```

You can then paste the direct links into any download manager (aria2c, IDM, JDownloader, wget).

## How it works

The site sits behind Cloudflare, so plain `requests` or `curl` get a 403. This tool drives a real Chromium browser with [Playwright](https://playwright.dev/python/):

1. Opens the share page and waits for Cloudflare to clear.
2. Clicks **DOWNLOAD** once (this only opens an ad, which the script closes).
3. Clicks **DOWNLOAD** a second time. The page sends `POST /f/{id}/go`.
4. Reads the `HX-Redirect` header of that response. That header is the direct link.

The browser never actually downloads the file.

## Requirements

- Python 3.10 or newer
- Windows, macOS, or Linux
- A display, because the browser runs visibly (see Notes)

## Setup

```powershell
# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate         # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download the Chromium build Playwright uses
playwright install chromium
```

## Usage

1. Put your share links in a text file, one per line. See `urls.example.txt`:

   ```
   https://fuckingfast.co/xxxxxxxxxxxx#Example_Game_--_.part01.rar
   https://fuckingfast.co/yyyyyyyyyyyy#Example_Game_--_.part02.rar
   ```

2. Run the extractor:

   ```powershell
   python extract.py -f urls.txt -o download_links.txt
   ```

3. A Chromium window opens and works through the list. Leave it alone until it finishes.

You get two files:

| File | Contents |
| --- | --- |
| `download_links.txt` | One direct link per line, ready for a download manager |
| `download_links.txt.map.txt` | `source URL<TAB>direct link` for every input, or `FAILED` |

Links are written as soon as they are found, so a crash does not lose earlier results.

### Other ways to run it

```powershell
# One or more URLs directly, printed to the terminal
python extract.py "https://fuckingfast.co/td7k3c32mmwz"

# Mix a file and extra URLs
python extract.py -f urls.txt "https://fuckingfast.co/td7k3c32mmwz" -o out.txt
```

### Options

| Option | Description |
| --- | --- |
| `urls` | One or more share URLs |
| `-f`, `--file` | Read URLs from a file, one per line |
| `-o`, `--output` | Write direct links to this file (also writes `<file>.map.txt`) |
| `--headless` | Hide the browser window. Usually fails, see Notes |

The exit code is `0` if every URL resolved and `1` if any failed.

### Downloading the links

```bash
aria2c -i download_links.txt -d ./downloads -j 3 -x 5
```

## Notes

- **Headed mode is the default on purpose.** In headless mode Cloudflare tends to answer the `/go` request without the redirect header, so extraction fails.
- **Direct links expire.** Download soon after extracting. If a link stops working, run the extractor again.
- **Retries.** Each URL is tried up to 3 times with a short backoff, and there is a 2 second pause between URLs to avoid rate limiting. On some URLs the first attempt logs `Execution context was destroyed`. This is the ad navigation and the retry handles it.
- **Keep your lists private.** `.gitignore` excludes all `.txt` files except `requirements.txt` and `urls.example.txt`.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Executable doesn't exist ... chromium` | Run `playwright install chromium` inside the venv |
| `Cloudflare did not clear` | Run again, and do not minimise the browser window |
| Many `FAILED` lines | Rerun on only the failed URLs from the `.map.txt` file |
| `/go responded but no HX-Redirect header` | You are likely running headless. Remove `--headless` |

## Disclaimer

For personal use. Respect the terms of service of the sites you use and the copyright of what you download.
