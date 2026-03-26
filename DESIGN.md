# Design System Strategy: The Kinetic Operator

## 1. Overview & Creative North Star
**Creative North Star: "Precision Luminescence"**

This design system moves away from the clunky, legacy aesthetics of industrial SCADA (Supervisory Control and Data Acquisition) and towards a "High-Tech Editorial" experience. It treats industrial data not as a spreadsheet, but as a living, breathing digital organism. 

By leveraging **intentional asymmetry**, we break the rigid "grid-jail" of standard dashboards. Critical metrics are given oversized, display-grade prominence, while secondary controls are nested within sophisticated tonal layers. We use the contrast between the deep, obsidian-like background (`#10141a`) and the neon-kinetic accents (`primary` cyan and `secondary` amber) to guide the operator’s eye through a hierarchy of urgency and importance. This is a system designed for high-stakes environments where professional sophistication meets split-second readability.

---

## 2. Colors: Tonal Architecture
The palette is rooted in a deep-space dark mode, utilizing neon accents not as decoration, but as functional status indicators.

*   **Primary (`#c3f5ff`):** Reserved for "Active State" and "Normal Operation." Use this to signify flow, connectivity, and healthy system pulses.
*   **Secondary (`#ffd799`):** The "Cautionary Pulse." Used for warnings, manual overrides, or secondary data streams that require heightened attention.
*   **Tertiary (`#b5ffaa`):** The "Safe Success" indicator. Used for completed processes or confirmed binary states.

### The "No-Line" Rule
Standard 1px borders are strictly prohibited for sectioning. They clutter the interface and create visual noise. Instead:
*   Define boundaries through **Background Color Shifts**. A `surface-container-low` component should sit on a `surface` background to create a visible but soft edge.
*   Use **Spaced Voids**. Rely on the spacing scale (e.g., `spacing.8`) to create "invisible" borders that allow the layout to breathe.

### Surface Hierarchy & Nesting
Treat the UI as a series of stacked, machined plates.
*   **Base Layer:** `surface` (#10141a)
*   **Primary Containers:** `surface-container` (#1c2026) for main data modules.
*   **Nested Elements:** `surface-container-high` (#262a31) for interactive cards or highlighted sensor groups within a module.

### The "Glass & Gradient" Rule
To achieve a "high-tech" feel, use **Glassmorphism** for floating overlays (modals or tooltips). 
*   **Effect:** Apply `surface-container-highest` with 60% opacity and a `20px` backdrop-blur. 
*   **Signature Textures:** For high-priority CTAs or "System Active" headers, use a subtle linear gradient from `primary` (#c3f5ff) to `primary_container` (#00e5ff) at a 135-degree angle.

---

## 3. Typography: The Narrative Scale
We use a dual-typeface system to balance technical precision with modern editorial flair.

*   **Display & Headlines (Space Grotesk):** Use for high-level KPIs and system titles. Its wide aperture and technical geometry feel "engineered." 
    *   *Tip:* Use `display-lg` (3.5rem) for the most critical system metric (e.g., "98.4% Efficiency") to create an immediate focal point.
*   **Body & Labels (Inter):** Use for all functional data, descriptions, and labels. It is chosen for its extreme legibility at small sizes (`body-sm` at 0.75rem).
*   **Visual Hierarchy:** Always pair a `label-md` in `on_surface_variant` (muted) with a `title-lg` in `on_surface` (bright) to create clear "Property: Value" relationships without needing lines.

---

## 4. Elevation & Depth: Tonal Layering
In a SCADA environment, shadows can be distracting. We use **Tonal Layering** to convey depth.

*   **The Layering Principle:** Depth is achieved by "stacking." A `surface-container-lowest` card placed on a `surface-container-low` section creates a recessed, "etched" look. Conversely, a `surface-container-highest` card on a `surface` background creates a "raised" platform.
*   **Ambient Shadows:** For floating elements (like a diagnostic pop-over), use a shadow color tinted with `surface_tint` (#00daf3) at 6% opacity with a large `48px` blur. This simulates the glow of a neon screen rather than a generic grey shadow.
*   **The "Ghost Border" Fallback:** If a container requires a border for accessibility, use the `outline_variant` token at **15% opacity**. This creates a "glint" on the edge of the container, mimicking machined metal.

---

## 5. Components

### Buttons
*   **Primary:** Solid `primary` background with `on_primary` text. Use `rounded-md` (0.75rem).
*   **Secondary:** Ghost style. No background, `outline` border at 20% opacity, `primary` text.
*   **States:** On hover, primary buttons should emit a soft outer glow using the `primary` color (10% opacity blur).

### Cards & Lists
*   **Forbid Dividers:** Do not use lines to separate list items. Use a background shift (alternating `surface-container-low` and `surface-container-lowest`) or simply use `spacing.4` to separate items.
*   **Corner Radius:** Stick strictly to `rounded-lg` (1rem) for main cards to maintain the "sophisticated" feel requested.

### Data Inputs
*   **Industrial Inputs:** Fields should use `surface_container_highest` backgrounds. The bottom edge should have a 2px accent of `outline_variant` that transitions to `primary` when the field is focused.

### Specialized SCADA Components
*   **The "Status Pulse" Chip:** A small selection chip using `tertiary_container` for "Running" states. Use a `full` (9999px) corner radius for a pill shape.
*   **The "Glow Metric" Card:** For critical alerts, the entire card background should have a subtle radial gradient of `error_container` fading into `surface_container`.

---

## 6. Do's and Don'ts

### Do:
*   **DO** use whitespace as a functional tool. If two data points are unrelated, push them apart using the `spacing.16` or `spacing.24` tokens.
*   **DO** use "Space Grotesk" for numbers. They are the "hero" of a SCADA system.
*   **DO** use `surface-bright` for hover states on dark containers to create a "backlit" effect.

### Don't:
*   **DON'T** use 100% white (#FFFFFF). It causes eye strain in dark industrial environments. Use `on_surface` (#dfe2eb).
*   **DON'T** use sharp 90-degree corners. It feels dated and aggressive. Stick to the `roundedness` scale, favoring `md` and `lg`.
*   **DON'T** use standard red for every warning. Use `secondary` (amber) for non-critical warnings and reserve `error` (#ffb4ab) only for system-critical failures.