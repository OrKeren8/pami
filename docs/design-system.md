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
2. **Pink is for actions, focus and brand marks.** Lines and surfaces are neutral. Outlining
   every input in pink spent the accent on things that are not actions, which left nothing to
   make the real action stand out.
3. **One accent per view.** Two primary buttons means neither is primary. This is also why the
   selected tab is a raised white chip and not a gradient - a view switch is not an action.
4. **Shape carries hierarchy.** Buttons are `--ds-r-sm`, panels `--ds-r-lg`, and only status
   pills are fully round. When everything was a pill, a button looked like a tag.
5. **Anything that stands in a row with other controls is `--ds-control-h` tall.** Neighbouring
   controls at 32, 34, 36 and 38px is the kind of thing you feel before you can name it.
   Set a height and you must set `box-sizing: border-box`, or padding is added on top.
6. **Labels are quiet but legible.** 12px, weight 600, neutral grey. Not uppercase 700, which
   shouted over the values, and not 11.5px mauve, which was decoration.
7. **Large text is tracked tighter.** `--ds-track-tight` on headings and big numbers. The same
   tracking at 1.5rem as at 0.875rem reads loose.
8. **Three elevations, each a tight contact shadow plus a soft ambient one.** One diffuse blur
   alone reads as fog; the near shadow is what makes an edge look crisp.
9. **Destructive actions are outlined, not filled**, and `--ds-danger` is a different hue from
   the brand. In rose it was a shade away from the accent, so an error read as a notice.
10. **Disabled means a flat grey control**, never the same control at half opacity - that looks
    like a rendering fault rather than a state.
11. **Pills are a status vocabulary.** Facts about a thing (type, assignee, priority, due date)
    go in `ds-meta` as one quiet line. Spend pills on everything and the status disappears.

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
| Data | `ds-stat` (+ `-warn`), `ds-table-scroll`, `ds-table`, `ds-num` |
| Metadata | `ds-meta`, `ds-meta-sep` |
| Page rule | `ds-header-rule` |
| Whole-region states | `ds-state`, `ds-spinner` |
| Layout | `ds-inline`, `ds-spread` |

State comes from ARIA attributes where one exists (`aria-selected`, `aria-current`,
`:disabled`) rather than a parallel `.active` class, so the styling and the accessibility tree
cannot disagree.

## Tokens

Spacing is a 4px scale (`--ds-1` … `--ds-8`), so gaps chosen independently in two components
still line up. Type is `--ds-t-xs` … `--ds-t-xl` with `--ds-track-tight` / `--ds-track-snug`
for anything large. Radii run `--ds-r-xs` … `--ds-r-lg` plus `--ds-r-pill`. Control heights are
`--ds-control-h` and `--ds-control-h-sm`. Motion is `--ds-fast` with `--ds-ease`, and every
transition is disabled under `prefers-reduced-motion` - except the spinner, which is slowed
rather than stopped, because a frozen spinner reads as a hung page.

## Judging it

The look was arrived at by rendering the built CSS in headless Chrome, at real page widths,
with real content, and then writing down what was ugly before changing anything. Static
harnesses for each screen live outside the repo (they are throwaway), but the method is worth
keeping: screenshot, name the specific defect, fix that, screenshot again. Every rule above is
a defect that was visible in a screenshot, not a preference.

## Adoption

The Jira workspace is built entirely on it and is the reference implementation - read
`frontend/src/pages/JiraConsolePage.js` alongside `JiraConsolePage.css` to see the split
between system and layout.

Migrated so far: **Jira workspace**, **admin dashboard**, **Chat View**. In each case the page
stylesheet lost its own buttons, inputs, spinner, table and loading/error states and kept only
layout plus whatever is genuinely that page's identity - the pink conversation card and its
hover preview stayed in Chat View, because nothing else would reuse them.

Also migrated: **sign-in**, and the **Slack console**, which needed the dark surface tokens
(`--ds-dark-*`, `--ds-on-dark*`) before it could use anything - it is deliberately a dark
Slack-alike, so the move was to give the system plum darks in the pink's own hue family rather
than to repaint the console pink.

Not migrated: the **dashboard** (`HomePage.css`, 7k lines). Take it a region at a time, deleting
the local rules a primitive replaces rather than layering the two. Its modals and forms already
use the primitives; the graph, the chat pane and the node modal do not.
