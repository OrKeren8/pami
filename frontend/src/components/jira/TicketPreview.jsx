import React, { useMemo } from 'react';

import { parseBlocks } from '../../lib/markdownBlocks';

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

function TicketPreview({ text }) {
    const blocks = useMemo(() => parseBlocks(text), [text]);

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
                                    {item.text || <span className="ticket-preview-blank" />}
                                </li>
                            ))}
                        </ul>
                    );
                }
                if (block.kind === 'steps') {
                    return (
                        <ol key={index} className="ticket-preview-list">
                            {block.items.map((item, itemIndex) => (
                                <li key={itemIndex}>
                                    {item.text || <span className="ticket-preview-blank" />}
                                </li>
                            ))}
                        </ol>
                    );
                }
                if (block.kind === 'bullets') {
                    return (
                        <ul key={index} className="ticket-preview-list">
                            {block.items.map((item, itemIndex) => (
                                <li key={itemIndex}>
                                    {item.text || <span className="ticket-preview-blank" />}
                                </li>
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
