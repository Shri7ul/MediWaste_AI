# Local TLS material for the exhibition

Nothing in this folder is committed except this file. The key and certificate are
generated on the exhibition laptop and are not shared, not reused, and not valid
for anything outside the local network.

Generate them with [mkcert](https://github.com/FiloSottile/mkcert), from the
`frontend` folder, substituting the laptop's current LAN address:

```powershell
mkcert -install
mkcert -key-file certs/lan-key.pem -cert-file certs/lan-cert.pem 192.168.1.14 localhost 127.0.0.1
```

Then `npm run dev:https`, which passes exactly these two paths to Next.js.

Regenerate whenever the laptop's LAN IP changes — a certificate is bound to the
addresses listed when it was created, and the phone will refuse a mismatch.
