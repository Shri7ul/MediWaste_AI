/**
 * @type {import('next').NextConfig}
 *
 * SAME-ORIGIN PROXY TO THE FLASK API — why this exists
 *
 * For a phone browser to grant camera access the page must come from a secure
 * origin, so the exhibition build is served as `https://<lan-ip>:3000`. A page on
 * an `https://` origin is NOT allowed to fetch `http://<lan-ip>:5000`: browsers
 * block that as active mixed content, and no amount of frontend code can opt out
 * of it. So instead of the browser talking to Flask directly, the browser talks
 * HTTPS to Next.js and Next.js talks plain HTTP to Flask.
 *
 * Consequences, all of them deliberate:
 *  - Flask is untouched and stays plain HTTP. No second certificate, and only
 *    ONE origin has to be trusted by the judge's phone.
 *  - CORS stops being involved at all, because the browser now sees same-origin
 *    requests. The backend's existing CORS configuration is left as it is.
 *  - `BACKEND_ORIGIN` is read on the server only and defaults to loopback — the
 *    Next.js server and Flask run on the same laptop — so no LAN IP is baked
 *    into the application.
 *
 * This rewrite is inert unless the client is pointed at it with
 * `NEXT_PUBLIC_API_BASE_URL=/backend`. With that unset, `src/lib/api/client.ts`
 * keeps deriving the API origin from the served page exactly as before.
 */
const BACKEND_ORIGIN = (process.env.BACKEND_ORIGIN || 'http://127.0.0.1:5000').trim().replace(/\/+$/, '')

const nextConfig = {
  async rewrites() {
    return [{ source: '/backend/:path*', destination: `${BACKEND_ORIGIN}/:path*` }]
  },
}

export default nextConfig
