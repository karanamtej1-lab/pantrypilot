# Third-party notices

PantryPilot adapts ideas and a small amount of logic from these open-source projects.

## Simplicity / Vane (MIT)

- Source: https://github.com/Blueturboguy07/Simplicity (fork of https://github.com/ItzCrazyKns/Vane)
- Used in: backend/ask.py: the search-planner idea (the AI chooses only *what* to search for; code retrieves, and a failed plan can never add facts), the strict citation-marker parsing rules (CITATION_RUN, ported from src/components/MessageRenderer/citationParser.ts), and the "How I found this" transparency idea. Rewritten in Python for PantryPilot; PantryPilot searches only official sources, not the open web.

```
MIT License

Copyright (c) 2026 ItzCrazyKns

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Data and libraries

- U.S. Census Bureau 2020 ZCTA Gazetteer (public domain): data/zip_centroids.json
- Leaflet (BSD-2-Clause), OpenStreetMap map data (ODbL), jsPDF (MIT): loaded from cdnjs
- Official text in knowledge/: Texas Health and Human Services (hhs.texas.gov), Texas WIC (texaswic.org), 2-1-1 Texas (211texas.org); each file names its source page
