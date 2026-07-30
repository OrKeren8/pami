import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { forceLink, forceSimulation, forceX, forceY } from 'd3-force';

import { rectCollide } from '../lib/graph/rectCollide';
import { unlinkedRepel } from '../lib/graph/unlinkedRepel';

const PILL_WIDTH = 168;
const PILL_HEIGHT = 32;
const COLLIDE_PADDING = 10;

// Every link pulls identically, the way Obsidian treats them: being connected is the fact
// that matters, and correlation_score already speaks through line thickness. Score-scaled
// physics also made hub nodes fight their own strongest links.
const LINK_STRENGTH = 0.7;
// Must clear the collide minimum (pill width + padding), or the link force and the collide
// force fight forever and connected pills sit on top of each other.
const LINK_DISTANCE = PILL_WIDTH + COLLIDE_PADDING + 24;
// Weak on purpose: anything stronger compresses the whole graph into one ball and erases
// the distance difference between connected and unconnected conversations.
const CENTER_STRENGTH = 0.012;
const DRAG_ALPHA_TARGET = 0.3;
const RESCORE_ALPHA_TARGET = 0.1;
const WARMUP_TICKS = 320;
const SETTLE_TICKS = 320;

const pinStorageKey = (projectId) => `pami.graph.pins.${projectId}`;

const readPins = (projectId) => {
    if (!projectId) return {};
    try {
        const raw = window.localStorage.getItem(pinStorageKey(projectId));
        const parsed = raw ? JSON.parse(raw) : {};
        return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (error) {
        return {};
    }
};

const writePins = (projectId, pins) => {
    if (!projectId) return;
    try {
        window.localStorage.setItem(pinStorageKey(projectId), JSON.stringify(pins));
    } catch (error) {
        /* storage full or unavailable: pins are a convenience, not a requirement */
    }
};

const prefersReducedMotion = () =>
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function useForceGraph({
    nodes,
    links,
    projectId,
    width,
    height,
    connectionForce = 58,
    repulsionForce = 34
}) {
    const simulationRef = useRef(null);
    const datumRef = useRef({ nodes: [], links: [] });
    const pinsRef = useRef({});
    const frameRef = useRef(null);
    const [tick, setTick] = useState(0);
    // Mirrored into state because the pin marker is rendered: a ref alone would leave the
    // marker one interaction behind.
    const [pinnedIds, setPinnedIds] = useState([]);

    const centerX = width / 2;
    const centerY = height / 2;

    const linkStrengthScale = useMemo(
        () => Math.max(0.1, (Number(connectionForce) || 0) / 58),
        [connectionForce]
    );
    const chargeScale = useMemo(
        () => Math.max(0.1, (Number(repulsionForce) || 0) / 34),
        [repulsionForce]
    );
    // Once link strength saturates at 1, the only way "pull them closer" stays meaningful is
    // to shorten the target distance as well. Floored at 1 so the distance never drops below
    // the collide minimum and starts a fight the layout cannot win.
    const linkDistanceScale = useMemo(
        () => Math.min(1.6, Math.max(1, Math.sqrt(58 / Math.max(10, Number(connectionForce) || 58)))),
        [connectionForce]
    );

    const scheduleRender = useCallback(() => {
        if (frameRef.current) return;
        frameRef.current = window.requestAnimationFrame(() => {
            frameRef.current = null;
            setTick((value) => value + 1);
        });
    }, []);

    useEffect(() => {
        pinsRef.current = readPins(projectId);
        setPinnedIds(Object.keys(pinsRef.current));
    }, [projectId]);

    useEffect(() => {
        if (!nodes.length || !width || !height) {
            simulationRef.current?.stop();
            simulationRef.current = null;
            datumRef.current = { nodes: [], links: [] };
            return undefined;
        }

        const previous = new Map(datumRef.current.nodes.map((node) => [node.id, node]));
        const pins = pinsRef.current;

        const simulationNodes = nodes.map((node, index) => {
            const carried = previous.get(node.id);
            const pin = pins[node.id];
            const seedAngle = (index / nodes.length) * Math.PI * 2;
            const seedRadius = Math.min(width, height) * 0.28;

            return {
                ...node,
                w: PILL_WIDTH,
                h: PILL_HEIGHT,
                x: carried?.x ?? pin?.x ?? centerX + Math.cos(seedAngle) * seedRadius,
                y: carried?.y ?? pin?.y ?? centerY + Math.sin(seedAngle) * seedRadius,
                vx: carried?.vx ?? 0,
                vy: carried?.vy ?? 0,
                fx: pin ? pin.x : null,
                fy: pin ? pin.y : null
            };
        });

        const byId = new Map(simulationNodes.map((node) => [node.id, node]));
        const simulationLinks = links
            .filter((link) => byId.has(link.source) && byId.has(link.target))
            .map((link) => ({ ...link }));

        const simulation = forceSimulation(simulationNodes)
            .force('repel', unlinkedRepel(chargeScale).links(simulationLinks))
            .force(
                'link',
                forceLink(simulationLinks)
                    .id((node) => node.id)
                    .distance(LINK_DISTANCE * linkDistanceScale)
                    // Clamped to 1: d3 treats link strength as a fraction, and a slider at
                    // maximum would otherwise overshoot and destabilise the layout.
                    .strength(Math.min(1, LINK_STRENGTH * linkStrengthScale))
            )
            .force('collide', rectCollide(COLLIDE_PADDING, 1, 3))
            .force('x', forceX(centerX).strength(CENTER_STRENGTH))
            .force('y', forceY(centerY).strength(CENTER_STRENGTH))
            .velocityDecay(0.4);

        datumRef.current = { nodes: simulationNodes, links: simulationLinks };
        simulationRef.current = simulation;

        if (prefersReducedMotion()) {
            simulation.stop();
            simulation.tick(SETTLE_TICKS);
            setTick((value) => value + 1);
        } else {
            // Ticks are driven by requestAnimationFrame, which a hidden tab suspends. A
            // synchronous warm-up means positions are always meaningful on first paint.
            simulation.tick(WARMUP_TICKS);
            setTick((value) => value + 1);
            simulation.on('tick', scheduleRender);
        }

        return () => {
            simulation.on('tick', null);
            simulation.stop();
            if (frameRef.current) {
                window.cancelAnimationFrame(frameRef.current);
                frameRef.current = null;
            }
        };
    }, [
        nodes,
        links,
        width,
        height,
        centerX,
        centerY,
        chargeScale,
        linkStrengthScale,
        linkDistanceScale,
        scheduleRender
    ]);

    const reheat = useCallback((target = RESCORE_ALPHA_TARGET) => {
        const simulation = simulationRef.current;
        if (!simulation || prefersReducedMotion()) return;
        simulation.alphaTarget(target).restart();
        window.setTimeout(() => simulation.alphaTarget(0), 1200);
    }, []);

    const dragStart = useCallback((id) => {
        const simulation = simulationRef.current;
        const node = datumRef.current.nodes.find((candidate) => candidate.id === id);
        if (!simulation || !node) return;
        node.fx = node.x;
        node.fy = node.y;
        simulation.alphaTarget(DRAG_ALPHA_TARGET).restart();
    }, []);

    const dragMove = useCallback(
        (id, x, y) => {
            const node = datumRef.current.nodes.find((candidate) => candidate.id === id);
            if (!node) return;
            node.fx = x;
            node.fy = y;
            node.x = x;
            node.y = y;
            // Drag feedback must not depend on the simulation ticking: it is paused under
            // reduced motion and suspended entirely while the tab is hidden.
            scheduleRender();
        },
        [scheduleRender]
    );

    const dragEnd = useCallback(
        (id) => {
            const simulation = simulationRef.current;
            const node = datumRef.current.nodes.find((candidate) => candidate.id === id);
            simulation?.alphaTarget(0);
            if (!node) return;
            pinsRef.current = { ...pinsRef.current, [id]: { x: node.fx, y: node.fy } };
            writePins(projectId, pinsRef.current);
            setPinnedIds(Object.keys(pinsRef.current));
        },
        [projectId]
    );

    const unpin = useCallback(
        (id) => {
            const node = datumRef.current.nodes.find((candidate) => candidate.id === id);
            if (node) {
                node.fx = null;
                node.fy = null;
            }
            const next = { ...pinsRef.current };
            delete next[id];
            pinsRef.current = next;
            writePins(projectId, next);
            setPinnedIds(Object.keys(next));
            reheat();
        },
        [projectId, reheat]
    );

    const resetLayout = useCallback(() => {
        datumRef.current.nodes.forEach((node) => {
            node.fx = null;
            node.fy = null;
        });
        pinsRef.current = {};
        writePins(projectId, {});
        setPinnedIds([]);
        reheat(DRAG_ALPHA_TARGET);
    }, [projectId, reheat]);

    return {
        tick,
        nodes: datumRef.current.nodes,
        links: datumRef.current.links,
        pinnedIds,
        dragStart,
        dragMove,
        dragEnd,
        unpin,
        resetLayout
    };
}
