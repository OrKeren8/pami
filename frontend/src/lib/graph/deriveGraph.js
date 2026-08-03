export const MIN_CORRELATION_SCORE = 30;

const nodeId = (node) => {
    const raw = node?.id || node?._id;
    if (!raw) return '';
    if (typeof raw === 'string') return raw;
    return String(raw.$oid || raw);
};

export function deriveGraph(contextNodes, minScore = MIN_CORRELATION_SCORE) {
    const source = Array.isArray(contextNodes) ? contextNodes : [];

    const nodes = source
        .map((node) => {
            const id = nodeId(node);
            if (!id) return null;
            return {
                id,
                title: node.header || 'Context node',
                summary: node.summary || '',
                topics: Array.isArray(node.topics) ? node.topics : [],
                color: node.color || '#8b5cf6',
                nodeType: node.node_type || 'context',
                conversationId:
                    node.conversation_id || node.conversationId || node.conversation || null,
                degree: 0
            };
        })
        .filter(Boolean);

    const known = new Set(nodes.map((node) => node.id));
    const pairToScore = new Map();

    source.forEach((node) => {
        const sourceId = nodeId(node);
        if (!sourceId || !known.has(sourceId)) return;

        (node.sibling_links || []).forEach((link) => {
            const targetId = String(link?.sibling_id || '');
            const score = Number(link?.correlation_score || 0);
            if (!targetId || targetId === sourceId) return;
            if (!known.has(targetId) || score < minScore) return;

            const key = [sourceId, targetId].sort().join('::');
            const previous = pairToScore.get(key);
            if (previous === undefined || score > previous) pairToScore.set(key, score);
        });
    });

    const byId = new Map(nodes.map((node) => [node.id, node]));
    const links = Array.from(pairToScore.entries()).map(([key, score]) => {
        const [source_, target_] = key.split('::');
        byId.get(source_).degree += 1;
        byId.get(target_).degree += 1;
        return { id: key, source: source_, target: target_, score };
    });

    return { nodes, links };
}
