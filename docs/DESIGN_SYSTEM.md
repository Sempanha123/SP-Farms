# Design System

SP-Farms uses a compact desktop-first visual language. The supplied reference image remains the source of truth for shell silhouette, density, and interaction hierarchy; final reference fidelity is locked in Phase 56.

## Tokens

Both themes expose semantic colors for window, surface, alternate surface, border, text, muted text, accent, warning, danger, success, and selection. Components consume semantics rather than hardcoded status colors.

- Primary accent: mint/lime with dark readable text.
- Warning: restrained amber.
- Danger: red only for destructive actions and errors.
- Radius: 8 px controls, 10 px panels.
- Base type: 13 px Segoe UI Variable or Segoe UI.
- Inputs/buttons: 30 px minimum height.
- Dense table rows: 34 px.
- Borders: thin and low contrast; no glow or glass effects.

## Components

- `Panel`: bordered grouping surface.
- `PrimaryButton`: high-priority mint action.
- `StatusChip`: compact semantic state marker.
- `EmptyState`: title, guidance, and optional next action.
- `CompactTable`: alternating dense table with hidden row header.
- `MetricRow`: compact summary metrics.

Every actionable control must preserve a visible keyboard focus state. Text and essential state must not rely on color alone. Use the offscreen-tested `DesignPreview` as the component gallery while developing shared controls.
