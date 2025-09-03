# Static Files Directory

This directory contains static files that are served with **highest priority** by Caddy before any requests are proxied to the CFG App.

## How It Works

1. **Priority Serving**: Caddy checks this directory first for any requested files
2. **Direct Serving**: If a file is found, it's served directly without application processing
3. **Fallback**: If no static file is found, the request is proxied to the CFG App

## File Types Supported

- **HTML**: Landing pages, documentation
- **CSS**: Stylesheets and themes
- **JavaScript**: Client-side functionality
- **Images**: Icons, logos, screenshots
- **Documents**: PDFs, text files
- **Other**: Any static assets

## Current Structure

```
static/
├── index.html          # Main landing page
├── robots.txt          # Search engine directives
├── css/
│   └── style.css       # Main stylesheet
├── images/             # Image assets
├── js/                 # JavaScript files
└── .gitkeep            # Git tracking file
```

## Adding New Files

Simply place files in the appropriate subdirectory:

- **HTML pages**: Place directly in `static/` (e.g., `static/about.html` → `/about.html`)
- **CSS files**: Place in `static/css/` (e.g., `static/css/theme.css` → `/css/theme.css`)
- **Images**: Place in `static/images/` (e.g., `static/images/logo.png` → `/images/logo.png`)
- **JavaScript**: Place in `static/js/` (e.g., `static/js/app.js` → `/js/app.js`)

## URL Mapping

| File Path | URL Access |
|-----------|------------|
| `static/index.html` | `/` or `/index.html` |
| `static/about.html` | `/about.html` |
| `static/css/style.css` | `/css/style.css` |
| `static/images/logo.png` | `/images/logo.png` |
| `static/js/app.js` | `/js/app.js` |

## Benefits

- **Performance**: No application processing overhead for static content
- **Caching**: Better browser caching for static assets
- **Scalability**: Reduced load on the CFG App
- **Flexibility**: Easy to add landing pages, documentation, and other static content

## Example Use Cases

- Landing pages and marketing content
- Documentation and help pages
- Client download pages
- API documentation
- Status pages
- Maintenance pages
