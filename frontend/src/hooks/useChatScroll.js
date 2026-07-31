import { useCallback, useEffect, useRef } from 'react';

// A user who has scrolled up is reading something; yanking them back to the newest message
// would be worse than not following it. Anything within this many pixels of the bottom
// counts as "still at the bottom", which covers sub-pixel rounding and momentum scrolling.
const BOTTOM_SLACK = 56;

/**
 * Keeps a scroll container pinned to its newest content while the user is at the bottom.
 *
 * `signals` is whatever changes as content grows - the message list, the length of the
 * reply being revealed, the pending-reply flag. Every change re-pins.
 */
export default function useChatScroll(signals) {
    const containerRef = useRef(null);
    const stickToBottomRef = useRef(true);

    const isAtBottom = useCallback(() => {
        const element = containerRef.current;
        if (!element) return true;
        const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
        return distance <= BOTTOM_SLACK;
    }, []);

    const scrollToBottom = useCallback((behavior = 'auto') => {
        const element = containerRef.current;
        if (!element) return;
        stickToBottomRef.current = true;
        element.scrollTo({ top: element.scrollHeight, behavior });
    }, []);

    useEffect(() => {
        const element = containerRef.current;
        if (!element) return undefined;

        const onScroll = () => {
            stickToBottomRef.current = isAtBottom();
        };
        element.addEventListener('scroll', onScroll, { passive: true });
        return () => element.removeEventListener('scroll', onScroll);
    }, [isAtBottom]);

    useEffect(() => {
        const element = containerRef.current;
        if (!element || !stickToBottomRef.current) return;
        // Straight assignment, not scrollTo with smooth: this fires on every revealed chunk,
        // and overlapping smooth animations fight each other and visibly stutter.
        element.scrollTop = element.scrollHeight;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, signals);

    return { containerRef, scrollToBottom, isAtBottom };
}
