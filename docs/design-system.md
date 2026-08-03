# PAMI design system

`frontend/src/styles/system.css`, loaded once from `src/index.css` so it sits ahead of every
page stylesheet.

It exists because the same control kept coming out differently on each screen: three button
sizes, four label treatments, status pills whose only styling lived in one page's CSS. The
system owns those decisions; a page stylesheet should only say where things sit.

## How to use it

Compose classes in the markup, and write page CSS only for layout:

```jsx
<div className="ds-panel ds-panel-pad">
    <div className="ds-panel-head">
        <div className="ds-tabs" role="tablist">
            <button role="tab" aria-selected={active} className="ds-tab">Story</button>
        </div>
        <span className="ds-hint">A change described from the user's side.</span>
    </div>

    <label className="ds-field">
        <span>Assignee</span>
        <select className="ds-select">…</select>
    </label>

    <div className="ds-spread">
        <span className="ds-pill ds-pill-done">Done</span>
        <button className="ds-btn ds-btn-primary">Submit</button>
    </div>
</div>
```

## Rules

1. **Use the tokens.** A raw hex or a magic `13px` in a page stylesheet is drift waiting to
   happen. Colours, spacing, radii, shadows, type sizes and durations all have variables.
2. **Pink is for actions and brand marks.** Surfaces stay near-white. If the panel is tinted,
   the button on it is no longer the loudest thing on screen.
3. **One accent per view.** Two primary buttons means neither is primary.
4. **Labels are quiet.** They name a value; they are not the value. `ds-field > span` is
   sentence case at weight 600 on purpose - uppercase 700 labels shouted over the content.
5. **Three elevations, no more.** `--ds-shadow-1/2/3`. A page with five depths has none.
6. **Destructive actions are outlined, not filled.** `ds-btn-danger` is the second click of a
   two-click confirm, never the first thing your eye lands on.

## What is in it

| Group | Classes |
| --- | --- |
| Panels | `ds-panel`, `ds-panel-pad`, `ds-panel-head` |
| Fields | `ds-field`, `ds-field-head`, `ds-label`, `ds-input`, `ds-select`, `ds-textarea` |
| Buttons | `ds-btn` + `ds-btn-primary` / `-ghost` / `-danger` / `-quiet`, `ds-btn-sm` |
| Tabs | `ds-tabs`, `ds-tab` (state via `aria-selected`, not a class) |
| Pills | `ds-pill` + `ds-pill-accent` / `-todo` / `-progress` / `-done` |
| Lists | `ds-list`, `ds-row` (state via `aria-current`), `ds-row-truncate` |
| Text | `ds-section-label`, `ds-hint`, `ds-empty` (+ `-title` / `-body`), `ds-error` |
| Layout | `ds-inline`, `ds-spread` |

State comes from ARIA attributes where one exists (`aria-selected`, `aria-current`,
`:disabled`) rather than a parallel `.active` class, so the styling and the accessibility tree
cannot disagree.

## Tokens

Spacing is a 4px scale (`--ds-1` … `--ds-8`), so gaps chosen independently in two components
still line up. Type is `--ds-t-xs` … `--ds-t-xl`. Motion is `--ds-fast` with `--ds-ease`, and
every transition is disabled under `prefers-reduced-motion`.

## Adoption

The Jira workspace is built entirely on it and is the reference implementation - read
`frontend/src/pages/JiraConsolePage.js` alongside `JiraConsolePage.css` to see the split
between system and layout. The dashboard, Chat View and Slack console still carry their own
older CSS; move them over a screen at a time, deleting the local rules that a primitive
replaces rather than layering the two.
