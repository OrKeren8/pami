import { useCallback, useEffect, useRef, useState } from 'react';

// About 900 characters a second: fast enough that a long answer is not a wait, slow enough
// that the eye can follow where the text is coming from.
const CHARS_PER_MS = 0.9;

/**
 * Reveals a string progressively, paced by the clock rather than by render count.
 *
 * A timer-per-chunk version advanced only as fast as the surrounding component could
 * re-render - measured at 31 characters a second on this page, against the 500 it was
 * configured for. Deriving the count from elapsed time makes the duration the same
 * whatever a render costs: a slow frame reveals more characters, not fewer.
 *
 * Returns `null` when nothing is being revealed.
 */
export default function useRevealedText() {
    const [revealedChars, setRevealedChars] = useState(null);
    const startedAtRef = useRef(0);
    const totalRef = useRef(0);
    const frameRef = useRef(0);

    const stop = useCallback(() => {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = 0;
        setRevealedChars(null);
    }, []);

    const reveal = useCallback((total) => {
        cancelAnimationFrame(frameRef.current);
        if (!total) {
            setRevealedChars(null);
            return;
        }

        // Animation frames do not fire in a hidden tab. Without this the reply that arrived
        // while the user was elsewhere would sit as an empty bubble until they came back.
        if (typeof document !== 'undefined' && document.hidden) {
            setRevealedChars(null);
            return;
        }

        totalRef.current = total;
        startedAtRef.current = performance.now();
        setRevealedChars(0);

        const step = () => {
            const elapsed = performance.now() - startedAtRef.current;
            const shown = Math.min(totalRef.current, Math.ceil(elapsed * CHARS_PER_MS));
            setRevealedChars(shown);

            if (shown < totalRef.current) {
                frameRef.current = requestAnimationFrame(step);
            } else {
                frameRef.current = 0;
                // One more paint with the full text, then drop out of revealing state so the
                // caret and the held-back source chips resolve together.
                setRevealedChars(null);
            }
        };
        frameRef.current = requestAnimationFrame(step);
    }, []);

    useEffect(() => {
        // Same reason in reverse: leaving mid-reveal would freeze the text part-written.
        const onHidden = () => {
            if (document.hidden && frameRef.current) {
                cancelAnimationFrame(frameRef.current);
                frameRef.current = 0;
                setRevealedChars(null);
            }
        };
        document.addEventListener('visibilitychange', onHidden);
        return () => {
            document.removeEventListener('visibilitychange', onHidden);
            cancelAnimationFrame(frameRef.current);
        };
    }, []);

    return { revealedChars, reveal, stop };
}
