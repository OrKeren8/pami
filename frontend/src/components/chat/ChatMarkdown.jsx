import React, { useMemo } from 'react';

import { parseBlocks } from '../../lib/markdownBlocks';

/**
 * Renders an assistant reply as formatted text.
 *
 * The model writes markdown whether or not anything asks it to, so a reply arrived reading
 * `3. **Centralized Design System:** ...` - the emphasis showing as punctuation and the list
 * as one run-on paragraph. This renders the shapes the model actually produces and nothing
 * else: no links, no images, no raw HTML, because none of that should come out of a chat
 * bubble unreviewed.
 *
 * Blocks come from the shared parser; inline emphasis is handled here, since the Jira preview
 * deliberately leaves `**bold**` alone.
 */

// Bold before italic so `**x**` is not read as an italic wrapping `*x*`, and code first of all
// so emphasis inside a code span stays literal.
const INLINE = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*\n]+\*)/g;

const renderInline = (text) =>
    text.split(INLINE).map((part, index) => {
        if (!part) return null;
        if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
            return <code key={index}>{part.slice(1, -1)}</code>;
        }
        if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
            return <strong key={index}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('__') && part.endsWith('__') && part.length > 4) {
            return <strong key={index}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
            return <em key={index}>{part.slice(1, -1)}</em>;
        }
        return <React.Fragment key={index}>{part}</React.Fragment>;
    });

function ChatMarkdown({ text, trailing = null }) {
    const blocks = useMemo(() => parseBlocks(text), [text]);

    if (!blocks.length) return <p className="chat-md-paragraph">{trailing}</p>;

    // The caret rides on the last block so it follows the text as it is revealed, instead of
    // sitting under a finished paragraph on a line of its own.
    const lastIndex = blocks.length - 1;

    return (
        <div className="chat-md">
            {blocks.map((block, index) => {
                const tail = index === lastIndex ? trailing : null;

                if (block.kind === 'h') {
                    // Capped so a reply cannot outrank the page heading.
                    const Tag = `h${Math.min(5, block.level + 3)}`;
                    return (
                        <Tag key={index} className="chat-md-heading">
                            {renderInline(block.text)}
                            {tail}
                        </Tag>
                    );
                }

                if (block.kind === 'checks') {
                    return (
                        <ul key={index} className="chat-md-checks">
                            {block.items.map((item, itemIndex) => (
                                <li key={itemIndex} className={item.done ? 'done' : ''}>
                                    <span aria-hidden="true">{item.done ? '☑' : '☐'}</span>
                                    {renderInline(item.text)}
                                </li>
                            ))}
                        </ul>
                    );
                }

                if (block.kind === 'steps' || block.kind === 'bullets') {
                    const List = block.kind === 'steps' ? 'ol' : 'ul';
                    return (
                        <List
                            key={index}
                            className="chat-md-list"
                            start={block.kind === 'steps' ? block.start : undefined}
                        >
                            {block.items.map((item, itemIndex) => (
                                <li key={itemIndex}>{renderInline(item.text)}</li>
                            ))}
                        </List>
                    );
                }

                return (
                    <p key={index} className="chat-md-paragraph">
                        {renderInline(block.text)}
                        {tail}
                    </p>
                );
            })}
        </div>
    );
}

export default ChatMarkdown;
