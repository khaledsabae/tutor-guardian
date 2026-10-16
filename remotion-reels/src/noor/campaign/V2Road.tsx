// Reel 2 «درب الأسرة» (v2_road) — don't know where to start? The family's
// own road, as the app draws it (#130 «درب {الاسم}»): from «من هنا بدأ
// دربكم» Noor walks the gold stretch the family has lit, a lantern for each
// step, to «أنتم هنا»; then the road runs on, unlit, to the gates «على
// الأفق» — the next path, Ramadan, the age of seven — under a sky that takes
// each season's paper touch (Rajab's stars, Sha'ban's bunting, the birds and
// tents of Dhu al-Hijjah).
import React, {useMemo} from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../palette';
import {LanternG} from '../art';
import {hillD, P, star8} from '../geometry';
import {
	blinkEyes,
	Caption,
	Chip,
	eased,
	EndCard,
	fadeRise,
	hop,
	Noor,
	SafeZones,
	showFor,
	SkySheet,
	springAt,
	Stars,
	txt,
	W,
	Watermark,
} from './kit';
import {Cue, endCues, ReelSound} from './sound';
import {PaperGate, Season, SeasonMarks} from './world';
import {V2} from './copy';

export const V2_TOTAL = 600;
const FROM = 450;

// ── the screen, at reel size (the app's dp × 3) ──────────────────────────────
const ROAD_X = 830;
const ROAD_TOP = 640; // the band's foot
const START_Y = 1712;
const HERE_Y = 1290;
const CARD = {left: 50, width: 700};
const TITLE_Y = 292;
const BAND = {x: 50, y: 384, w: 980, h: 256, r: 56};
const GATE_TOPS = [712, 874, 1036];
const GATE_H = 146;
const HERE_TOP = 1196;
const LIT_Y = 1424;
const WEEK_TOP = 1478;
const roadX = (y: number) => ROAD_X + 12 * Math.sin((y - ROAD_TOP) / 70);
const PAGE = '#FAF8F5'; // the app's background
const CARD_BG = '#FFFFFF';
const MUTED = '#5B6B67';

// hook
const START: [number, number] = [470, 1330];
const START_SIZE = 420;
const NOOR_SIZE = 170;
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
	hook: [3, 66],
	look: [24, 32, 42, 52, 60, 66],
	rise: 4,
	topics: [8, 62],
	sheet: 66,
	title: 86,
	band: 86,
	toStart: [70, 92],
	startDot: 88,
	walk: [98, 148], // Noor walks the lit road as it is drawn under him
	lit: [96, 146],
	roadLanterns: [108, 122, 136],
	week: 112,
	weekLanterns: [120, 130, 140],
	here: 150,
	horizon: 196,
	unlit: [200, 262],
	gates: [216, 236, 256], // near first: the road reaches the lowest gate first
	seasons: [
		[290, 334],
		[334, 376],
		[376, 446],
	] as [number, number][],
	message: 402,
};

const SEASONS: Season[] = ['rajab', 'shaban', 'hijjah'];

// Sound cues (source frames); exported so the voice-over cut can retime and duck them.
export const V2_CUES: Cue[] = [
	{file: 'rustle', at: 0, vol: 0.45},
	{file: 'rustle', at: T.rise, vol: 0.35},
	...TOPICS.map((_, i) => ({file: 'tick' as const, at: T.topics[0] + i * 4, vol: 0.28})),
	{file: 'air', at: T.topics[1], vol: 0.45},
	{file: 'rustle_long', at: T.sheet, vol: 0.5},
	{file: 'air', at: T.toStart[0], vol: 0.3},
	{file: 'drop', at: T.toStart[1], vol: 0.45},
	{file: 'rustle_long', at: T.lit[0], vol: 0.45},
	...T.roadLanterns.map((a, i) => ({file: 'air' as const, at: a, vol: 0.42 - i * 0.04})),
	{file: 'rustle', at: T.week, vol: 0.35},
	{file: 'drop', at: T.here, vol: 0.5},
	{file: 'tick', at: T.here + 4, vol: 0.35},
	{file: 'rustle_long', at: T.unlit[0], vol: 0.45},
	...T.gates.map((a) => ({file: 'rustle' as const, at: a, vol: 0.42})),
	...T.gates.map((a) => ({file: 'tick' as const, at: a + 6, vol: 0.3})),
	...T.seasons.map(([a]) => ({file: 'swish' as const, at: a, vol: 0.38})),
	{file: 'air', at: T.message, vol: 0.4},
	...endCues(FROM),
];

/** Mix trim of this reel (lands the silent cut near -23 LUFS). */
export const V2_GAIN = 1.13;

/** A point along the road polyline, bottom (y0) to top (y1), every 8 px. */
const roadPts = (y0: number, y1: number): P[] => {
	const pts: P[] = [];
	const n = Math.ceil(Math.abs(y0 - y1) / 8);
	for (let i = 0; i <= n; i++) {
		const y = y0 + ((y1 - y0) * i) / n;
		pts.push([roadX(y), y]);
	}
	return pts;
};
const polyD = (pts: P[]) => pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');

export const V2Road: React.FC<{safe?: boolean}> = ({safe = false}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	const lit = useMemo(() => polyD(roadPts(START_Y, HERE_Y)), []);
	const unlit = useMemo(() => polyD(roadPts(HERE_Y, ROAD_TOP + 10)), []);
	const litP = eased(frame, T.lit[0], T.lit[1], Easing.inOut(Easing.sin));
	const unlitP = eased(frame, T.unlit[0], T.unlit[1], Easing.inOut(Easing.sin));
	const gateY = GATE_TOPS.map((t) => t + GATE_H / 2);

	// ── Noor ─────────────────────────────────────────────────────────────────
	const rise = springAt(frame, T.rise, fps, 11, 80);
	let pos: [number, number] = [START[0], START[1] + 420 * (1 - rise)];
	let size = START_SIZE;
	let squash = 0;
	let hopping = false;
	if (frame >= T.toStart[0]) {
		const h = hop(frame, T.toStart[0], T.toStart[1], START, [roadX(START_Y), START_Y + 40], 260);
		pos = [h.x, h.y];
		size = START_SIZE + (NOOR_SIZE - START_SIZE) * h.p;
		hopping = frame < T.toStart[1];
		if (frame >= T.toStart[1]) squash = (1 - springAt(frame, T.toStart[1], fps, 7, 220)) * 0.12;
	}
	if (frame >= T.walk[0]) {
		const p = eased(frame, T.walk[0], T.walk[1], Easing.inOut(Easing.sin));
		const y = START_Y + (HERE_Y - START_Y) * p;
		const step = frame < T.walk[1] ? Math.abs(Math.sin((frame - T.walk[0]) * 0.42)) * 16 : 0;
		pos = [roadX(y), y + 40 - step];
		if (frame >= T.walk[1]) squash = (1 - springAt(frame, T.walk[1], fps, 7, 220)) * 0.1;
	}
	const look = interpolate(frame, T.look, [0, -1, -1, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	let eyes = blinkEyes(frame, 'open', [182, 318, 420]);
	let mouth: 'smile' | 'open' | 'calm' = 'smile';
	let sparkles = 0;
	let lookUp = 0;
	if (frame < 72 && frame > 24) mouth = 'calm';
	if (hopping || (frame >= T.walk[0] && frame < T.walk[1])) {
		eyes = 'happy';
		mouth = 'open';
	}
	if (frame >= T.here && frame < T.here + 26) {
		eyes = 'happy';
		mouth = 'open';
		sparkles = springAt(frame, T.here + 1, fps, 9, 160) * (1 - eased(frame, T.here + 18, T.here + 26));
	}
	if (frame >= T.unlit[0]) lookUp = eased(frame, T.unlit[0], T.unlit[0] + 12);
	if (frame >= T.seasons[0][0]) {
		eyes = blinkEyes(frame, 'open', [318, 420]);
		mouth = 'open';
	}
	const pose = {cx: pos[0], by: pos[1], size};

	// ── the page ─────────────────────────────────────────────────────────────
	const pageOn = frame >= T.sheet;
	const titleS = fadeRise(frame, T.title, fps, 24, T.message - 6);
	const bandS = springAt(frame, T.band, fps, 13, 90);
	const startS = springAt(frame, T.startDot, fps, 10, 170);
	const hereS = springAt(frame, T.here, fps, 11, 150);
	const weekS = springAt(frame, T.week, fps, 12, 140);
	const horizonS = fadeRise(frame, T.horizon, fps, 20);
	// the season on show, and how far in it is (drops in, lifts away)
	const seasonShow = T.seasons.map(([a, b], i) => springAt(frame, a, fps, 12, 120) * (i < 2 ? 1 - eased(frame, b - 4, b + 6) : 1));

	const roadLanterns = [0.25, 0.55, 0.85].map((t) => {
		const y = START_Y + (HERE_Y - START_Y) * t;
		return {x: roadX(y), y: y + 12};
	});

	return (
		<AbsoluteFill style={{background: C.emerald, overflow: 'hidden'}}>
			<Stars frame={frame} fps={fps} />
			{/* the hook, then the app's page drops over it */}
			<SkySheet color={PAGE} frame={frame} fps={fps} at={T.sheet}>
				{pageOn && (
					<>
						{/* «درب مريم» */}
						<div style={{position: 'absolute', left: CARD.left, top: TITLE_Y, width: CARD.width, ...titleS}}>
							<p style={txt({fontWeight: 900, fontSize: 68, lineHeight: 1.3, color: C.ink, textAlign: 'right'})}>{V2.title}</p>
						</div>
						{/* the sky band with the season's touch */}
						<SkyBand frame={frame} s={bandS} show={seasonShow} />

						{/* «على الأفق» */}
						<div style={{position: 'absolute', left: CARD.left, top: ROAD_TOP + 14, width: CARD.width - 30, ...horizonS}}>
							<p style={txt({fontWeight: 700, fontSize: 40, lineHeight: 1.3, color: MUTED, textAlign: 'right'})}>{V2.horizon}</p>
						</div>

						{/* the road: gold where it is lit, paper where it is still ahead */}
						<svg width={W} height={1920} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
							{unlitP > 0.004 && (
								<>
									<path d={unlit} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - unlitP} fill="none" stroke={C.ivory3}
										strokeWidth={36} strokeLinecap="round" transform="translate(6 8)" opacity={0.6} />
									<path d={unlit} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - unlitP} fill="none" stroke={C.ivory3}
										strokeWidth={34} strokeLinecap="round" />
								</>
							)}
							{litP > 0.004 && (
								<>
									<path d={lit} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - litP} fill="none" stroke={C.ivory3}
										strokeWidth={36} strokeLinecap="round" transform="translate(6 8)" />
									<path d={lit} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - litP} fill="none" stroke={C.gold}
										strokeWidth={34} strokeLinecap="round" />
								</>
							)}
							{/* «من هنا بدأ دربكم»: the start */}
							{startS > 0.001 && (
								<g transform={`translate(${roadX(START_Y)} ${START_Y}) scale(${startS})`}>
									<circle cx={5} cy={7} r={30} fill={C.ivory3} />
									<circle r={30} fill={C.shadow} />
								</g>
							)}
							{roadLanterns.map((l, i) => (
								<LanternG
									key={i}
									x={l.x}
									y={l.y}
									size={78}
									pop={springAt(frame, T.roadLanterns[i] - 4, fps, 10, 160)}
									flame={springAt(frame, T.roadLanterns[i], fps, 9, 150)}
									glow={springAt(frame, T.roadLanterns[i] + 3, fps, 18, 70)}
									flicker={0.6 * Math.sin(frame * 0.33 + i * 1.7) + 0.4 * Math.sin(frame * 0.13 + i)}
								/>
							))}
						</svg>

						{/* the gates on the horizon, near first */}
						{[2, 1, 0].map((g, order) => {
							const at = T.gates[order];
							const gs = springAt(frame, at, fps, 10, 170);
							const cs = springAt(frame, at + 5, fps, 12, 140);
							const gate = V2.gates[g];
							return (
								<React.Fragment key={g}>
									{gs > 0.001 && (
										<div
											style={{
												position: 'absolute',
												left: roadX(gateY[g]) - 40,
												top: gateY[g] - 60,
												transform: `scale(${gs})`,
												transformOrigin: '50% 100%',
											}}
										>
											<PaperGate h={100} near={g === 2} />
										</div>
									)}
									{cs > 0.001 && (
										<div
											style={{
												position: 'absolute',
												left: CARD.left,
												top: GATE_TOPS[g],
												width: CARD.width - 40,
												height: GATE_H,
												background: CARD_BG,
												borderRadius: 40,
												boxShadow: `8px 10px 0 ${C.ivory2}`,
												border: `3px solid #DCE9E6`,
												boxSizing: 'border-box',
												padding: '8px 32px 10px',
												opacity: Math.min(1, cs * 1.4),
												transform: `translateX(${-(1 - cs) * 120}px)`,
												display: 'flex',
												flexDirection: 'column',
												justifyContent: 'center',
											}}
										>
											{gate.eyebrow && <p style={txt({fontWeight: 700, fontSize: 26, lineHeight: 1.25, color: MUTED, textAlign: 'right'})}>{gate.eyebrow}</p>}
											<p style={txt({fontWeight: 900, fontSize: 37, lineHeight: 1.3, color: C.ink, textAlign: 'right'})}>{gate.title}</p>
											{gate.line && <p style={txt({fontWeight: 700, fontSize: 30, lineHeight: 1.4, color: MUTED, textAlign: 'right'})}>{gate.line}</p>}
											{gate.action && (
												<p style={txt({fontWeight: 900, fontSize: 33, lineHeight: 1.3, color: C.emerald, textAlign: 'left', marginTop: 2})}>
													{gate.action}
												</p>
											)}
										</div>
									)}
								</React.Fragment>
							);
						})}

						{/* «أنتم هنا» */}
						{hereS > 0.001 && (
							<div
								style={{
									position: 'absolute',
									left: CARD.left + 20,
									top: HERE_TOP,
									width: CARD.width - 60,
									background: CARD_BG,
									borderRadius: 40,
									border: `5px solid ${C.hill2}`,
									boxShadow: `8px 10px 0 ${C.ivory2}`,
									boxSizing: 'border-box',
									padding: '16px 34px 20px',
									transform: `scale(${hereS})`,
									transformOrigin: '100% 50%',
								}}
							>
								<p style={txt({fontWeight: 900, fontSize: 50, lineHeight: 1.3, color: C.hill2, textAlign: 'right'})}>{V2.here}</p>
								<p style={txt({fontWeight: 700, fontSize: 31, lineHeight: 1.45, color: C.ink, textAlign: 'right'})}>{V2.hereHint}</p>
							</div>
						)}

						{/* «ما أضأتموه» — this week's lanterns */}
						{weekS > 0.001 && (
							<>
								<div style={{position: 'absolute', left: CARD.left, top: LIT_Y, width: CARD.width - 30, opacity: weekS}}>
									<p style={txt({fontWeight: 700, fontSize: 40, lineHeight: 1.3, color: MUTED, textAlign: 'right'})}>{V2.lit}</p>
								</div>
								<div
									style={{
										position: 'absolute',
										left: CARD.left,
										top: WEEK_TOP,
										width: CARD.width - 40,
										height: 150,
										background: '#F1EEE9',
										borderRadius: 40,
										transform: `translateX(${-(1 - weekS) * 120}px)`,
										opacity: Math.min(1, weekS * 1.4),
									}}
								>
									<p style={txt({fontWeight: 900, fontSize: 38, lineHeight: 1.3, color: C.ink, textAlign: 'right', padding: '16px 34px 0'})}>
										{V2.thisWeek}
									</p>
									<svg width={CARD.width - 40} height={90} style={{position: 'absolute', left: 0, top: 60, overflow: 'visible'}}>
										{T.weekLanterns.map((a, i) => (
											<LanternG
												key={i}
												x={CARD.width - 120 - i * 74}
												y={80}
												size={64}
												pop={springAt(frame, a - 4, fps, 10, 160)}
												flame={springAt(frame, a, fps, 9, 150)}
												glow={0}
												flicker={0.6 * Math.sin(frame * 0.33 + i * 1.7)}
											/>
										))}
									</svg>
								</div>
							</>
						)}
						{startS > 0.001 && (
							<div style={{position: 'absolute', left: CARD.left, top: START_Y - 32, width: CARD.width - 30, opacity: startS}}>
								<p style={txt({fontWeight: 700, fontSize: 38, lineHeight: 1.3, color: MUTED, textAlign: 'right'})}>{V2.start}</p>
							</div>
						)}
					</>
				)}
			</SkySheet>

			{/* the hook: too many topics, no idea where to begin */}
			{TOPICS.map((tp, i) => {
				const sc = showFor(frame, T.topics[0] + i * 4, T.topics[1] + i * 2, fps, 10, 10, 170);
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
				<Noor
					frame={frame}
					{...pose}
					eyes={eyes}
					mouth={mouth}
					look={frame < T.unlit[0] ? look : -0.4 * lookUp}
					tilt={frame < T.unlit[0] ? look * 5 : -6 * lookUp}
					sparkles={sparkles}
					squash={squash}
				/>
			)}

			<Caption lines={V2.hook} top={300} font={96} style={fadeRise(frame, T.hook[0], fps, 30, T.hook[1])} />
			<Caption lines={[V2.message.join(' ')]} top={TITLE_Y - 8} font={62} color={C.ink} style={fadeRise(frame, T.message, fps, 24, FROM - 4)} />

			<EndCard frame={frame} fps={fps} from={FROM} slug="v2_road" tagline={V2.tagline} noorFrom={pose} />
			<Watermark frame={frame} fps={fps} hideAt={T.sheet} />
			{safe ? <SafeZones /> : null}
			<ReelSound cues={V2_CUES} total={V2_TOTAL} gain={V2_GAIN} />
		</AbsoluteFill>
	);
};

/**
 * The band at the top of the road screen: a night sky with a few stars over
 * two cut hills (the app's sky band), and, one season at a time, its paper
 * touch along the top edge (`show[i]` for Rajab, Sha'ban, Dhu al-Hijjah).
 */
const SkyBand: React.FC<{frame: number; s: number; show: number[]}> = ({frame, s, show}) => {
	if (s <= 0.001) return null;
	const {x, y, w, h, r} = BAND;
	const k = 3; // the app's dp → reel px
	const far: P[] = [
		[-40, h - 46],
		[w * 0.3, h - 72],
		[w * 0.62, h - 58],
		[w + 40, h - 70],
	];
	const near: P[] = [
		[-40, h - 22],
		[w * 0.4, h - 34],
		[w * 0.75, h - 20],
		[w + 40, h - 30],
	];
	const stars: [number, number, number, boolean][] = [
		[0.08, 0.16, 7, true],
		[0.2, 0.3, 4, false],
		[0.33, 0.18, 6, true],
		[0.47, 0.34, 4, false],
		[0.55, 0.15, 7, true],
		[0.66, 0.26, 4, false],
		[0.8, 0.17, 6, true],
		[0.9, 0.36, 4, false],
		[0.94, 0.12, 6, true],
	];
	const seasonOn = show.some((v) => v > 0.05);
	return (
		<div
			style={{
				position: 'absolute',
				left: x,
				top: y,
				width: w,
				height: h,
				transform: `translateY(${-(1 - s) * 140}px)`,
				opacity: Math.min(1, s * 1.5),
			}}
		>
			<div style={{position: 'absolute', inset: 0, borderRadius: r, background: C.ivory3, transform: 'translate(8px, 10px)'}} />
			<svg width={w} height={h} style={{position: 'absolute', inset: 0, borderRadius: r, overflow: 'hidden'}}>
				<rect width={w} height={h} rx={r} fill={C.ink} />
				{stars.map(([fx, fy, sr, gold], i) => {
					const tw = 1 + 0.12 * Math.sin(frame * 0.1 + i * 1.3);
					const dim = seasonOn && fy < 0.22 ? 0.35 : 1; // the season's marks own the top edge
					return gold ? (
						<polygon key={i} points={star8(fx * w, fy * h, sr * tw)} fill={C.gold} opacity={dim} />
					) : (
						<circle key={i} cx={fx * w} cy={fy * h} r={sr * 0.8} fill={C.ivory} opacity={dim} />
					);
				})}
				{(['rajab', 'shaban'] as Season[]).map((sn, i) => (
					<SeasonMarks key={sn} season={sn} w={w} h={h} k={k} show={show[i]} frame={frame} farY={h - 66} />
				))}
				<path d={hillD(far, h + 40)} fill={C.hill2} />
				<SeasonMarks season="hijjah" w={w} h={h} k={k} show={show[2]} frame={frame} farY={h - 66} />
				<path d={hillD(near, h + 40)} fill={C.emerald} />
			</svg>
		</div>
	);
};
