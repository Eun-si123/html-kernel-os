# HTML Kernel OS website — editorial redesign (2026-11-23)

## Brief

Replace generic gradients, floating terminal effects and decorative cards with a credible, readable technical project website. Visitors should see the difference between a **real HTML-derived x86-64 kernel** and a simulated browser desktop or a finished operating system. Preserve all seven boot choices and interactive source/boot behavior.

## Public references visited in the mini-PC browser (inspiration only)

- [Zed](https://zed.dev/) — focused real-product demonstration and strong content hierarchy.
- [Linux Kernel Archives](https://www.kernel.org/) — factual, easily accessible project state rather than vague marketing.
- [Ink & Switch](https://www.inkandswitch.com/) — research publication, editorial rhythm and restrained typography.

No graphics, font files, screenshots, proprietary code, trademarks or licensed visuals are copied from these references.

## Site system

Warm paper background, ink-colored text, one terracotta accent, and a dark code/boot surface. Plain borders and typographic spacing replace glossy gradients and fake app windows. System sans for Korean, local serif for headline emphasis, and system mono for code. No remote fonts, trackers or framework.

Structure: goal, genuine HTML-to-ISO process, observed evidence, readable approach, source code, roadmap and honest limitations. Boot Lab becomes a practical session console with image selection, boot/stop/download actions, VGA screen, COM1 output and accurate statuses.

## Validation gates

- Existing compiler and browser static tests, docs checks and JavaScript syntax pass.
- Desktop and 390px mobile layouts are visually inspected; no horizontal overflow; keyboard focus visible.
- Home tabs/copy and all seven boot values behave as before.
- Real Chromium boot of a newly deployed ISO produces exact expected COM1 bytes.
- Physical PC, memory management and interrupts remain unverified / unimplemented.

Do not confuse a visual preview with execution evidence.

## CSS deployment cache

Both pages pin a versioned CSS URL to prevent previously cached pre-redesign assets from styling newly deployed HTML. Update the version string when changing the CSS on subsequent releases. Tests resolve the local asset path before the query.

## Automatic device light/dark theme (2026-11-23)

Both routes follow the browser/OS prefers-color-scheme setting with CSS, including form controls and toolbar color. The existing warm paper palette remains light; dark uses charcoal and ink-friendly contrast. No local storage, JavaScript, tracking, or manual toggle. Cache-versioned shared CSS URL is incremented to avoid stale styles during Pages deployment.
