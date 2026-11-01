# Third-party components

This repository ships prebuilt renderer bundles. Those bundles include third-party
libraries, and those libraries keep their own terms regardless of anything stated about
this project's own code.

| Component | Version | License | Where |
|---|---|---|---|
| three.js | r180 | MIT | bundled inside `static/lattice.js` and `static/renderer3d.js` |
| GSAP | 3.13.0 | GSAP standard license (free for commercial use, with conditions) | bundled inside the same files |
| esbuild | 0.25.11 | MIT | build tool only, not shipped |

## three.js (MIT)

Copyright (c) 2010-2025 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.

## GSAP

GSAP 3.13 ships under the GSAP standard license, free for commercial use, with the
conditions published at https://gsap.com/standard-license. The minified bundles retain
GreenSock's own licence headers at end of file; do not strip them when rebuilding. GSAP's
terms are not MIT and are not affected by anything in this repository.

## Rebuilding

`npm ci && npm run build` regenerates `static/renderer3d.js` with `--legal-comments=eof`.
The lattice bundle is produced by the same tool invocation on `lattice.js`. Any rebuild
must keep those comment banners.
