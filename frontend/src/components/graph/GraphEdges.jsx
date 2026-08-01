const strokeWidth = (score) => 0.8 + (Math.min(100, Math.max(0, score)) / 100) * 1.8;
const strokeOpacity = (score) => 0.16 + (Math.min(100, Math.max(0, score)) / 100) * 0.44;

function GraphEdges({ links, activeLinkIds, dimmed, hiddenLinkIds }) {
    return (
        <svg className="graph-edges" aria-hidden="true">
            {links.map((link) => {
                // d3 replaces the string endpoints with node objects when the link force
                // initializes; a render in between would otherwise emit NaN coordinates.
                if (
                    !Number.isFinite(link.source?.x) ||
                    !Number.isFinite(link.source?.y) ||
                    !Number.isFinite(link.target?.x) ||
                    !Number.isFinite(link.target?.y)
                ) {
                    return null;
                }

                // Not rendered at all rather than made transparent: this is how a
                // connection appears one after another during the reveal.
                if (hiddenLinkIds && hiddenLinkIds.has(link.id)) return null;

                const isActive = activeLinkIds.has(link.id);
                const className = dimmed && !isActive ? 'graph-edge graph-edge-dim' : 'graph-edge';
                return (
                    <line
                        key={link.id}
                        className={`${className}${isActive ? ' graph-edge-revealed' : ''}`}
                        x1={link.source.x}
                        y1={link.source.y}
                        x2={link.target.x}
                        y2={link.target.y}
                        strokeWidth={strokeWidth(link.score)}
                        strokeOpacity={isActive ? 0.85 : strokeOpacity(link.score)}
                    />
                );
            })}
        </svg>
    );
}

export default GraphEdges;
