# MediWaste AI — frontend

Next.js 14 (App Router) operator interface for the MediWaste AI segregation and
compliance assistant. Every decision shown here comes from the Flask backend; the
frontend renders results and records the operator's choice, it never classifies
waste or evaluates compliance itself.

```
Judge's phone ──┐  HTTPS                      HTTP (loopback)
                ├────────> Next.js (:3000) ─────────────────> Flask (:5000)
Exhibition PC ──┘          serves /scan and                   vision → normalization
                           proxies /backend/*                 → policy engine → expected route
                                                              → verification → audit event
```

The phone is not a separate app or a separate pipeline. It loads the same
`/scan` route, calls the same `/analyze` and `/verify` endpoints, and produces
the same audit events as the desktop screen.

## Run it locally

```bash
npm install
npm run dev
# http://localhost:3000  → redirects to /scan
```

## Exhibition mode: HTTPS on the LAN

A phone browser will only hand over the camera on a **secure origin**, so for a
physical-phone demo the frontend has to be served as `https://<laptop-ip>:3000`.
Everything below is local-network only; see [Security boundary](#security-boundary).

Run these on the Windows exhibition laptop, in the `frontend` folder.

**1. Install mkcert.**

```powershell
winget install FiloSottile.mkcert
# or: choco install mkcert   — or download mkcert.exe from the project releases
```

**2. Install the local certificate authority.**

```powershell
mkcert -install
```

This adds mkcert's CA to the Windows trust store, which is what makes the
laptop's own browser accept the certificate without warnings. It does **not**
affect the phone — see [Phone certificate trust](#phone-certificate-trust).

**3. Find the laptop's LAN address and generate a certificate for it.**

```powershell
ipconfig                     # IPv4 Address of the Wi-Fi adapter, e.g. 192.168.1.14
mkcert -key-file certs/lan-key.pem -cert-file certs/lan-cert.pem 192.168.1.14 localhost 127.0.0.1
```

The certificate is bound to the addresses listed here, so regenerate it whenever
the laptop's IP changes. `certs/` is gitignored apart from its README.

**4. Start the frontend in HTTPS LAN mode.**

```powershell
npm run dev:https
```

That script is `next dev -H 0.0.0.0 -p 3000 --experimental-https` with the two
certificate paths above. Passing the key and certificate explicitly matters:
`--experimental-https` on its own tries to fetch a mkcert binary from the
internet to generate one. Windows will ask whether to allow Node.js through the
firewall the first time — allow it on private networks.

**5. Start Flask.**

```powershell
conda activate ml
python app.py
```

Loopback binding is enough, because the Next.js server proxies the API from the
same laptop. If you would rather have the browser reach Flask directly (see
[How requests flow](#how-requests-flow)), start it LAN-bound instead —
`app.py` calls `app.run()` without a `host`, so use
`flask --app app run --host=0.0.0.0 --port=5000`.

**6. CORS.**

In the proxied setup the browser only ever talks to the Next.js origin, so CORS
is not involved and no backend configuration is needed. If you switch to the
direct setup, the frontend origin is now HTTPS, so the root `.env` needs the
**https** origin:

```
CORS_ALLOW_ORIGINS=http://localhost:3000,https://192.168.1.14:3000
```

`app.py` matches these exactly — scheme, host and port all have to agree — and it
reads them at startup, so restart Flask afterwards.

**7. Put the phone on the same Wi-Fi** as the laptop. Guest networks and
"client isolation" on the access point will block phone→laptop traffic even
though both devices show as connected.

**8. Open the app on the phone.** Either scan the QR code shown on the laptop's
`/scan` screen, or type the address:

```
https://192.168.1.14:3000/scan
```

**9. Get the phone to trust the certificate** — see the next section.

**10. Grant camera permission** when the browser asks, after tapping
`Start scan`.

**11. Run the flow:** select a ward → `Start scan` → capture a real item →
expected route → select the bin actually used → `Check compliance` → verdict,
then `Why this route?` and `Start disposal`.

### Phone certificate trust

`mkcert -install` trusts the CA **on the laptop only**. On the phone there are
two options, and they behave differently by browser and Android version — do not
assume either is automatic.

**Option A — accept the warning (fastest).** Chrome for Android shows "Your
connection is not private"; tap `Advanced` → `Proceed to 192.168.1.14 (unsafe)`.
The origin is still `https://`, so the camera prompt normally still appears, even
though Chrome labels the connection "Not secure". This is per-tab and may need
repeating. If the camera stays unavailable after proceeding, use Option B.

**Option B — install the mkcert CA on the phone (no warnings).** Run
`mkcert -CAROOT` on the laptop, copy `rootCA.pem` to the phone, and install it via
Settings → Security → *Encryption & credentials* → *Install a certificate* →
*CA certificate*. Android will warn that a third party may inspect traffic, and
the exact menu path differs between OEMs and Android versions. Chrome for Android
honours user-installed CAs; Firefox for Android uses its own trust store and will
keep rejecting the certificate. Newer Android releases deliberately make
user-CA installation harder, and on a managed/work profile it may be blocked
entirely — in that case use Option A.

Remove the CA from the phone after the exhibition.

## How requests flow

A page served over `https://` is not allowed to `fetch()` `http://<ip>:5000`.
Browsers block that as active mixed content and no frontend code can opt out of
it, so HTTPS mode routes API calls through the Next.js server instead:

```
phone ──https──> https://192.168.1.14:3000/backend/analyze
                        │  rewrite in next.config.mjs
                        └──http──> http://127.0.0.1:5000/analyze
```

`NEXT_PUBLIC_API_BASE_URL=/backend` (in `.env.local`) is what points the client at
the proxy; `BACKEND_ORIGIN` is where the server forwards it. Only one origin has
to be trusted by the phone, Flask keeps its existing plain-HTTP setup, and CORS
drops out of the picture. Neither variable contains a LAN IP.

Leave `NEXT_PUBLIC_API_BASE_URL` empty to go back to the browser calling Flask
directly, in which case `src/lib/api/client.ts` derives the API origin from the
served page — useful over plain HTTP, but under HTTPS it means Flask also has to
be served over TLS (`flask --app app run --cert=... --key=... --host=0.0.0.0`)
and the phone has to trust that certificate too.

## Plain HTTP on the LAN (no camera)

`npm run dev:lan` serves `http://<laptop-ip>:3000`. Everything works except the
live camera: the capture screen says "Camera access isn't available" and offers
`Upload photo`, which opens the phone's camera roll or camera app. Analysis,
expected route, verification, audit event and evidence are the same code path as a
live capture, so this is a legitimate fallback if the certificate setup fails
during judging.

## Configuration

| Variable | Where | Default | Purpose |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | browser | *(unset)* | Absolute backend URL, or `/backend` to use the same-origin proxy. Always wins over derivation. |
| `BACKEND_ORIGIN` | server | `http://127.0.0.1:5000` | Where `/backend/*` is forwarded. Never sent to the browser. |
| `NEXT_PUBLIC_API_PORT` | browser | `5000` | Backend port used only when the browser calls Flask directly. |

Copy `.env.example` to `.env.local`. Values are read at server start, so restart
`npm run dev*` after editing. Nothing here is a secret — every `NEXT_PUBLIC_*`
value is inlined into the browser bundle.

## Troubleshooting

Two diagnostics answer most questions. On the laptop, `curl http://127.0.0.1:5000/health`
proves Flask is up. On the phone, opening `https://192.168.1.14:3000/backend/health`
proves the network path, the certificate and the proxy all work — if that returns
JSON, the app's API calls will work too.

**The phone cannot load the page at all.** Check, in this order: both devices on
the same non-guest Wi-Fi; the IP is still correct (`ipconfig` again after any
reconnect — DHCP reassigns); Windows Firewall is allowing inbound TCP 3000 for
Node.js on private networks. If the first-run firewall prompt was dismissed, add
an inbound rule for port 3000 through Windows Defender Firewall → *Advanced
settings* → *Inbound Rules* → *New Rule*. Do not turn the firewall off.

**Certificate warning that cannot be bypassed, or "hostname mismatch".** The
certificate lists specific addresses. If the laptop's IP changed, regenerate it
with the new one and restart `npm run dev:https`. Reaching the app by a name that
is not in the certificate (a hostname, or a different interface's IP) produces the
same error.

**Camera permission denied.** Tap the padlock or the "Not secure" label in
Chrome's address bar → *Permissions* → *Camera* → allow, then reload. Android also
has a system-level toggle: Settings → Apps → Chrome → Permissions → Camera. A
denied prompt is remembered per site, so re-prompting requires clearing it here.

**Camera still unavailable on an HTTPS page.** Install the CA on the phone
(Option B above) rather than bypassing the warning, and confirm the address bar
really shows `https://`. If another tab or app holds the camera, close it.

**API calls fail but the page loads.** In proxied mode this is almost always
Flask not running, or `BACKEND_ORIGIN` pointing at the wrong port — the browser
console will show 502s on `/backend/*`. In direct mode a CORS error means the
frontend origin is missing from `CORS_ALLOW_ORIGINS`; remember it is now `https://`,
and that the match is exact.

**Backend port 5000 in use.** Something else is bound to it (on Windows,
`netstat -ano | findstr :5000`). Start Flask on another port and set
`BACKEND_ORIGIN` to match.

**"Analysis failed" on the phone but not the laptop.** This is not a phone
problem — it means Flask is running outside the conda `ml` environment and the
vision dependencies cannot be imported.

## Security boundary

This is a local-network exhibition setup, not production TLS. The certificate is
issued by a CA that exists only on the exhibition laptop, there is no
authentication, and the app must not be exposed to the internet or port-forwarded.
Private keys and certificates are gitignored and must never be committed. Remove
the mkcert CA from any phone that had it installed once the demo is over.

## Phone layout notes

`/scan` is the landing route (`/` redirects to it) and is laid out phone-first:
a compact non-sticky header with a horizontally scrollable nav, ward selection
before capture, a near-full-viewport camera with a thumb-reachable shutter, and
one primary action per state. Dashboard, Operations and Events stay reachable
from the same nav. Desktop keeps the wider clinical layout from `lg` up.

The **Scan with your phone** card on `/scan` is desktop-only exhibition
convenience. It builds its QR code from `window.location`, so it always encodes
the origin this browser is genuinely serving from — including the `https://` one —
and when that origin is loopback it draws no code at all and explains why, because
a QR pointing at `localhost` would send the phone to itself. The URL is always
shown as text as well. The encoder is `src/lib/qr.ts` — about 250 lines, no
dependency added.

## Checks

```bash
npx tsc --noEmit
npx next lint
npm run build
```

Note that `next start` has no HTTPS support, so exhibition HTTPS mode runs
`next dev`. Load `/scan`, `/operations`, `/dashboard` and `/events` once before
judging so the dev server has compiled them.




