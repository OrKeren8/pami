import React, { useMemo } from 'react';

/**
 * Shows the ticket description as structure rather than as raw text.
 *
 * The templates use `## Heading`, `- item` and `- [ ] item` because that is what Jira and the
 * team's ticket format use. Left in a textarea they read as punctuation; a reviewer skimming the
 * ticket cannot see where the acceptance criteria stop. This renders those three forms and
 * leaves everything else as a paragraph - deliberately not a markdown library, because the
 * ticket only ever contains these shapes and a parser would invite inline styling that Jira
 * would then show literally.
 */

const parse = (text) => {
    const blocks = [];
    let paragraph = [];
    let list = null;

    const flushParagraph = () => {
        if (paragraph.length) {
            blocks.push({ kind: 'p', text: paragraph.join(' ') });
            paragraph = [];
        }
    };
    const flushList = () => {
        if (list) {
            blocks.push(list);
            list = null;
        }
    };

    for (const rawLine of (text || '').split('\n')) {
        const line = rawLine.trimEnd();

        if (!line.trim()) {
            flushParagraph();
            flushList();
            continue;
        }

        const heading = line.match(/^(#{1,4})\s+(.*)$/);
        if (heading) {
            flushParagraph();
            flushList();
            blocks.push({ kind: 'h', level: heading[1].length, text: heading[2] });
            continue;
        }

        // Checklist before plain bullet: "- [ ] x" also matches the bullet pattern.
        const check = line.match(/^\s*-\s+\[( |x|X)\]\s*(.*)$/);
        if (check) {
            flushParagraph();
            if (list?.kind !== 'checks') {
                flushList();
                list = { kind: 'checks', items: [] };
            }
            list.items.push({ done: check[1].toLowerCase() === 'x', text: check[2] });
            continue;
        }

        const bullet = line.match(/^\s*[-*]\s+(.*)$/);
        if (bullet) {
            flushParagraph();
            if (list?.kind !== 'bullets') {
                flushList();
                list = { kind: 'bullets', items: [] };
            }
            list.items.push({ text: bullet[1] });
            continue;
        }

        const numbered = line.match(/^\s*(\d+)[.)]\s+(.*)$/);
        if (numbered) {
            flushParagraph();
            if (list?.kind !== 'steps') {
                flushList();
                list = { kind: 'steps', items: [] };
            }
            list.items.push({ text: numbered[2] });
            continue;
        }

        paragraph.push(line.trim());
    }

    flushParagraph();
    flushList();
    return blocks;
};

function TicketPreview({ text }) {
    const blocks = useMemo(() => parse(text), [text]);

    if (!blocks.length) {
        return <p className="ticket-preview-empty">Nothing written yet.</p>;
    }

    return (
        <div className="ticket-preview">
            {blocks.map((block, index) => {
                if (block.kind === 'h') {
                    // Capped at h4 so a ticket cannot outrank the page heading.
                    const Tag = `h${Math.min(4, block.level + 2)}`;
                    return (
                        <Tag key={index} className="ticket-preview-heading">
                            {block.text}
                        </Tag>
                    );
                }
                if (block.kind === 'checks') {
                    return (
                        <ul key={index} className="ticket-preview-checks">
                            {block.items.map((item, itemIndex) => (
                                <li key={itemIndex} className={item.done ? 'done' : ''}>
                                    <span aria-hidden="true">{item.done ? '☑' : '☐'}</span>
                                    {item.text || <em>empty</em>}
                                </li>
                            ))}
                        </ul>
                    );
                }
                if (block.kind === 'steps') {
                    return (
                        <ol key={index} className="ticket-preview-list">
                            {block.items.map((item, itemIndex) => (
                                <li key={itemIndex}>{item.text || <em>empty</em>}</li>
                            ))}
                        </ol>
                    );
                }
                if (block.kind === 'bullets') {
                    return (
                        <ul key={index} className="ticket-preview-list">
                            {block.items.map((item, itemIndex) => (
                                <li key={itemIndex}>{item.text || <em>empty</em>}</li>
                            ))}
                        </ul>
                    );
                }
                return (
                    <p key={index} className="ticket-preview-paragraph">
                        {block.text}
                    </p>
                );
            })}
        </div>
    );
}

export default TicketPreview;
