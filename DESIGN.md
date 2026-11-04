---
name: TrackLyrics
description: A quiet desktop surface for a local music library and listening.
colors:
  primary-accent: "#8ed9b2"
  dark-accent-strong: "#a3e6c3"
  dark-accent-ink: "#12231a"
  dark-warning: "#d8b46c"
  dark-canvas: "#101315"
  dark-sidebar: "#14181b"
  dark-surface: "#171b1e"
  dark-raised: "#1d2225"
  dark-text: "#ecefeb"
  dark-secondary: "#a3acae"
  dark-muted: "#7d888b"
  dark-divider: "#2a3134"
  dark-divider-strong: "#384145"
  dark-selected: "#1d2824"
  dark-danger: "#ee8f84"
  light-canvas: "#f3f5f3"
  light-sidebar: "#eef1ef"
  light-surface: "#f8faf8"
  light-raised: "#ffffff"
  light-text: "#202629"
  light-secondary: "#556166"
  light-muted: "#606c71"
  light-divider: "#d9dfdc"
  light-divider-strong: "#c9d1cd"
  light-selected: "#e7f0eb"
  light-accent: "#2d7958"
  light-accent-strong: "#24694c"
  light-accent-ink: "#f7fbf8"
  light-warning: "#8b6419"
  light-danger: "#b5483e"
typography:
  interface:
    fontFamily: '"Segoe UI Variable", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "13px"
    fontWeight: 400
  heading:
    fontFamily: '"Segoe UI Variable", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "17px"
    fontWeight: 620
    letterSpacing: "-0.025em"
  lyrics:
    fontFamily: '"Segoe UI Variable", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.9
rounded:
  compact: "4px"
  control: "7px"
  player-mark: "8px"
  dialog: "11px"
  circle: "99px"
spacing:
  compact: "4px"
  tight: "8px"
  local: "12px"
  group: "18px"
  inset: "22px"
components:
  button-primary:
    backgroundColor: "{colors.primary-accent}"
    textColor: "{colors.dark-accent-ink}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "34px"
  search-field:
    backgroundColor: "{colors.dark-canvas}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.control}"
    padding: "0 9px"
    height: "34px"
  navigation-active:
    backgroundColor: "{colors.dark-selected}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "36px"
  format-label:
    textColor: "{colors.dark-muted}"
    rounded: "{rounded.compact}"
    padding: "3px 5px"
  player-play:
    backgroundColor: "{colors.dark-text}"
    textColor: "{colors.dark-canvas}"
    rounded: "{rounded.circle}"
    size: "34px"
    height: "34px"
  track-row-selected:
    backgroundColor: "{colors.dark-selected}"
    textColor: "{colors.dark-text}"
    padding: "0 11px"
    height: "62px"
---

# Design System: TrackLyrics

## Overview

**Creative North Star: "Listening Archive"**

TrackLyrics presents a local music collection as a place to return to. The desktop frame keeps navigation, a ruled library, a lyrics reader, and audio transport in a compact working arrangement. Graphite and cool paper themes share the same hierarchy; a restrained green marks primary actions and current playback.

The selected track connects its row, lyrics context, and player. Downloads have their own view with per-job progress and outcomes. Use stored metadata and measured application state; the product has no approved album-art catalog.

**Key Characteristics:**

- Compact navigation and scannable, ruled track rows.
- A lyrics reader beside the library and persistent player dock.
- Dark and light themes with parallel information hierarchy.
- Feedback describes real track, download, and application states.

## Colors

Graphite and cool paper provide the two canvas families; their text, dividers, selected surfaces, and semantic states retain their roles across themes.

### Primary
- **Listening Green** (`#8ed9b2`): Dark-theme primary actions and current playback. The light theme uses its deeper counterpart, `#2d7958`, for the same role.

### Neutral
- **Graphite Canvas** (`#101315`), **Sidebar** (`#14181b`), **Surface** (`#171b1e`), and **Raised Surface** (`#1d2225`): dark-theme page, navigation, work surface, and raised-control layers.
- **Graphite Text** (`#ecefeb`), **Secondary** (`#a3acae`), and **Muted** (`#7d888b`): primary content, supporting text, and quiet metadata in dark mode.
- **Graphite Divider** (`#2a3134`) and **Strong Divider** (`#384145`): table rules and stronger control boundaries in dark mode.
- **Cool Paper** (`#f3f5f3`), **Sidebar** (`#eef1ef`), **Surface** (`#f8faf8`), and **Raised Surface** (`#ffffff`): corresponding light-theme layers.
- **Paper Text** (`#202629`), **Secondary** (`#556166`), **Muted** (`#606c71`), **Divider** (`#d9dfdc`), and **Strong Divider** (`#c9d1cd`): light-theme text hierarchy and rules.
- **Selected Surfaces** (`#1d2824` dark, `#e7f0eb` light): active navigation and selected track rows.

### Tertiary
- **Soft Coral** (`#ee8f84` dark, `#b5483e` light): failures and destructive actions. Warning uses the separate amber values defined in the stylesheet.

**The State Color Rule.** Keep accent, danger, warning, success, and muted text tied to their actual interface states in both themes.

## Typography

**Interface Font:** Segoe UI Variable, with Segoe UI, system UI, and platform sans-serif fallbacks.
**Lyrics Font:** The same interface stack, set with a wider measure and more generous leading.

**Character:** Familiar desktop typography keeps controls and metadata compact. Weight and spacing establish hierarchy; lyrics are given room to read without introducing a decorative display face.

### Hierarchy
- **Interface** (400, 13px, 1.4): application baseline for controls and ordinary content.
- **Heading** (620, 17px, 1.25, `-0.025em`): active view title; dialog and download titles scale within the same family.
- **Track title** (540, 12px): primary row metadata; smaller at the narrowest layout.
- **Lyrics** (400, 14px, 1.9, max width 42ch): readable lyric content, reduced to 13px on the narrow layout.
- **Metadata labels** (typically 9–11px): quiet table headings, statuses, and supporting details. Time, counts, and percentages use tabular numerals.

## Layout

The desktop shell uses a 218px navigation column, a 68px top bar, a two-column library and lyrics workspace, and an 86px bottom player dock. The library and lyrics content scroll independently; the player remains in view. Search and Add Downloads stay in the top bar, and queue details open in a compact popover or dedicated Downloads view.

At 1180px the navigation and workspace columns contract. At 980px navigation becomes an icon rail. At 760px the lyrics reader switches to a pane reached from the selected track while the player becomes a two-row dock. At 500px the rail narrows, search collapses to an icon until focused, and track rows reduce their metadata density. The interface honors reduced-motion preferences.

Keep content aligned to the ruled library grid. Use compact 4–12px control and row spacing, with 18–22px insets around larger regions. Do not place ordinary workflows inside nested card grids.

## Elevation & Depth

The library is mostly flat: surface tone and hairline rules establish its structure. Dialogs, menus, queue popovers, and notices use the shared shadow to leave the content plane. Shadow opacity shifts with the theme.

### Shadow Vocabulary
- **Dialog and popover** (`0 18px 52px rgba(0, 0, 0, 0.4), 0 3px 10px rgba(0, 0, 0, 0.24)` in dark mode): floating menus, dialogs, queue popover, and notices. Light mode uses `0 18px 52px rgba(20, 34, 27, 0.16), 0 3px 10px rgba(20, 34, 27, 0.08)`.

## Shapes

Controls use compact 5–7px corners; dialogs use 11px. Track rows stay rectangular and table-like. Circular geometry belongs to transport buttons and the small local indicator. Borders and surface shifts define grouping; ordinary library content does not become a series of rounded cards.

## Components

### Buttons
- **Character:** compact, direct controls with visible keyboard focus.
- **Primary:** green fill, dark ink in dark mode and light ink in light mode; 34px minimum height with 12px horizontal padding.
- **Secondary:** raised surface with a strong divider; quiet actions remain transparent until hover.
- **Danger:** reserved for destructive confirmation, with coral or the explicit destructive fill.
- **Hover / Focus:** short color feedback; all interactive controls receive a 2px theme-aware focus outline.

### Inputs / Fields
- **Search:** 34px single-line field in the top bar, 7px corners, canvas fill, and a border/surface shift on focus. At widths up to 500px it expands when focused.
- **Forms:** themed text fields, text areas, and selects use the same divider and raised/canvas surfaces. Errors appear beside the action they describe.

### Navigation
- Icon-and-label rows are 36px high, with a 7px radius. The active item uses a tinted surface and normal text; counts remain quiet until active.
- Below 980px the sidebar becomes an icon rail; below 500px it contracts further.

### Chips
- Audio format labels are small outlined tags with 4px corners and tracked uppercase text. They identify stored format rather than acting as pills.
- The lyrics language switch is a bordered segmented control; unavailable languages remain visibly disabled.

### Cards / Containers
- Library rows are 62px high (57px at the narrowest width), separated by one-pixel rules; selected and current playback states remain distinct.
- The player is a persistent dock with track identity, previous/play/next, seek, volume, format, and queue access. Narrow layouts reflow it to two rows.
- Download rows own their status, percentage, error, retry action, and progress bar. Progress fills by transform so updates do not shift the list.
- Dialogs use an 11px corner, 20px padding, a themed border, and the overlay shadow.

## Do's and Don'ts

### Do:
- **Do** keep selected track, lyrics context, and player state in sync.
- **Do** use real library metadata and per-job download progress.
- **Do** preserve the same information hierarchy in dark and light themes.
- **Do** keep visible keyboard focus and honor reduced motion.
- **Do** give errors and empty states a factual explanation and a relevant next action where available.

### Don't:
- **Don't** fabricate album art, metrics, or server, network, and system-status messages.
- **Don't** use generic dashboard card grids or nested cards for ordinary library content.
- **Don't** treat a duplicate warning as a blocked save; duplicates may still be saved.
- **Don't** remove a track or playlist without the implemented confirmation step.
