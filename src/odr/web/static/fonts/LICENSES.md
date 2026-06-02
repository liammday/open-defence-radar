# Vendored fonts

The console's three typefaces are self-hosted (latin subset, `woff2`) so the app
has no runtime dependency on the Google Fonts CDN. All three are licensed under
the **SIL Open Font License 1.1** (OFL), which permits bundling and redistribution.

| Family | Files | Designer / source | Licence |
|--------|-------|-------------------|---------|
| Instrument Serif | `instrumentserif-*.woff2` | Rodrigo Fuenzalida — https://fonts.google.com/specimen/Instrument+Serif | OFL 1.1 |
| Newsreader | `newsreader-*.woff2` | Production Type — https://fonts.google.com/specimen/Newsreader | OFL 1.1 |
| IBM Plex Mono | `ibmplexmono-*.woff2` | IBM — https://fonts.google.com/specimen/IBM+Plex+Mono | OFL 1.1 |

The `woff2` files were generated from the Google Fonts `css2` API (latin subset);
the `@font-face` declarations live in `../fonts.css`. Full OFL text:
https://openfontlicense.org
