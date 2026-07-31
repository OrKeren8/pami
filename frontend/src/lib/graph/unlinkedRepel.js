// Inverse-linear rather than inverse-square: the job here is pushing unrelated clusters
// out of each other's space, and a 1/d² field is already negligible at the distances where
// that matters.
const REPEL_BASE = 20;
const MIN_DISTANCE = 60;
const MAX_PUSH = 0.2;

const pairKey = (left, right) => (left < right ? `${left}::${right}` : `${right}::${left}`);

// Repulsion between UNCONNECTED conversations only. d3's forceManyBody pushes every pair
// apart, which means a link has to win a tug of war against the very force separating the
// pair it is trying to bring together. Excluding linked pairs makes the link the only
// thing deciding how close two conversations sit, and leaves repulsion to do what it is
// actually for: keeping unrelated clusters out of each other's space.
export function unlinkedRepel(strength = 1) {
    let nodes = [];
    let linked = new Set();

    // Deliberately NOT alpha-scaled. An alpha-scaled repulsion has already faded to nothing
    // by the time the layout settles, so unconnected conversations end up wherever the link
    // forces happen to leave them. A persistent push gives them personal space, and the
    // per-tick clamp is what keeps that stable instead of explosive.
    function force() {
        const scale = REPEL_BASE * strength;
        if (!scale) return;

        for (let i = 0; i < nodes.length; i += 1) {
            const a = nodes[i];
            for (let j = i + 1; j < nodes.length; j += 1) {
                const b = nodes[j];
                if (linked.has(pairKey(a.id, b.id))) continue;

                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const distance = Math.max(Math.hypot(dx, dy), MIN_DISTANCE);
                const magnitude = Math.min(scale / distance, MAX_PUSH);
                const ux = dx / distance;
                const uy = dy / distance;

                a.vx -= ux * magnitude;
                a.vy -= uy * magnitude;
                b.vx += ux * magnitude;
                b.vy += uy * magnitude;
            }
        }
    }

    force.initialize = (next) => {
        nodes = next || [];
    };

    force.links = (nextLinks) => {
        linked = new Set(
            (nextLinks || []).map((link) =>
                pairKey(link.source.id ?? link.source, link.target.id ?? link.target)
            )
        );
        return force;
    };

    return force;
}
