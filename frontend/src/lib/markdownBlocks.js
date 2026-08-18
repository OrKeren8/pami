/**
 * Splits text into the block shapes the app actually writes: headings, bullet lists, numbered
 * lists, checklists and paragraphs.
 *
 * Shared by the Jira ticket preview and the chat, which need the same structure and disagree
 * only about inline styling - a ticket must not carry `**bold**` into Jira, and a chat reply
 * should show it as bold rather than as punctuation. Keeping the split here means the two
 * cannot drift on what counts as a list.
 *
 * Deliberately not a markdown library: these five shapes are the whole vocabulary, and a full
 * parser would render things neither surface wants.
 */

export const parseBlocks = (text) => {
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
