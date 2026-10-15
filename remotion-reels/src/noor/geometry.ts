// Small geometry helpers: smooth hill outlines and a tapered "paper road"
// that can be revealed progressively (it unrolls, it never morphs).

export type P = [number, number];

/** Catmull-Rom through `pts`, written as SVG cubic Béziers (starts with M). */
export const smoothD = (pts: P[]): string => {
	if (pts.length < 2) return '';
	let d = `M${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
	for (let i = 0; i < pts.length - 1; i++) {
		const p0 = pts[Math.max(0, i - 1)];
		const p1 = pts[i];
		const p2 = pts[i + 1];
		const p3 = pts[Math.min(pts.length - 1, i + 2)];
		const c1: P = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
		const c2: P = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
		d += ` C${c1[0].toFixed(1)} ${c1[1].toFixed(1)} ${c2[0].toFixed(1)} ${c2[1].toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
	}
	return d;
};

/** A hill sheet: smooth crest through `crest`, closed far below the frame. */
export const hillD = (crest: P[], bottom: number): string => {
	const first = crest[0];
	const last = crest[crest.length - 1];
	return `${smoothD(crest)} L${last[0]} ${bottom} L${first[0]} ${bottom} Z`;
};

export type RoadCtrl = {x: number; y: number; w: number};
type Sample = {x: number; y: number; w: number; nx: number; ny: number; t: number};

const bez = (a: number, b: number, c: number, d: number, u: number) => {
	const v = 1 - u;
	return v * v * v * a + 3 * v * v * u * b + 3 * v * u * u * c + u * u * u * d;
};

const smoothstep = (u: number) => u * u * (3 - 2 * u);

/** A tapered ribbon along a Catmull-Rom centreline, parametrised by arc length. */
export class Road {
	samples: Sample[] = [];

	constructor(ctrl: RoadCtrl[], stepsPerSeg = 48) {
		const raw: {x: number; y: number; w: number}[] = [];
		for (let i = 0; i < ctrl.length - 1; i++) {
			const p0 = ctrl[Math.max(0, i - 1)];
			const p1 = ctrl[i];
			const p2 = ctrl[i + 1];
			const p3 = ctrl[Math.min(ctrl.length - 1, i + 2)];
			const c1x = p1.x + (p2.x - p0.x) / 6;
			const c1y = p1.y + (p2.y - p0.y) / 6;
			const c2x = p2.x - (p3.x - p1.x) / 6;
			const c2y = p2.y - (p3.y - p1.y) / 6;
			for (let s = 0; s < stepsPerSeg; s++) {
				const u = s / stepsPerSeg;
				raw.push({
					x: bez(p1.x, c1x, c2x, p2.x, u),
					y: bez(p1.y, c1y, c2y, p2.y, u),
					w: p1.w + (p2.w - p1.w) * smoothstep(u),
				});
			}
		}
		const end = ctrl[ctrl.length - 1];
		raw.push({x: end.x, y: end.y, w: end.w});

		let acc = 0;
		const lens = [0];
		for (let i = 1; i < raw.length; i++) {
			acc += Math.hypot(raw[i].x - raw[i - 1].x, raw[i].y - raw[i - 1].y);
			lens.push(acc);
		}
		this.samples = raw.map((r, i) => {
			const a = raw[Math.max(0, i - 1)];
			const b = raw[Math.min(raw.length - 1, i + 1)];
			const tx = b.x - a.x;
			const ty = b.y - a.y;
			const l = Math.hypot(tx, ty) || 1;
			return {...r, nx: -ty / l, ny: tx / l, t: lens[i] / acc};
		});
	}

	/** Point on the centreline at arc-length fraction t (0 = near end). */
	at(t: number): Sample {
		const s = this.samples;
		const tt = Math.min(1, Math.max(0, t));
		let lo = 0;
		let hi = s.length - 1;
		while (hi - lo > 1) {
			const mid = (lo + hi) >> 1;
			if (s[mid].t <= tt) lo = mid;
			else hi = mid;
		}
		const a = s[lo];
		const b = s[hi];
		const u = b.t === a.t ? 0 : (tt - a.t) / (b.t - a.t);
		const lerp = (x: number, y: number) => x + (y - x) * u;
		return {
			x: lerp(a.x, b.x),
			y: lerp(a.y, b.y),
			w: lerp(a.w, b.w),
			nx: lerp(a.nx, b.nx),
			ny: lerp(a.ny, b.ny),
			t: tt,
		};
	}

	/** Closed outline of the road from t=0 to t=p, with a softly rounded leading edge. */
	outline(p: number): string {
		if (p <= 0.001) return '';
		const pts = this.samples.filter((s) => s.t < p);
		pts.push(this.at(p));
		const left = pts.map((s) => [s.x + (s.nx * s.w) / 2, s.y + (s.ny * s.w) / 2]);
		const right = pts.map((s) => [s.x - (s.nx * s.w) / 2, s.y - (s.ny * s.w) / 2]);
		const tip = pts[pts.length - 1];
		// Leading edge: a shallow curve (a paper strip being unrolled), not a
		// full half circle, which on a wide strip reads as a blob.
		const cap: number[][] = [];
		const r = tip.w / 2;
		const depth = r * 0.35;
		const tx = tip.ny; // tangent = normal rotated
		const ty = -tip.nx;
		for (let k = 1; k < 12; k++) {
			const a = (Math.PI * k) / 12;
			const cx = Math.cos(a);
			const sx = Math.sin(a);
			cap.push([tip.x + r * tip.nx * cx + depth * tx * sx, tip.y + r * tip.ny * cx + depth * ty * sx]);
		}
		const all = [...left, ...cap, ...right.reverse()];
		return 'M' + all.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L') + ' Z';
	}
}

/** Eight-point star polygon points (outer radius r, inner = 0.6 r). */
export const star8 = (cx: number, cy: number, r: number): string => {
	const out: string[] = [];
	for (let i = 0; i < 16; i++) {
		const a = -Math.PI / 2 + (i * Math.PI) / 8;
		const rr = i % 2 === 0 ? r : r * 0.6;
		out.push(`${(cx + rr * Math.cos(a)).toFixed(1)},${(cy + rr * Math.sin(a)).toFixed(1)}`);
	}
	return out.join(' ');
};
