// Reel 2 «درب اليوم» (v2_road) — don't know where to start? Three small
// stops on a paper road: today's step, ask Almorabbi, the child's mission.
// Each stop turns gold as Noor hops on to the next; the sky goes from dawn
// to night.
import React, {useMemo} from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../palette';
import {LanternG} from '../art';
import {hillD, P, Road} from '../geometry';
import {
	blinkEyes,
	Caption,
	Chip,
	eased,
	EndCard,
	fadeRise,
	H,
	hop,
	Noor,
	Paper,
	SafeZones,
	SkySheet,
	springAt,
	Stars,
	Sun,
	txt,
	W,
	Watermark,
} from './kit';
import {Cue, endCues, ReelSound} from './sound';
import {V2} from './copy';

export const V2_TOTAL = 600;
const FROM = 450;

const FAR: P[] = [
	[-200, 640],
	[200, 604],
	[560, 652],
	[900, 612],
	[1280, 642],
];
const MAIN: P[] = [
	[-200, 700],
	[300, 672],
	[700, 712],
	[1280, 684],
];
const FRONT: P[] = [
	[-200, 1566],
	[300, 1522],
	[560, 1504],
	[820, 1524],
	[1280, 1492],
];

const STATIONS = [
	{x: 300, y: 1290, side: 1, noor: [150, 1334] as [number, number]},
	{x: 640, y: 1010, side: -1, noor: [792, 1054] as [number, number]},
	{x: 330, y: 744, side: 1, noor: [168, 788] as [number, number]},
];
const START: [number, number] = [470, 1330]; // the hook: big, in the middle, among the topics
const START_SIZE = 420;
const NOOR_SIZE = 320;

// «so many topics…» — chips that float round Noor in the hook
const TOPICS: {x: number; y: number; r: number}[] = [
	{x: 250, y: 760, r: -6},
	{x: 700, y: 800, r: 5},
	{x: 200, y: 990, r: 4},
	{x: 760, y: 1040, r: -4},
	{x: 220, y: 1220, r: -3},
	{x: 760, y: 1270, r: 6},
];

// frames
const T = {
	hook: [3, 88],
	look: [24, 32, 42, 52, 60, 66],
	rise: 4,
	topics: [8, 70], // pop in one by one, fold away
	// road reaches each stop, Noor hops there, the stop turns gold, the sky turns
	road: [
		[64, 96],
		[162, 194],
		[258, 290],
	],
	hops: [100, 198, 294],
	hopLen: 20,
	sky: [134, 230, 326],
	roadEnd: [328, 352],
	lanterns: [354, 366, 378, 390],
	message: 360,
};

export const V2Road: React.FC<{safe?: boolean}> = ({safe = false}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	const road = useMemo(
		() =>
			new Road([
				{x: 470, y: 1990, w: 210},
				{x: 410, y: 1620, w: 168},
				{x: 300, y: 1290, w: 140},
				{x: 470, y: 1140, w: 122},
				{x: 640, y: 1010, w: 106},
				{x: 520, y: 872, w: 92},
				{x: 330, y: 744, w: 80},
				{x: 290, y: 672, w: 64},
				{x: 350, y: 610, w: 52},
			]),
		[],
	);
	// arc-length position of each stop on the road
	const stopT = useMemo(
		() =>
			STATIONS.map((s) => {
				let best = 0;
				let bd = Infinity;
				for (const p of road.samples) {
					const d = Math.hypot(p.x - s.x, p.y - s.y);
					if (d < bd) {
						bd = d;
						best = p.t;
					}
				}
				return best;
			}),
		[road],
	);
	const paths = useMemo(() => ({far: hillD(FAR, H + 900), main: hillD(MAIN, H + 900), front: hillD(FRONT, H + 900)}), []);

	// road reveal: unrolls to each stop in turn, then over the last hill
	let roadP = 0;
	const segs: [number, number, number, number][] = [
		[T.road[0][0], T.road[0][1], 0, stopT[0]],
		[T.road[1][0], T.road[1][1], stopT[0], stopT[1]],
		[T.road[2][0], T.road[2][1], stopT[1], stopT[2]],
		[T.roadEnd[0], T.roadEnd[1], stopT[2], 1],
	];
	for (const [a, b, p0, p1] of segs) if (frame >= a) roadP = p0 + (p1 - p0) * eased(frame, a, b, Easing.inOut(Easing.sin));

	const slide = (at: number, dist: number) => dist * (1 - springAt(frame, at, fps, 12, 80));

	// ── Noor ─────────────────────────────────────────────────────────────────
	const rise = springAt(frame, T.rise, fps, 11, 80);
	let pos: [number, number] = [START[0], START[1] + 420 * (1 - rise)];
	let size = START_SIZE;
	let squash = 0;
	let hopping = false;
	const spots = [START, ...STATIONS.map((s) => s.noor)];
	for (let i = 0; i < 3; i++) {
		const a = T.hops[i];
		const b = a + T.hopLen;
		if (frame >= a) {
			const h = hop(frame, a, b, spots[i], spots[i + 1], 190);
			pos = [h.x, h.y];
			if (i === 0) size = START_SIZE + (NOOR_SIZE - START_SIZE) * h.p;
			hopping = frame < b;
			if (frame >= b) squash = (1 - springAt(frame, b, fps, 7, 220)) * 0.12;
		}
	}
	const look = (() => {
		const [a, b, c, d, e, f] = T.look;
		return interpolate(frame, [a, b, c, d, e, f], [0, -1, -1, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	})();
	const done = (i: number) => T.hops[i] + T.hopLen;
	let eyes = blinkEyes(frame, 'open', [140, 250]);
	let mouth: 'smile' | 'open' | 'calm' = 'smile';
	let sparkles = 0;
	if (frame < 76 && frame > 24) mouth = 'calm';
	if (hopping) {
		eyes = 'happy';
		mouth = 'open';
	}
	for (let i = 0; i < 3; i++) {
		if (frame >= done(i) && frame < done(i) + 22) {
			eyes = 'happy';
			mouth = 'open';
			sparkles = springAt(frame, done(i) + 1, fps, 9, 160) * (1 - eased(frame, done(i) + 16, done(i) + 22));
		}
	}
	if (frame >= T.lanterns[0]) {
		eyes = blinkEyes(frame, 'happy', []);
		mouth = 'open';
		sparkles = springAt(frame, T.lanterns[0], fps, 9, 160);
	}
	const pose = {cx: pos[0], by: pos[1], size};

	// ── lanterns along the road at night ─────────────────────────────────────
	const lanternSpots = [0.13, 0.39, 0.56, 0.8].map((t, i) => {
		const s = road.at(t);
		const side = i % 2 === 0 ? 1 : -1;
		const off = s.w / 2 + 40;
		return {x: s.x + side * s.nx * off, y: s.y + side * s.ny * off, size: 140 - i * 14};
	});

	const cues: Cue[] = [
		{file: 'rustle', at: 0, vol: 0.45},
		{file: 'rustle', at: T.rise, vol: 0.35},
		...TOPICS.map((_, i) => ({file: 'tick' as const, at: T.topics[0] + i * 4, vol: 0.28})),
		{file: 'air', at: T.topics[1], vol: 0.45},
		...T.road.map(([a]) => ({file: 'rustle_long' as const, at: a, vol: 0.5})),
		...T.hops.map((a) => ({file: 'air' as const, at: a, vol: 0.3})),
		...[0, 1, 2].map((i) => ({file: 'drop' as const, at: done(i) + 1, vol: 0.5})),
		...[0, 1, 2].map((i) => ({file: 'tick' as const, at: done(i) + 4, vol: 0.35})),
		...T.sky.map((a) => ({file: 'rustle' as const, at: a, vol: 0.5})),
		{file: 'rustle_long', at: T.roadEnd[0], vol: 0.4},
		...T.lanterns.map((a, i) => ({file: 'air' as const, at: a + 4, vol: 0.5 - i * 0.05})),
		...endCues(FROM),
	];

	return (
		<AbsoluteFill style={{background: C.ivory3, overflow: 'hidden'}}>
			{/* dawn, then a new paper sky at each stop */}
			<Sun x={900} y={740 - 140 * eased(frame, 0, 50, Easing.out(Easing.cubic))} r={70} />
			<SkySheet color={C.ivory2} frame={frame} fps={fps} at={T.sky[0]}>
				<Sun x={790} y={440} r={84} />
			</SkySheet>
			<SkySheet color={C.coral} frame={frame} fps={fps} at={T.sky[1]}>
				<Sun x={840} y={590} r={90} />
			</SkySheet>
			<SkySheet color={C.emerald} frame={frame} fps={fps} at={T.sky[2]}>
				<Stars frame={frame} fps={fps} at={T.sky[2] + 4} skip={(s) => s.y > 640} />
			</SkySheet>

			{/* the far hill, the main hill with the road, lanterns and the stops */}
			<svg
				width={W}
				height={H}
				style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', transform: `translateY(${slide(0, 500)}px)`}}
			>
				<path d={paths.far} fill={C.hill2} />
			</svg>
			<svg
				width={W}
				height={H}
				style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', transform: `translateY(${slide(4, 900)}px)`}}
			>
				<defs>
					<clipPath id="v2-main">
						<path d={paths.main} />
					</clipPath>
				</defs>
				<path d={paths.main} fill={C.hill3} />
				<g clipPath="url(#v2-main)">
					<path d={road.outline(roadP)} fill={C.shadow} transform="translate(7 9)" />
					<path d={road.outline(roadP)} fill={C.ivory} />
				</g>
				{lanternSpots.map((l, i) => (
					<LanternG
						key={i}
						x={l.x}
						y={l.y}
						size={l.size}
						pop={springAt(frame, T.lanterns[i] - 6, fps, 10, 160)}
						flame={springAt(frame, T.lanterns[i], fps, 9, 150)}
						glow={springAt(frame, T.lanterns[i] + 3, fps, 18, 70)}
						flicker={0.6 * Math.sin(frame * 0.33 + i * 1.7) + 0.4 * Math.sin(frame * 0.13 + i)}
					/>
				))}
				{STATIONS.map((s, i) => {
					const reach = T.road[i][1] - 4;
					const pop = springAt(frame, reach, fps, 10, 170);
					if (pop <= 0.001) return null;
					const gold = frame >= done(i);
					const bump = gold ? 1 + 0.12 * Math.sin(Math.PI * Math.min(1, (frame - done(i)) / 10)) : 1;
					return (
						<g key={i} transform={`translate(${s.x} ${s.y}) scale(${pop * bump})`}>
							<circle cx={7} cy={9} r={66} fill={C.shadow} />
							<circle r={66} fill={C.emerald} />
							<circle r={54} fill={gold ? C.gold : C.ivory2} />
							<text y={22} textAnchor="middle" style={{fontFamily: txt().fontFamily, fontWeight: 900, fontSize: 66}} fill={C.ink}>
								{V2.stations[i].n}
							</text>
						</g>
					);
				})}
			</svg>
			<svg
				width={W}
				height={H}
				style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', transform: `translateY(${slide(9, 600)}px)`}}
			>
				<path d={paths.front} fill={C.shadow} />
			</svg>

			{/* labels beside each stop */}
			{STATIONS.map((s, i) => {
				const at = done(i) + 2;
				const sc = springAt(frame, at, fps, 11, 170);
				if (sc <= 0.001) return null;
				const left = s.side === 1 ? s.x + 100 : 70;
				const width = s.side === 1 ? 880 - left : s.x - 100 - 70;
				return (
					<div
						key={i}
						style={{
							position: 'absolute',
							left,
							top: s.y - 78,
							width,
							transform: `scale(${sc})`,
							transformOrigin: s.side === 1 ? '0% 50%' : '100% 50%',
						}}
					>
						<Paper radius={28} off={10} style={{padding: '14px 26px 18px'}}>
							<p style={txt({fontWeight: 900, fontSize: 48, lineHeight: 1.35, color: C.ink})}>{V2.stations[i].title}</p>
							<p style={txt({fontWeight: 700, fontSize: 37, lineHeight: 1.35, color: C.emerald})}>{V2.stations[i].sub}</p>
						</Paper>
					</div>
				);
			})}

			{/* the hook: too many topics, no idea where to begin */}
			{TOPICS.map((tp, i) => {
				const sc =
					springAt(frame, T.topics[0] + i * 4, fps, 10, 170) *
					(1 - eased(frame, T.topics[1] + i * 2, T.topics[1] + i * 2 + 10, Easing.in(Easing.cubic)));
				if (sc <= 0.001) return null;
				const bob = Math.sin(frame * 0.09 + i * 1.3) * 8;
				return (
					<div
						key={i}
						style={{position: 'absolute', left: tp.x, top: tp.y + bob, transform: `translate(-50%, -50%) rotate(${tp.r}deg) scale(${sc})`}}
					>
						<Chip label={V2.topics[i]} font={44} />
					</div>
				);
			})}

			{frame >= T.rise && frame < FROM && (
				<Noor frame={frame} {...pose} eyes={eyes} mouth={mouth} look={look} tilt={look * 5} sparkles={sparkles} squash={squash} />
			)}

			<Caption lines={V2.hook} top={300} font={96} color={C.ink} style={fadeRise(frame, T.hook[0], fps, 30, T.hook[1])} />
			<Caption lines={V2.message} top={300} font={84} style={fadeRise(frame, T.message, fps, 30, FROM - 4)} />

			<EndCard frame={frame} fps={fps} from={FROM} slug="v2_road" tagline={V2.tagline} noorFrom={pose} />
			<Watermark frame={frame} fps={fps} hideAt={FROM} />
			{safe ? <SafeZones /> : null}
			<ReelSound cues={cues} total={V2_TOTAL} gain={1.13} />
		</AbsoluteFill>
	);
};
