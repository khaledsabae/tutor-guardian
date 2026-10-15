// Reel 5 «شارع القناديل» (v5_ramadan) — this Ramadan is different: thirty
// paper lanterns strung across a street, lit one after another each time the
// family does something together. Quietly: no counters, no blame, and no
// religious text on screen.
import React from 'react';
import {AbsoluteFill, Easing, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../palette';
import {LanternG, WalkersG} from '../art';
import {star8} from '../geometry';
import {
	blinkEyes,
	Caption,
	CX,
	eased,
	EndCard,
	fadeRise,
	H,
	Noor,
	noorHead,
	Paper,
	SafeZones,
	showFor,
	springAt,
	Stars,
	txt,
	W,
	Watermark,
} from './kit';
import {Cue, endCues, ReelSound} from './sound';
import {V5} from './copy';

export const V5_TOTAL = 615;
const FROM = 465;

const ROWS = [
	{y0: 600, sag: 64, at: 2},
	{y0: 810, sag: 70, at: 7},
	{y0: 1020, sag: 76, at: 12},
];
const PER_ROW = 10;
const LANTERN = 124;
const ropeY = (r: number, x: number) => ROWS[r].y0 + ROWS[r].sag * (1 - ((x - 540) / 560) ** 2);
// Right to left, row by row: the first lantern is top right.
const lanternX = (j: number) => 862 - j * 86.4;

const T = {
	hook: [3, 84],
	houses: 0,
	noorRise: 16,
	moments: [92, 150, 208, 266], // each card; its lantern is lit 18 frames later
	litDelay: 18,
	dayByDay: [330, 392],
	ripple: 340, // lanterns 5 … 30
	rippleStep: 3.6,
	message: 400,
	walk: [100, 380],
};

// Each string unrolls from right to left (it never crosses the hook words);
// a lantern pops onto it as the string reaches it.
const UNROLL = 24;
const ropeEdge = (frame: number, at: number) => 1100 - 1130 * Math.min(1, Math.max(0, (frame - at) / UNROLL));
const reachAt = (at: number, x: number) => at + (UNROLL * (1100 - x)) / 1130;

const litAt = (k: number) => (k < 4 ? T.moments[k] + T.litDelay : T.ripple + (k - 4) * T.rippleStep);

const NOOR = {cx: 200, by: 1500, size: 360};

// Sound cues (source frames); exported so the voice-over cut can retime and duck them.
export const V5_CUES: Cue[] = [
	{file: 'rustle', at: T.houses, vol: 0.45},
	...ROWS.map((r) => ({file: 'rustle' as const, at: r.at, vol: 0.45})),
	{file: 'rustle', at: T.noorRise, vol: 0.3},
	...T.moments.map((a) => ({file: 'rustle' as const, at: a, vol: 0.4})),
	...[0, 1, 2, 3].map((k) => ({file: 'air' as const, at: litAt(k) - 14, vol: 0.3})),
	...[0, 1, 2, 3].map((k) => ({file: 'drop' as const, at: litAt(k), vol: 0.45})),
	{file: 'rustle', at: T.dayByDay[0], vol: 0.35},
	...Array.from({length: 26}, (_, i) => i)
		.filter((i) => i % 4 === 0)
		.map((i) => ({file: 'air' as const, at: litAt(4 + i), vol: 0.32})),
	{file: 'drop', at: T.ripple + 104, vol: 0.5},
	...endCues(FROM),
];

/** Mix trim of this reel (lands the silent cut near -23 LUFS). */
export const V5_GAIN = 1.14;

export const V5Ramadan: React.FC<{safe?: boolean}> = ({safe = false}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	// ── Noor ─────────────────────────────────────────────────────────────────
	const rise = springAt(frame, T.noorRise, fps, 11, 80);
	let by = NOOR.by + 420 * (1 - rise);
	let eyes = blinkEyes(frame, 'open', [70, 250]);
	let mouth: 'smile' | 'calm' | 'open' = 'smile';
	let sparkles = 0;
	let tilt = 0;
	// looks up at the strings as they drop
	tilt = -8 * eased(frame, 30, 44) * (1 - eased(frame, 76, 90));
	for (let k = 0; k < 4; k++) {
		const a = litAt(k);
		if (frame >= a && frame < a + 24) {
			eyes = 'happy';
			mouth = 'open';
			sparkles = springAt(frame, a + 1, fps, 9, 160) * (1 - eased(frame, a + 16, a + 24));
		}
	}
	if (frame >= T.ripple + 30) {
		eyes = 'happy';
		mouth = 'open';
		sparkles = springAt(frame, T.ripple + 30, fps, 9, 160);
		const h = frame - (T.ripple + 104);
		if (h >= 0 && h < 16) by -= Math.sin((Math.PI * h) / 16) * 44;
	}
	const pose = {cx: NOOR.cx, by, size: NOOR.size};
	const head = noorHead({cx: NOOR.cx, by: NOOR.by, size: NOOR.size});

	// ── lanterns ─────────────────────────────────────────────────────────────
	const lanterns = ROWS.flatMap((row, r) =>
		Array.from({length: PER_ROW}, (_, j) => {
			const k = r * PER_ROW + j;
			const x = lanternX(j);
			const y = ropeY(r, x);
			const a = litAt(k);
			const reach = reachAt(row.at, x);
			// a swing that settles once it pops on, then a slow breeze
			const settle = Math.exp(-Math.max(0, frame - reach) / 22);
			const sway = 9 * settle * Math.sin((frame - reach) * 0.35 + j) + 1.6 * Math.sin(frame * 0.05 + k * 0.7);
			return {
				k,
				x,
				y,
				sway,
				pop: springAt(frame, reach, fps, 10, 160),
				flame: springAt(frame, a, fps, 9, 150),
				glow: springAt(frame, a + 3, fps, 18, 70),
				flicker: 0.6 * Math.sin(frame * 0.33 + k * 1.7) + 0.4 * Math.sin(frame * 0.13 + k),
			};
		}),
	);

	// the spark Noor sends to each of the first four lanterns
	const sparks = [0, 1, 2, 3].map((k) => {
		const a = litAt(k) - 14;
		const p = eased(frame, a, a + 14, Easing.inOut(Easing.quad));
		if (frame < a || frame >= a + 14) return null;
		const L = lanterns[k];
		const tx = L.x;
		const ty = L.y + 60;
		const x = head.x + (tx - head.x) * p;
		const y = head.y + (ty - head.y) * p - Math.sin(Math.PI * p) * 160;
		return {x, y};
	});

	// ── the family walks down the street ─────────────────────────────────────
	const walkE = eased(frame, T.walk[0], T.walk[1], Easing.inOut(Easing.sin));
	const walking = frame > T.walk[0] && frame < T.walk[1];
	const phase = walkE * 22 * Math.PI;
	const famX = 760 - 300 * walkE;
	const famPop = springAt(frame, T.walk[0] - 10, fps, 11, 150);

	return (
		<AbsoluteFill style={{background: C.emerald, overflow: 'hidden'}}>
			<Stars frame={frame} fps={fps} skip={(s) => s.y > 560} />
			<Houses frame={frame} fps={fps} />

			{/* three strings of ten paper lanterns */}
			<svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
				{ROWS.map((row, r) => {
					const edge = ropeEdge(frame, row.at);
					if (edge >= 1100) return null;
					const xs = [edge, ...Array.from({length: 23}, (_, i) => -20 + i * 52).filter((x) => x > edge)];
					const pts = xs.map((x) => `${x.toFixed(1)},${ropeY(r, x).toFixed(1)}`).join(' ');
					return (
						<g key={r}>
							<polyline points={pts} fill="none" stroke={C.shadow} strokeWidth={6} transform="translate(3 5)" />
							<polyline points={pts} fill="none" stroke={C.ivory3} strokeWidth={5} strokeLinejoin="round" />
							{lanterns
								.filter((l) => Math.floor(l.k / PER_ROW) === r)
								.map((l) => {
									const u = LANTERN / 48;
									const hang = 26;
									if (l.pop <= 0.001) return null;
									return (
										<g key={l.k} transform={`rotate(${l.sway} ${l.x} ${l.y})`}>
											<line x1={l.x} y1={l.y} x2={l.x} y2={l.y + hang} stroke={C.ivory3} strokeWidth={3} />
											<LanternG
												x={l.x}
												y={l.y + hang + (43.5 - 5) * u}
												size={LANTERN}
												pop={l.pop}
												flame={l.flame}
												glow={l.glow}
												flicker={l.flicker}
											/>
										</g>
									);
								})}
						</g>
					);
				})}
				{sparks.map((s, i) =>
					s ? (
						<g key={i}>
							<polygon points={star8(s.x + 3, s.y + 4, 22)} fill={C.shadow} />
							<polygon points={star8(s.x, s.y, 22)} fill={C.gold} />
						</g>
					) : null,
				)}
			</svg>

			{/* the family */}
			{famPop > 0.001 && frame < FROM && (
				<svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
					<WalkersG
						x={famX}
						y={1512}
						size={300}
						mirror
						pop={famPop}
						stepA={walking ? Math.abs(Math.sin(phase)) * 2.4 : 0}
						stepB={walking ? Math.abs(Math.sin(phase + Math.PI / 2)) * 3 : 0}
						swayA={walking ? Math.sin(phase) * 1.3 : 0}
						swayB={walking ? Math.sin(phase + Math.PI / 2) * 1.8 : 0}
					/>
				</svg>
			)}

			{frame >= T.noorRise && frame < FROM && <Noor frame={frame} {...pose} eyes={eyes} mouth={mouth} tilt={tilt} sparkles={sparkles} />}

			{/* the street, in front */}
			<svg
				width={W}
				height={H}
				style={{position: 'absolute', left: 0, top: 0, transform: `translateY(${500 * (1 - springAt(frame, 4, fps, 12, 80))}px)`}}
			>
				<path d={`M-20 1508 Q540 1490 1100 1508 L1100 ${H + 20} L-20 ${H + 20} Z`} fill={C.shadow} />
				<path d={`M-20 1600 Q540 1586 1100 1600 L1100 ${H + 20} L-20 ${H + 20} Z`} fill={C.ink} />
			</svg>

			{/* what the family did together — one card at a time */}
			{T.moments.map((a, i) => {
				const b = (T.moments[i + 1] ?? T.dayByDay[0]) - 6;
				const s = showFor(frame, a, b, fps, 8, 12, 150);
				if (s <= 0.001) return null;
				return (
					<div
						key={i}
						style={{
							position: 'absolute',
							left: CX - 380,
							top: 330,
							width: 760,
							display: 'flex',
							justifyContent: 'center',
							transform: `scale(${s})`,
						}}
					>
						<Paper radius={30} style={{padding: '16px 44px 22px'}}>
							<p style={txt({fontWeight: 900, fontSize: 64, lineHeight: 1.4, color: C.ink})}>{V5.moments[i]}</p>
						</Paper>
					</div>
				);
			})}

			<Caption lines={V5.hook} top={296} font={90} style={fadeRise(frame, T.hook[0], fps, 30, T.hook[1])} />
			<Caption lines={[V5.dayByDay]} top={330} font={76} style={fadeRise(frame, T.dayByDay[0], fps, 24, T.dayByDay[1])} />
			<Caption lines={V5.message} top={296} font={84} style={fadeRise(frame, T.message, fps, 30, FROM - 4)} />

			<EndCard frame={frame} fps={fps} from={FROM} slug="v5_ramadan" tagline={V5.tagline} noorFrom={pose} />
			<Watermark frame={frame} fps={fps} hideAt={FROM} />
			{safe ? <SafeZones /> : null}
			<ReelSound cues={V5_CUES} total={V5_TOTAL} gain={V5_GAIN} />
		</AbsoluteFill>
	);
};

/** A row of paper houses behind the street, with warm arched windows. */
const Houses: React.FC<{frame: number; fps: number}> = ({frame, fps}) => {
	const dy = 600 * (1 - springAt(frame, 0, fps, 12, 80));
	const houses = [
		{x: -10, w: 230, top: 1236, dome: true, color: C.hill3},
		{x: 210, w: 190, top: 1300, dome: false, color: C.hill2},
		{x: 390, w: 250, top: 1210, dome: true, color: C.hill3},
		{x: 630, w: 200, top: 1286, dome: false, color: C.hill2},
		{x: 820, w: 290, top: 1226, dome: true, color: C.hill3},
	];
	const win = (x: number, y: number, w: number, h: number, lit: boolean, key: string) => (
		<path
			key={key}
			d={`M${x} ${y + h} V${y + w / 2} A${w / 2} ${w / 2} 0 0 1 ${x + w} ${y + w / 2} V${y + h} Z`}
			fill={lit ? C.gold : C.shadow}
		/>
	);
	return (
		<svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', transform: `translateY(${dy}px)`}}>
			{houses.map((h, i) => {
				const dw = h.w * 0.5;
				const dx = h.x + (h.w - dw) / 2;
				return (
					<g key={i}>
						<g transform="translate(8 10)" fill={C.shadow}>
							<rect x={h.x} y={h.top} width={h.w} height={600} />
							{h.dome ? <path d={`M${dx} ${h.top} A${dw / 2} ${dw / 2} 0 0 1 ${dx + dw} ${h.top} Z`} /> : null}
						</g>
						<rect x={h.x} y={h.top} width={h.w} height={600} fill={h.color} />
						{h.dome ? <path d={`M${dx} ${h.top + 1} A${dw / 2} ${dw / 2} 0 0 1 ${dx + dw} ${h.top + 1} Z`} fill={h.color} /> : null}
						{!h.dome ? <rect x={h.x - 8} y={h.top - 14} width={h.w + 16} height={18} fill={h.color} /> : null}
						{win(h.x + h.w / 2 - 50, h.top + 60, 40, 74, i % 2 === 0, `a${i}`)}
						{win(h.x + h.w / 2 + 10, h.top + 60, 40, 74, i !== 1, `b${i}`)}
					</g>
				);
			})}
		</svg>
	);
};
