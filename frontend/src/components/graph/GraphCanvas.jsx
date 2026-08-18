import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { select } from 'd3-selection';
import { zoom as d3Zoom, zoomIdentity } from 'd3-zoom';

import GraphControls from './GraphControls';
import GraphEdges from './GraphEdges';
import GraphNode from './GraphNode';
import GraphTimeline from './GraphTimeline';
import { deriveGraph } from '../../lib/graph/deriveGraph';
import { useForceGraph } from '../../hooks/useForceGraph';
import { useTimeMachine } from '../../hooks/useTimeMachine';
import './graph.css';

// Tags that describe the conversation rather than what it was about. Mirrors the list the
// organizer applies server-side; this one exists for nodes organized before that landed.
const MEDIUM_WORDS = new Set([
    'assistant',
    'chat',
    'clarification',
    'conversation',
    'dialogue',
    'discussion',
    'exchange',
    'followup',
    'general',
    'greeting',
    'hello',
    'inquiry',
    'interaction',
    'introduction',
    'message',
    'misc',
    'other',
    'question',
    'reply',
    'request',
    'response',
    'start',
    'unclear',
    'user'
]);

const isMediumTopic = (topic) => {
    const words = topic.replace(/-/g, ' ').split(/\s+/).filter(Boolean);
    return words.length > 0 && words.every((word) => MEDIUM_WORDS.has(word));
};

// How far the pointer must travel before a press counts as dragging the node rather than
// clicking it. Small enough that a deliberate nudge still moves the pill.
const DRAG_THRESHOLD_PX = 4;

const SCALE_MIN = 0.3;
const SCALE_MAX = 2.5;
const SETTINGS_KEY = 'pami.graph.forces';

const readSettings = () => {
    try {
        const raw = window.localStorage.getItem(SETTINGS_KEY);
        const parsed = raw ? JSON.parse(raw) : null;
        if (!parsed) return { connectionForce: 58, repulsionForce: 34 };
        return {
            connectionForce: Number(parsed.connectionForce) || 58,
            repulsionForce: Number(parsed.repulsionForce) || 34
        };
    } catch (error) {
        return { connectionForce: 58, repulsionForce: 34 };
    }
};

// One connection at a time, slow enough to read which peer it reached.
const SPOTLIGHT_LINK_INTERVAL_MS = 520;
const SPOTLIGHT_HOLD_MS = 1500;
// The links are written by a background task and arrive over several seconds, so the
// spotlight has to outlast the polling that fetches them or it would end before the
// connections it exists to show.
const SPOTLIGHT_MIN_MS = 7000;

function GraphCanvas({
    contextNodes,
    projectId,
    isLoading,
    error,
    onRetry,
    onOpenNode,
    toggle,
    spotlightId,
    onSpotlightDone
}) {
    const viewportRef = useRef(null);
    const zoomBehaviourRef = useRef(null);
    const userAdjustedRef = useRef(false);
    const lastFitRef = useRef(0);
    const lastCountRef = useRef(0);
    const controlsRef = useRef(null);
    const [size, setSize] = useState({ width: 0, height: 0 });
    const [transform, setTransform] = useState(zoomIdentity);
    const [hoverId, setHoverId] = useState(null);
    const [selectedId, setSelectedId] = useState(null);
    const [search, setSearch] = useState('');
    const [settings, setSettings] = useState(readSettings);

    // The graph is drawn from whatever list it is handed, so rewinding the project is a
    // matter of handing it the nodes that existed at that moment. deriveGraph drops a link
    // whose other end is missing, which unwinds the connections for free.
    const timeMachine = useTimeMachine(contextNodes);

    const { nodes: sourceNodes, links: sourceLinks } = useMemo(
        () => deriveGraph(timeMachine.visibleNodes),
        [timeMachine.visibleNodes]
    );

    const {
        tick,
        nodes,
        links,
        pinnedIds,
        dragStart,
        dragMove,
        dragEnd,
        dragCancel,
        unpin,
        resetLayout
    } = useForceGraph({
        measureHostRef: viewportRef,
        nodes: sourceNodes,
        links: sourceLinks,
        projectId,
        width: size.width,
        height: size.height,
        connectionForce: settings.connectionForce,
        repulsionForce: settings.repulsionForce
    });

    // Measured, not assumed: the toolbar wraps to two rows on a narrow window, and a fixed
    // offset would put the chip strip on top of it.
    const [controlsHeight, setControlsHeight] = useState(48);

    useEffect(() => {
        const element = controlsRef.current;
        if (!element) return undefined;

        const measure = () => setControlsHeight(element.offsetHeight || 48);
        measure();
        const observer = new window.ResizeObserver(measure);
        observer.observe(element);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        const element = viewportRef.current;
        if (!element) return undefined;

        const measure = () => {
            const rect = element.getBoundingClientRect();
            setSize({ width: Math.round(rect.width), height: Math.round(rect.height) });
        };

        measure();
        const observer = new window.ResizeObserver(measure);
        observer.observe(element);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        const element = viewportRef.current;
        if (!element) return undefined;

        const behaviour = d3Zoom()
            .scaleExtent([SCALE_MIN, SCALE_MAX])
            .filter((event) => !event.target.closest('.graph-pill'))
            .on('zoom', (event) => {
                if (event.sourceEvent) userAdjustedRef.current = true;
                setTransform(event.transform);
            });

        zoomBehaviourRef.current = behaviour;
        select(element).call(behaviour).on('dblclick.zoom', null);
        return () => {
            select(element).on('.zoom', null);
            zoomBehaviourRef.current = null;
        };
    }, []);

    useEffect(() => {
        setSelectedId(null);
        setHoverId(null);
        setSearch('');
        userAdjustedRef.current = false;
    }, [projectId]);

    useEffect(() => {
        try {
            window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
        } catch (storageError) {
            /* persistence is a convenience */
        }
    }, [settings]);

    const toScene = useCallback(
        (event) => {
            const rect = viewportRef.current.getBoundingClientRect();
            return {
                x: (event.clientX - rect.left - transform.x) / transform.k,
                y: (event.clientY - rect.top - transform.y) / transform.k
            };
        },
        [transform]
    );

    const handlePointerDown = useCallback(
        (event, node) => {
            if (event.button !== 0) return;
            event.stopPropagation();
            setSelectedId(node.id);
            dragStart(node.id);

            const origin = { x: event.clientX, y: event.clientY };
            let moved = false;
            const onMove = (moveEvent) => {
                // A press is never perfectly still, so any movement at all used to count as a
                // drag. Below the threshold this stays a click - which is what lets a click
                // open the conversation without a stray pixel turning it into a nudge.
                if (!moved) {
                    const dx = moveEvent.clientX - origin.x;
                    const dy = moveEvent.clientY - origin.y;
                    if (dx * dx + dy * dy < DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX) return;
                    moved = true;
                }
                const point = toScene(moveEvent);
                dragMove(node.id, point.x, point.y);
            };
            const onUp = () => {
                window.removeEventListener('pointermove', onMove);
                window.removeEventListener('pointerup', onUp);
                window.removeEventListener('pointercancel', onUp);
                // Every press ends in one of these two. Leaving the no-movement case
                // unhandled is what kept the simulation running for ever.
                if (moved) {
                    dragEnd(node.id);
                } else {
                    dragCancel(node.id);
                    // The pill is a button showing a conversation; clicking it should open
                    // that conversation. It used to need a double click, so a single click
                    // selected the node and otherwise did nothing at all.
                    if (onOpenNode) onOpenNode(node);
                }
            };

            window.addEventListener('pointermove', onMove);
            window.addEventListener('pointerup', onUp);
            // A press that leaves the window, or is taken over by a scroll gesture, never
            // fires pointerup.
            window.addEventListener('pointercancel', onUp);
        },
        [dragCancel, dragEnd, dragMove, dragStart, onOpenNode, toScene]
    );

    // A node just created from a conversation: everything else dims and its connections are
    // revealed one after another, so the user can see where it landed and what it attached to.
    const [revealedCount, setRevealedCount] = useState(0);
    const spotlightStartedRef = useRef(0);

    const spotlightLinks = useMemo(() => {
        if (!spotlightId) return [];
        return links
            .filter(
                (link) => link.source.id === spotlightId || link.target.id === spotlightId
            )
            // Strongest first, so the reveal reads as "closest relative, then the next".
            .sort((left, right) => right.score - left.score);
    }, [links, spotlightId]);

    const spotlightActive = Boolean(spotlightId) && nodes.some((node) => node.id === spotlightId);

    // A node created while the graph is rewound would be created into the past and never seen.
    // The spotlight exists to show it arriving, so it returns to the present first.
    useEffect(() => {
        if (spotlightId && !timeMachine.isLive) timeMachine.goLive();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [spotlightId]);

    useEffect(() => {
        if (!spotlightId) return;
        spotlightStartedRef.current = performance.now();
        setRevealedCount(0);
    }, [spotlightId]);

    useEffect(() => {
        if (!spotlightActive) return undefined;

        if (revealedCount < spotlightLinks.length) {
            const timer = setTimeout(
                () => setRevealedCount((count) => count + 1),
                SPOTLIGHT_LINK_INTERVAL_MS
            );
            return () => clearTimeout(timer);
        }

        // Waiting out the minimum here, rather than ending as soon as the known links are
        // shown, is what lets a link that arrives late still be revealed: this effect re-runs
        // and cancels the pending finish.
        const elapsed = performance.now() - spotlightStartedRef.current;
        const wait = Math.max(SPOTLIGHT_HOLD_MS, SPOTLIGHT_MIN_MS - elapsed);
        const timer = setTimeout(() => onSpotlightDone && onSpotlightDone(), wait);
        return () => clearTimeout(timer);
    }, [spotlightActive, revealedCount, spotlightLinks.length, onSpotlightDone]);

    const { spotlightNeighbourIds, spotlightShownIds, spotlightHiddenIds } = useMemo(() => {
        const shown = new Set();
        const hidden = new Set();
        const neighbours = new Set();
        spotlightLinks.forEach((link, index) => {
            if (index < revealedCount) {
                shown.add(link.id);
                neighbours.add(link.source.id === spotlightId ? link.target.id : link.source.id);
            } else {
                hidden.add(link.id);
            }
        });
        return {
            spotlightNeighbourIds: neighbours,
            spotlightShownIds: shown,
            spotlightHiddenIds: hidden
        };
    }, [spotlightLinks, revealedCount, spotlightId]);

    const focusId = hoverId || selectedId;

    // GraphTimeline renders nothing below two nodes, so the fit must reserve nothing either.
    const hasTimeline = timeMachine.total > 1;

    const searchTerm = search.trim().toLowerCase();
    const matchIds = useMemo(() => {
        if (!searchTerm) return null;
        return new Set(
            nodes
                .filter((node) => {
                    // Header, summary and the topics the AI chose. A header is five words, so
                    // searching it alone missed a conversation by every word it was actually
                    // about.
                    if (node.title.toLowerCase().includes(searchTerm)) return true;
                    if ((node.summary || '').toLowerCase().includes(searchTerm)) return true;
                    return (node.topics || []).some((topic) =>
                        String(topic).toLowerCase().includes(searchTerm)
                    );
                })
                .map((node) => node.id)
        );
    }, [nodes, searchTerm]);

    // The topics worth offering as one-click filters: the ones that group nodes together. A
    // topic on a single node narrows nothing, and there is a long tail of those.
    const topicChips = useMemo(() => {
        const counts = new Map();
        nodes.forEach((node) => {
            (node.topics || []).forEach((raw) => {
                const topic = String(raw).trim().toLowerCase();
                if (topic.length < 3) return;
                // Nodes organized before the prompt was fixed carry tags about the medium
                // rather than the subject - "greeting", "assistant response". They are the
                // most common tags in an old project and the least useful chips.
                if (isMediumTopic(topic)) return;
                counts.set(topic, (counts.get(topic) || 0) + 1);
            });
        });
        return Array.from(counts.entries())
            .filter(([, count]) => count > 1)
            .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
            .slice(0, 6)
            .map(([topic, count]) => ({ topic, count }));
    }, [nodes]);

    const { neighbourIds, activeLinkIds } = useMemo(() => {
        const neighbours = new Set();
        const activeLinks = new Set();

        if (matchIds) {
            links.forEach((link) => {
                if (matchIds.has(link.source.id) && matchIds.has(link.target.id)) {
                    activeLinks.add(link.id);
                }
            });
        }

        if (!focusId) return { neighbourIds: neighbours, activeLinkIds: activeLinks };

        links.forEach((link) => {
            const sourceId = link.source.id;
            const targetId = link.target.id;
            if (sourceId === focusId) {
                neighbours.add(targetId);
                activeLinks.add(link.id);
            } else if (targetId === focusId) {
                neighbours.add(sourceId);
                activeLinks.add(link.id);
            }
        });
        return { neighbourIds: neighbours, activeLinkIds: activeLinks };
    }, [focusId, links, matchIds]);

    const fitToView = useCallback(() => {
        const behaviour = zoomBehaviourRef.current;
        if (!behaviour || !nodes.length || !size.width || !size.height) return;

        const xs = nodes.map((node) => node.x);
        const ys = nodes.map((node) => node.y);
        const minX = Math.min(...xs) - 120;
        const maxX = Math.max(...xs) + 120;
        const top = Math.min(...ys);
        const maxY = Math.max(...ys) + 60;
        const timelineHeight = hasTimeline ? 62 : 0;

        // Both floating bars overlay the canvas - controls at the top, the timeline at the
        // bottom - so the room they need is measured in scene units, which depend on the scale
        // being solved for. Two passes: fit without them, then re-fit with them converted at
        // that scale.
        // The timeline was the one missing: the oldest nodes, which the scrubber removes
        // first, were exactly the ones sitting behind it.
        const timelineRoom = timelineHeight > 0 ? timelineHeight + 12 : 0;
        const fit = (minY, bottomRoom) =>
            Math.max(
                SCALE_MIN,
                Math.min(
                    SCALE_MAX,
                    Math.min(
                        size.width / (maxX - minX),
                        size.height / (maxY - minY + bottomRoom)
                    )
                )
            );
        const stripHeight = topicChips.length > 0 ? 44 : 0;
        const barHeight = (controlsRef.current?.offsetHeight || 40) + stripHeight + 20;
        const firstPass = fit(top - 60, 0);
        const minY = top - Math.max(60, barHeight / firstPass);
        const bottomRoom = timelineRoom / firstPass;
        const scale = fit(minY, bottomRoom);

        // Centring vertically silently discards the headroom whenever width is the binding
        // constraint, which is how a node ends up hidden under the bar. Clamp the top node
        // to sit below it.
        // `top` is the topmost node's centre, so half a pill still sits above it.
        const halfPill = Math.max(...nodes.map((node) => node.h)) / 2;
        const centredY =
            (size.height - timelineHeight) / 2 - ((minY + maxY) / 2) * scale;
        const topAnchoredY = barHeight + halfPill * scale - top * scale;
        const fitsVertically = (maxY - minY) * scale <= size.height - timelineHeight;
        const next = zoomIdentity
            .translate(
                size.width / 2 - ((minX + maxX) / 2) * scale,
                fitsVertically ? Math.max(centredY, topAnchoredY) : centredY
            )
            .scale(scale);

        select(viewportRef.current).call(behaviour.transform, next);
    }, [hasTimeline, nodes, size.height, size.width, topicChips.length]);

    // A node arriving or leaving re-enables framing even after the user has panned: a node
    // created from a conversation starts with no links, which puts it at the edge of the
    // layout, and without this it can appear entirely outside the viewport.
    useEffect(() => {
        if (nodes.length && nodes.length !== lastCountRef.current) {
            lastCountRef.current = nodes.length;
            // Not while rewound: the count changes on every step of the scrubber, and
            // re-framing each time makes the camera chase the graph instead of letting it
            // grow inside a steady frame.
            if (timeMachine.isLive) userAdjustedRef.current = false;
        }
    }, [nodes.length, timeMachine.isLive]);

    // Keep the graph framed while it settles, and hand control over for good the moment
    // the user zooms or pans themselves.
    useEffect(() => {
        if (!tick || !nodes.length || userAdjustedRef.current) return;
        const now = performance.now();
        if (now - lastFitRef.current < 350) return;
        lastFitRef.current = now;
        fitToView();
    }, [fitToView, nodes.length, tick]);

    const isDimmed = spotlightActive || Boolean(focusId) || Boolean(matchIds);

    const nodeIsDimmed = (node) => {
        // The spotlight wins over hover and search: it is a short, deliberate animation, and
        // the pointer happening to rest on a pill must not undo it.
        if (spotlightActive) {
            return node.id !== spotlightId && !spotlightNeighbourIds.has(node.id);
        }
        if (matchIds) return !matchIds.has(node.id);
        if (!focusId) return false;
        return node.id !== focusId && !neighbourIds.has(node.id);
    };

    // States render as overlays INSIDE the viewport rather than replacing it. Returning a
    // different tree here left `viewportRef` null on first mount, so the measure and zoom
    // effects — which run once — silently bound to nothing and the canvas stayed blank.
    let overlay = null;
    if (error) {
        overlay = (
            <div className="graph-state graph-state-error">
                <p>The conversation graph could not be loaded.</p>
                <button type="button" className="graph-action" onClick={onRetry}>
                    Try again
                </button>
            </div>
        );
    } else if (isLoading) {
        overlay = (
            <div className="graph-state graph-state-loading" aria-busy="true">
                {[0, 1, 2, 3, 4, 5].map((index) => (
                    <span key={index} className="graph-skeleton-pill" />
                ))}
            </div>
        );
    } else if (!sourceNodes.length) {
        overlay = timeMachine.isLive ? (
            <div className="graph-state graph-state-empty">
                <p>No conversations in this project yet.</p>
                <span>Start a chat and the graph will fill in as conversations connect.</span>
            </div>
        ) : (
            // Rewound past the first node. Saying so beats an empty canvas that looks broken.
            <div className="graph-state graph-state-empty">
                <p>Before the project began.</p>
                <span>Nothing had been discussed yet at this point.</span>
            </div>
        );
    }

    return (
        <div className="graph-root">
            <GraphControls
                containerRef={controlsRef}
                toggle={toggle}
                connectionForce={settings.connectionForce}
                repulsionForce={settings.repulsionForce}
                onConnectionForce={(value) =>
                    setSettings((current) => ({ ...current, connectionForce: value }))
                }
                onRepulsionForce={(value) =>
                    setSettings((current) => ({ ...current, repulsionForce: value }))
                }
                search={search}
                onSearch={setSearch}
                matchCount={matchIds ? matchIds.size : 0}
                zoomPercent={Math.round(transform.k * 100)}
                onFit={fitToView}
                onReset={resetLayout}
            />

            {/* The topics the AI already assigned, as one-click filters, on their own strip
                under the toolbar. Each chip carries its own surface, so the strip needs no
                background of its own and nothing is laid over the graph. */}
            {topicChips.length > 0 && (
                <div className="graph-topics" style={{ top: controlsHeight + 14 }}>
                    {topicChips.map(({ topic, count }) => (
                        <button
                            key={topic}
                            type="button"
                            className="graph-topic"
                            aria-pressed={search === topic}
                            onClick={() =>
                                setSearch((current) => (current === topic ? '' : topic))
                            }
                            title={`${count} conversations`}
                        >
                            {topic}
                        </button>
                    ))}
                </div>
            )}

            <div
                ref={viewportRef}
                className="graph-viewport"
                onPointerDown={() => setSelectedId(null)}
            >
                <div
                    className="graph-scene"
                    data-tick={tick}
                    style={{
                        transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`
                    }}
                >
                    <GraphEdges
                        links={links}
                        activeLinkIds={spotlightActive ? spotlightShownIds : activeLinkIds}
                        dimmed={isDimmed}
                        hiddenLinkIds={spotlightActive ? spotlightHiddenIds : null}
                    />
                    <div className="graph-nodes">
                        {nodes.map((node) => (
                            <GraphNode
                                key={node.id}
                                node={node}
                                isSelected={node.id === selectedId}
                                isNeighbour={neighbourIds.has(node.id)}
                                isPinned={pinnedIds.includes(node.id)}
                                isSpotlit={spotlightActive && node.id === spotlightId}
                                dimmed={nodeIsDimmed(node)}
                                onPointerDown={handlePointerDown}
                                onOpen={onOpenNode}
                                onHover={setHoverId}
                                onUnpin={unpin}
                            />
                        ))}
                    </div>
                </div>

                {overlay}
            </div>

            <GraphTimeline
                total={timeMachine.total}
                step={timeMachine.step}
                at={timeMachine.at}
                isLive={timeMachine.isLive}
                isPlaying={timeMachine.isPlaying}
                onScrub={timeMachine.scrubTo}
                onPlay={timeMachine.play}
                onPause={timeMachine.pause}
                onLive={timeMachine.goLive}
            />
        </div>
    );
}

export default GraphCanvas;
