import { useCallback, useEffect, useMemo, useState } from 'react';

/**
 * The project rewound to a moment in its own history.
 *
 * The graph draws whatever node list it is handed, and `deriveGraph` drops any link whose other
 * end is missing - so rewinding is only a matter of handing it fewer nodes. A link disappears
 * exactly when the newer of the two nodes it joins does, which is also when it was created, so
 * the connections unwind correctly without being modelled at all.
 *
 * Position is an index into creation order rather than a timestamp: two nodes created in the
 * same second would otherwise appear together and a step would sometimes add nothing. One step,
 * one node.
 */

// Slow enough to read the header of the node that just appeared, fast enough that a project
// with thirty nodes does not take half a minute to replay.
const PLAY_STEP_MS = 620;

const nodeId = (node) => {
    const raw = node?.id || node?._id;
    if (!raw) return '';
    if (typeof raw === 'string') return raw;
    return String(raw.$oid || raw);
};

const createdAt = (node) => {
    const raw = node?.created_at || node?.createdAt;
    if (!raw) return 0;
    // Mongo hands back a naive UTC string; without the marker the browser reads it as local
    // time, which shifts every date in the readout by the viewer's offset.
    const text =
        typeof raw === 'string' && !raw.endsWith('Z') && !raw.includes('+') ? `${raw}Z` : raw;
    const parsed = new Date(text).getTime();
    return Number.isNaN(parsed) ? 0 : parsed;
};

export function useTimeMachine(contextNodes) {
    // Oldest first. A node with no date sorts first: it predates the field, so it predates
    // everything that has one.
    const ordered = useMemo(() => {
        const source = Array.isArray(contextNodes) ? contextNodes : [];
        return source
            .filter((node) => nodeId(node))
            .map((node) => ({ id: nodeId(node), at: createdAt(node) }))
            .sort((left, right) => left.at - right.at);
    }, [contextNodes]);

    const total = ordered.length;
    // null means live: the present, and it keeps up as new nodes arrive.
    const [step, setStep] = useState(null);
    const [isPlaying, setIsPlaying] = useState(false);

    const isLive = step === null || step >= total;

    const goLive = useCallback(() => {
        setStep(null);
        setIsPlaying(false);
    }, []);

    // A project that shrank - a node deleted while rewound - must not leave the scrubber
    // pointing past the end, which would read as live while showing a stale list.
    useEffect(() => {
        setStep((current) => (current !== null && current > total ? total : current));
    }, [total]);

    useEffect(() => {
        if (!isPlaying) return undefined;

        const timer = window.setInterval(() => {
            setStep((current) => {
                const next = (current === null ? 0 : current) + 1;
                if (next >= total) {
                    setIsPlaying(false);
                    // Ends live rather than at the last step, so playback finishes in the
                    // present instead of in a frozen copy of it.
                    return null;
                }
                return next;
            });
        }, PLAY_STEP_MS);

        return () => window.clearInterval(timer);
    }, [isPlaying, total]);

    const play = useCallback(() => {
        if (total < 2) return;
        // Replaying from the present means starting over, which is what the button is for
        // once the graph has caught up with itself.
        setStep((current) => (current === null || current >= total ? 0 : current));
        setIsPlaying(true);
    }, [total]);

    const pause = useCallback(() => setIsPlaying(false), []);

    const scrubTo = useCallback(
        (value) => {
            setIsPlaying(false);
            setStep(value >= total ? null : Math.max(0, value));
        },
        [total]
    );

    const visibleIds = useMemo(() => {
        if (isLive) return null;
        return new Set(ordered.slice(0, step).map((entry) => entry.id));
    }, [isLive, ordered, step]);

    const visibleNodes = useMemo(() => {
        if (!visibleIds) return contextNodes;
        return (contextNodes || []).filter((node) => visibleIds.has(nodeId(node)));
    }, [contextNodes, visibleIds]);

    // The moment on screen: the creation time of the newest node still standing.
    const at = useMemo(() => {
        if (isLive) return null;
        const last = ordered[step - 1];
        return last?.at || null;
    }, [isLive, ordered, step]);

    return {
        total,
        step: isLive ? total : step,
        at,
        isLive,
        isPlaying,
        visibleNodes,
        play,
        pause,
        scrubTo,
        goLive
    };
}
