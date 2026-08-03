/**
 * The scrubber under the graph. Drag it back and the project rewinds.
 *
 * Reads as a transport control - play, a track, a position - rather than as a filter, because
 * that is what it is: the same project at an earlier moment, not a subset of it.
 */

const dayFormat = { day: 'numeric', month: 'short' };
const fullFormat = { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' };

function GraphTimeline({ total, step, at, isLive, isPlaying, onScrub, onPlay, onPause, onLive }) {
    // Nothing to rewind through: one node is the whole history.
    if (total < 2) return null;

    const label = isLive
        ? 'Now'
        : new Date(at || Date.now()).toLocaleDateString(undefined, dayFormat);

    return (
        <div className={`graph-timeline ${isLive ? '' : 'graph-timeline-past'}`}>
            <button
                type="button"
                className="graph-timeline-play"
                onClick={isPlaying ? onPause : onPlay}
                aria-label={isPlaying ? 'Pause' : 'Replay the project from the start'}
                title={isPlaying ? 'Pause' : 'Replay the project from the start'}
            >
                {isPlaying ? '❚❚' : '▶'}
            </button>

            <input
                className="graph-timeline-track"
                type="range"
                min="0"
                max={total}
                step="1"
                value={step}
                aria-label="Project history"
                aria-valuetext={
                    isLive
                        ? `Now, all ${total} nodes`
                        : `${new Date(at || Date.now()).toLocaleString(
                              undefined,
                              fullFormat
                          )}, ${step} of ${total} nodes`
                }
                onChange={(event) => onScrub(Number(event.target.value))}
            />

            <span className="graph-timeline-readout">
                <strong>{label}</strong>
                <span>
                    {step} / {total}
                </span>
            </span>

            {/* Only offered when it does something. A live "Now" button is a dead control. */}
            {!isLive && (
                <button type="button" className="graph-timeline-now" onClick={onLive}>
                    Back to now
                </button>
            )}
        </div>
    );
}

export default GraphTimeline;
