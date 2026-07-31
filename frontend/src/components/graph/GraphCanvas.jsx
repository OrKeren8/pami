import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { select } from 'd3-selection';
import { zoom as d3Zoom, zoomIdentity } from 'd3-zoom';

import GraphControls from './GraphControls';
import GraphEdges from './GraphEdges';
import GraphNode from './GraphNode';
import { deriveGraph } from '../../lib/graph/deriveGraph';
import { useForceGraph } from '../../hooks/useForceGraph';
import './graph.css';

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

function GraphCanvas({ contextNodes, projectId, isLoading, error, onRetry, onOpenNode, toggle }) {
    const viewportRef = useRef(null);
    const zoomBehaviourRef = useRef(null);
    const userAdjustedRef = useRef(false);
    const lastFitRef = useRef(0);
    const controlsRef = useRef(null);
    const [size, setSize] = useState({ width: 0, height: 0 });
    const [transform, setTransform] = useState(zoomIdentity);
    const [hoverId, setHoverId] = useState(null);
    const [selectedId, setSelectedId] = useState(null);
    const [search, setSearch] = useState('');
    const [settings, setSettings] = useState(readSettings);

    const { nodes: sourceNodes, links: sourceLinks } = useMemo(
        () => deriveGraph(contextNodes),
        [contextNodes]
    );

    const {
        tick,
        nodes,
        links,
        pinnedIds,
        dragStart,
        dragMove,
        dragEnd,
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

            let moved = false;
            const onMove = (moveEvent) => {
                moved = true;
                const point = toScene(moveEvent);
                dragMove(node.id, point.x, point.y);
            };
            const onUp = () => {
                window.removeEventListener('pointermove', onMove);
                window.removeEventListener('pointerup', onUp);
                if (moved) dragEnd(node.id);
            };

            window.addEventListener('pointermove', onMove);
            window.addEventListener('pointerup', onUp);
        },
        [dragEnd, dragMove, dragStart, toScene]
    );

    const focusId = hoverId || selectedId;

    const searchTerm = search.trim().toLowerCase();
    const matchIds = useMemo(() => {
        if (!searchTerm) return null;
        return new Set(
            nodes
                .filter((node) => node.title.toLowerCase().includes(searchTerm))
                .map((node) => node.id)
        );
    }, [nodes, searchTerm]);

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

        // The floating controls bar overlays the canvas, so the headroom it needs is measured
        // in scene units — which depend on the scale we are solving for. Two passes: fit
        // without the bar, then re-fit with the bar converted at that scale.
        const fit = (minY) =>
            Math.max(
                SCALE_MIN,
                Math.min(
                    SCALE_MAX,
                    Math.min(size.width / (maxX - minX), size.height / (maxY - minY))
                )
            );
        const barHeight = (controlsRef.current?.offsetHeight || 40) + 20;
        const firstPass = fit(top - 60);
        const minY = top - Math.max(60, barHeight / firstPass);
        const scale = fit(minY);

        // Centring vertically silently discards the headroom whenever width is the binding
        // constraint, which is how a node ends up hidden under the bar. Clamp the top node
        // to sit below it.
        // `top` is the topmost node's centre, so half a pill still sits above it.
        const halfPill = Math.max(...nodes.map((node) => node.h)) / 2;
        const centredY = size.height / 2 - ((minY + maxY) / 2) * scale;
        const topAnchoredY = barHeight + halfPill * scale - top * scale;
        const fitsVertically = (maxY - minY) * scale <= size.height;
        const next = zoomIdentity
            .translate(
                size.width / 2 - ((minX + maxX) / 2) * scale,
                fitsVertically ? Math.max(centredY, topAnchoredY) : centredY
            )
            .scale(scale);

        select(viewportRef.current).call(behaviour.transform, next);
    }, [nodes, size.height, size.width]);

    // Keep the graph framed while it settles, and hand control over for good the moment
    // the user zooms or pans themselves.
    useEffect(() => {
        if (!tick || !nodes.length || userAdjustedRef.current) return;
        const now = performance.now();
        if (now - lastFitRef.current < 350) return;
        lastFitRef.current = now;
        fitToView();
    }, [fitToView, nodes.length, tick]);

    const isDimmed = Boolean(focusId) || Boolean(matchIds);

    const nodeIsDimmed = (node) => {
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
        overlay = (
            <div className="graph-state graph-state-empty">
                <p>No conversations in this project yet.</p>
                <span>Start a chat and the graph will fill in as conversations connect.</span>
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
                    <GraphEdges links={links} activeLinkIds={activeLinkIds} dimmed={isDimmed} />
                    <div className="graph-nodes">
                        {nodes.map((node) => (
                            <GraphNode
                                key={node.id}
                                node={node}
                                isSelected={node.id === selectedId}
                                isNeighbour={neighbourIds.has(node.id)}
                                isPinned={pinnedIds.includes(node.id)}
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
        </div>
    );
}

export default GraphCanvas;
