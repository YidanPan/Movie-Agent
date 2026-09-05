# P2 frontend module boundaries

The production console intentionally remains zero-build. `style.css` and
`app.js` are still the compatibility entry points used by existing browsers,
while the files in `css/` and `js/` expose semantic seams for incremental
extraction. New components should import the token layer and use the module
helpers instead of adding page-global selectors or hard-coded theme colors.

