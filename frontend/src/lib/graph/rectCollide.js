import { quadtree } from 'd3-quadtree';

const MAX_PUSH = 9;

// Overlap resolution is geometric, not alpha-scaled: a settled layout must still keep
// pills apart, and alpha is ~0 by the time a layout settles.
export function rectCollide(padding = 8, strength = 0.7, iterations = 2) {
    let nodes = [];

    function force() {
        if (!nodes.length) return;
        for (let pass = 0; pass < iterations; pass += 1) resolve();
    }

    function resolve() {

        let maxHalfWidth = 0;
        let maxHalfHeight = 0;
        nodes.forEach((node) => {
            maxHalfWidth = Math.max(maxHalfWidth, node.w / 2);
            maxHalfHeight = Math.max(maxHalfHeight, node.h / 2);
        });

        const tree = quadtree(
            nodes,
            (d) => d.x,
            (d) => d.y
        );

        nodes.forEach((node) => {
            const halfWidth = node.w / 2 + padding;
            const halfHeight = node.h / 2 + padding;
            const reachX = halfWidth + maxHalfWidth;
            const reachY = halfHeight + maxHalfHeight;

            tree.visit((quad, x0, y0, x1, y1) => {
                if (!quad.length) {
                    let leaf = quad;
                    do {
                        const other = leaf.data;
                        if (other && other.index > node.index) {
                            separate(node, other, padding, strength);
                        }
                        leaf = leaf.next;
                    } while (leaf);
                    return false;
                }
                return (
                    x0 > node.x + reachX ||
                    x1 < node.x - reachX ||
                    y0 > node.y + reachY ||
                    y1 < node.y - reachY
                );
            });
        });
    }

    force.initialize = (next) => {
        nodes = next || [];
        nodes.forEach((node, index) => {
            node.index = index;
        });
    };

    return force;
}

function separate(a, b, padding, strength) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const minX = a.w / 2 + b.w / 2 + padding;
    const minY = a.h / 2 + b.h / 2 + padding;

    const overlapX = minX - Math.abs(dx);
    const overlapY = minY - Math.abs(dy);
    if (overlapX <= 0 || overlapY <= 0) return;

    const aFixed = a.fx !== null && a.fx !== undefined;
    const bFixed = b.fx !== null && b.fx !== undefined;
    if (aFixed && bFixed) return;

    const alongX = overlapX / minX < overlapY / minY;
    // Clamped: an unclamped kick on a 206px-wide pill is a ~200px/tick velocity, which
    // makes hub nodes oscillate against the link force instead of settling.
    const magnitude = Math.min((alongX ? overlapX : overlapY) * strength, MAX_PUSH);
    const direction = (alongX ? dx : dy) < 0 ? -1 : 1;

    const aShare = aFixed ? 0 : bFixed ? 1 : 0.5;
    const bShare = 1 - aShare;

    // Applied to velocity, like d3's own collide: the integrator runs after every force,
    // so a position nudge here would simply be overwritten by the link force's velocity.
    if (alongX) {
        a.vx -= magnitude * aShare * direction;
        b.vx += magnitude * bShare * direction;
    } else {
        a.vy -= magnitude * aShare * direction;
        b.vy += magnitude * bShare * direction;
    }
}
