function GraphControls({
    containerRef,
    toggle,
    connectionForce,
    repulsionForce,
    onConnectionForce,
    onRepulsionForce,
    search,
    onSearch,
    matchCount,
    topics = [],
    onTopic,
    zoomPercent,
    onFit,
    onReset
}) {
    return (
        <div className="graph-controls" ref={containerRef}>
            {toggle}

            <div className="graph-controls-search">
                <input
                    id="graph-search"
                    type="search"
                    className="graph-search-input"
                    placeholder="Find a conversation"
                    value={search}
                    onChange={(event) => onSearch(event.target.value)}
                />
                {search ? (
                    <span className="graph-search-count">{matchCount} found</span>
                ) : null}

                {/* The topics the AI already assigned, as one-click filters. Clicking the
                    active one clears it, so the chip is a toggle rather than a dead end. */}
                {topics.length > 0 && (
                    <div className="graph-topics">
                        {topics.map(({ topic, count }) => (
                            <button
                                key={topic}
                                type="button"
                                className="graph-topic"
                                aria-pressed={search === topic}
                                onClick={() => onTopic(topic)}
                                title={`${count} conversations`}
                            >
                                {topic}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            <div className="graph-controls-sliders graph-controls-right">
                <label className="graph-slider" htmlFor="graph-connection-force">
                    <span>Connection</span>
                    <input
                        id="graph-connection-force"
                        type="range"
                        min="10"
                        max="100"
                        value={connectionForce}
                        onChange={(event) => onConnectionForce(Number(event.target.value))}
                    />
                    <output>{connectionForce}</output>
                </label>

                <label className="graph-slider" htmlFor="graph-repulsion-force">
                    <span>Repel</span>
                    <input
                        id="graph-repulsion-force"
                        type="range"
                        min="10"
                        max="100"
                        value={repulsionForce}
                        onChange={(event) => onRepulsionForce(Number(event.target.value))}
                    />
                    <output>{repulsionForce}</output>
                </label>
            </div>

            <div className="graph-controls-actions">
                <span className="graph-zoom-readout">{zoomPercent}%</span>
                <button type="button" className="graph-action" onClick={onFit}>
                    Fit
                </button>
                <button type="button" className="graph-action" onClick={onReset}>
                    Reset layout
                </button>
            </div>
        </div>
    );
}

export default GraphControls;
