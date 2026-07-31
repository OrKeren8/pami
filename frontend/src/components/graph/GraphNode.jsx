const dotSize = (degree) => Math.min(11, 6 + degree);

function GraphNode({
    node,
    isSelected,
    isNeighbour,
    isPinned,
    isSpotlit,
    dimmed,
    onPointerDown,
    onOpen,
    onHover,
    onUnpin
}) {
    const classNames = ['graph-pill'];
    if (isSelected) classNames.push('graph-pill-selected');
    if (isNeighbour) classNames.push('graph-pill-neighbour');
    if (isPinned) classNames.push('graph-pill-pinned');
    if (isSpotlit) classNames.push('graph-pill-spotlight');
    if (dimmed) classNames.push('graph-pill-dim');

    return (
        <button
            type="button"
            className={classNames.join(' ')}
            style={{
                transform: `translate(${node.x - node.w / 2}px, ${node.y - node.h / 2}px)`,
                width: node.w,
                height: node.h,
                '--pill-color': node.color
            }}
            title={node.title}
            aria-label={`${node.title}, ${node.degree} connections`}
            aria-pressed={isSelected}
            onPointerDown={(event) => {
                if (event.altKey) {
                    onUnpin(node.id);
                    return;
                }
                onPointerDown(event, node);
            }}
            onDoubleClick={() => onOpen(node)}
            onMouseEnter={() => onHover(node.id)}
            onMouseLeave={() => onHover(null)}
            onFocus={() => onHover(node.id)}
            onBlur={() => onHover(null)}
            onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onOpen(node);
                }
            }}
        >
            <span
                className="graph-pill-dot"
                style={{ width: dotSize(node.degree), height: dotSize(node.degree) }}
            />
            <span className="graph-pill-label">{node.title}</span>
        </button>
    );
}

export default GraphNode;
