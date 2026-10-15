// Reel 1 «نور يتذكّر» (v1_remember) — advice you heard and forgot; Noor
// remembers it with you: he asks when you will try a step, and the next day
// he asks how it went.
import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../palette';
import {LanternG, WalkersG} from '../art';
import {
	blinkEyes,
	Bubble,
	Caption,
	Chip,
	CX,
	eased,
	EndCard,
	fadeRise,
	H,
	Hills,
	lowHills,
	Noor,
	noorHead,
	Paper,
	SafeZones,
	showFor,
	SkySheet,
	springAt,
	Stars,
	Sun,
	Tap,
	txt,
	W,
	Watermark,
} from './kit';
import {Cue, endCues, ReelSound} from './sound';
import {V1} from './copy';

export const V1_TOTAL = 570;
const FROM = 420; // end card

const T = {
	hook: [3, 80],
	note: 2,
	lines: [30, 38, 46], // the note's lines fade: forgotten
	blow: 56, // the blank note is blown away
	noorRise: 16,
	card: 88,
	ask: [118, 200],
	tapWhen: 166,
	nextDay: [236, 292],
	dawn: 214,
	family: 262,
	follow: [272, 338],
	tapWorked: 320,
	thanks: [340, 412],
	lantern: 348,
	message: 364,
};

const NOOR = {cx: 250, by: 1528, size: 460};
const FAMILY = {x: 702, y: 1534, size: 320};

// Sound cues (source frames); exported so the voice-over cut can retime and duck them.
export const V1_CUES: Cue[] = [
	{file: 'rustle', at: 0, vol: 0.45},
	{file: 'rustle', at: T.note, vol: 0.5},
	...T.lines.map((at) => ({file: 'tick' as const, at: at + 2, vol: 0.3})),
	{file: 'air', at: T.blow, vol: 0.6},
	{file: 'rustle', at: T.card, vol: 0.5},
	{file: 'rustle', at: T.ask[0], vol: 0.4},
	{file: 'tick', at: T.tapWhen, vol: 0.55},
	{file: 'drop', at: T.tapWhen + 3, vol: 0.5},
	{file: 'rustle', at: 200, vol: 0.35},
	{file: 'rustle_long', at: T.dawn, vol: 0.6},
	{file: 'air', at: T.dawn + 22, vol: 0.45},
	{file: 'rustle', at: T.family, vol: 0.4},
	{file: 'rustle', at: T.follow[0], vol: 0.4},
	{file: 'tick', at: T.tapWorked, vol: 0.55},
	{file: 'rustle', at: T.thanks[0], vol: 0.35},
	{file: 'drop', at: T.thanks[0] + 6, vol: 0.55},
	{file: 'air', at: T.lantern + 6, vol: 0.55},
	...endCues(FROM),
];

/** Mix trim of this reel (lands the silent cut near -23 LUFS). */
export const V1_GAIN = 1.15;

export const V1Remember: React.FC<{safe?: boolean}> = ({safe = false}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	// ── the note that gets forgotten ─────────────────────────────────────────
	const noteIn = springAt(frame, T.note, fps, 12, 110);
	const blow = eased(frame, T.blow, T.blow + 24, Easing.in(Easing.cubic));
	// blown out to the left, under the hook text, not through it
	const noteY = -620 * (1 - noteIn) + 120 * blow;
	const noteX = -1000 * blow;
	const noteRot = -4 + 10 * (1 - noteIn) - 30 * blow;
	const lineGone = (i: number) => eased(frame, T.lines[i], T.lines[i] + 10);

	// ── Noor ─────────────────────────────────────────────────────────────────
	const rise = springAt(frame, T.noorRise, fps, 11, 80);
	let by = NOOR.by + 420 * (1 - rise);
	const lookCard = interpolate(frame, [22, 32, T.blow, T.blow + 10, 84, 94], [0, 0.8, 0.8, -1, -1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	let eyes = blinkEyes(frame, 'open', [100, 300]);
	let mouth: 'smile' | 'calm' | 'open' = 'smile';
	let sparkles = 0;
	let pulse = 0;
	let heart = 0;
	if (frame >= T.blow + 6 && frame < 84) mouth = 'calm';
	if (frame >= T.tapWhen + 2 && frame < 204) {
		eyes = 'happy';
		mouth = 'open';
		sparkles = springAt(frame, T.tapWhen + 3, fps, 9, 160);
		pulse = frame < T.tapWhen + 16 ? Math.sin((Math.PI * (frame - T.tapWhen - 2)) / 14) * 0.05 : 0;
	}
	// night passes: he dozes, the sun wakes him
	if (frame >= 206 && frame < 244) {
		eyes = 'closed';
		mouth = 'calm';
	}
	if (frame >= T.thanks[0] + 4) {
		eyes = 'happy';
		mouth = 'open';
		sparkles = springAt(frame, T.thanks[0] + 6, fps, 9, 160);
		heart = 0;
		const h = frame - (T.thanks[0] + 4);
		if (h < 16) by -= Math.sin((Math.PI * h) / 16) * 46;
	}
	const pose = {cx: NOOR.cx, by, size: NOOR.size};
	const head = noorHead({cx: NOOR.cx, by: NOOR.by, size: NOOR.size});

	// ── the lesson card and Noor's question ─────────────────────────────────
	const cardS = showFor(frame, T.card, 200, fps, 10, 12, 120);
	const askS = showFor(frame, T.ask[0], T.ask[1], fps);
	const whenSel = springAt(frame, T.tapWhen, fps, 10, 180);

	// Bubbles have a fixed width so the chip under the fingertip is known.
	const BW = 760;
	const frac = 0.22;
	const bLeft = head.x - frac * BW;
	const padX = 26 * 1.4;
	const chipH = 40 * 1.3 + 40 * 0.54;
	// «الليلة» is the first (right-most) of three fixed-width chips
	const whenW = [190, 160, 280];
	const rowW = whenW.reduce((a, b) => a + b, 0) + 2 * 16;
	const tapWhenX = bLeft + BW - padX - (BW - 2 * padX - rowW) / 2 - whenW[0] / 2;
	const tapWhenY = head.y - 36 - 26 * 0.8 - chipH / 2;

	// next day: follow-up with the four outcomes (2 × 2), «نجحت» first
	const followS = showFor(frame, T.follow[0], T.follow[1], fps);
	const workedSel = springAt(frame, T.tapWorked, fps, 10, 180);
	const gridW = 2 * 300 + 16;
	const tapWorkedX = bLeft + BW - padX - (BW - 2 * padX - gridW) / 2 - 150;
	const tapWorkedY = head.y - 36 - 26 * 0.8 - chipH - 14 - chipH / 2;

	const famS = springAt(frame, T.family, fps, 11, 150);
	const parentHead = {x: FAMILY.x + ((106.5 - 88) / 130) * FAMILY.size, y: FAMILY.y - ((200 - 86) / 130) * FAMILY.size};
	const thanksS = showFor(frame, T.thanks[0], T.thanks[1], fps);

	const sunUp = eased(frame, T.dawn + 14, T.dawn + 70, Easing.out(Easing.cubic));
	const lantern = {
		pop: springAt(frame, T.lantern, fps, 10, 160),
		flame: springAt(frame, T.lantern + 6, fps, 9, 150),
		glow: springAt(frame, T.lantern + 9, fps, 18, 70),
		flicker: 0.6 * Math.sin(frame * 0.33) + 0.4 * Math.sin(frame * 0.13),
	};

	return (
		<AbsoluteFill style={{background: C.emerald, overflow: 'hidden'}}>
			<Stars frame={frame} fps={fps} />
			<SkySheet color={C.coral} frame={frame} fps={fps} at={T.dawn}>
				<Sun x={760} y={1500 - 720 * sunUp} r={92} />
			</SkySheet>
			<Hills hills={lowHills(0).slice(0, 1)} frame={frame} fps={fps} />

			{/* the note: three lines fade, then it is blown away */}
			{noteIn > 0.001 && blow < 1 && (
				<Paper
					style={{
						position: 'absolute',
						left: CX - 280,
						top: 760,
						width: 560,
						height: 300,
						transform: `translate(${noteX}px, ${noteY}px) rotate(${noteRot}deg)`,
						padding: '54px 64px',
						boxSizing: 'border-box',
						display: 'flex',
						flexDirection: 'column',
						alignItems: 'flex-end',
						gap: 34,
					}}
				>
					{[1, 0.82, 0.6].map((w, i) => (
						<div
							key={i}
							style={{
								width: `${w * 100}%`,
								height: 26,
								borderRadius: 13,
								background: C.ivory3,
								opacity: 1 - lineGone(i),
								transform: `scaleX(${1 - 0.6 * lineGone(i)})`,
								transformOrigin: 'right center',
							}}
						/>
					))}
				</Paper>
			)}

			{/* the lesson card: today's step */}
			{cardS > 0.001 && (
				<div style={{position: 'absolute', left: CX - 400, top: 420, width: 800, transform: `scale(${cardS})`, transformOrigin: '50% 0%'}}>
					<Paper style={{padding: '30px 40px 40px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
						<Chip label={V1.label} sel={1} font={38} />
						<p style={txt({fontWeight: 900, fontSize: 56, lineHeight: 1.45, color: C.ink})}>
							{V1.step[0]}
							<br />
							{V1.step[1]}
						</p>
					</Paper>
				</div>
			)}

			{/* the family, the lantern they light */}
			{famS > 0.001 && frame < FROM && (
				<svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
					<LanternG x={468} y={1552} size={112} pop={lantern.pop} flame={lantern.flame} glow={lantern.glow} flicker={lantern.flicker} />
					<WalkersG
						x={FAMILY.x}
						y={FAMILY.y}
						size={FAMILY.size}
						mirror
						pop={famS}
						stepA={0}
						stepB={frame >= T.thanks[0] + 4 && frame < T.thanks[0] + 18 ? Math.sin((Math.PI * (frame - T.thanks[0] - 4)) / 14) * 6 : 0}
						swayA={Math.sin(frame * 0.05) * 0.8}
						swayB={Math.sin(frame * 0.06 + 1) * 1.2}
					/>
				</svg>
			)}

			{frame >= T.noorRise && frame < FROM && (
				<Noor
					frame={frame}
					{...pose}
					eyes={eyes}
					mouth={mouth}
					look={frame < 100 ? lookCard : 0}
					tilt={(frame < 100 ? lookCard : 0) * 4}
					sparkles={sparkles}
					pulse={pulse}
					heart={heart}
				/>
			)}

			<Hills hills={lowHills(0).slice(1)} frame={frame} fps={fps} />

			<Bubble tipX={head.x} tipY={head.y} frac={frac} s={askS} font={50} maxWidth={BW}>
				<div style={{width: BW - 2 * padX, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16}}>
					<span>{V1.when}</span>
					<div style={{display: 'flex', gap: 16, direction: 'rtl'}}>
						{V1.options.map((o, i) => (
							<Chip key={o} label={o} font={40} sel={i === 0 ? whenSel : 0} style={{width: whenW[i], boxSizing: 'border-box'}} />
						))}
					</div>
				</div>
			</Bubble>

			<Bubble tipX={head.x} tipY={head.y} frac={frac} s={followS} font={50} maxWidth={BW}>
				<div style={{width: BW - 2 * padX, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16}}>
					<span>
						{V1.followup[0]}
						<br />
						{V1.followup[1]}
					</span>
					<div style={{display: 'grid', gridTemplateColumns: '300px 300px', gap: 14, columnGap: 16, direction: 'rtl'}}>
						{V1.outcomes.map((o, i) => (
							<Chip key={o} label={o} font={40} sel={i === 0 ? workedSel : 0} style={{boxSizing: 'border-box'}} />
						))}
					</div>
				</div>
			</Bubble>

			<Bubble tipX={parentHead.x} tipY={parentHead.y - 18} frac={0.72} s={thanksS} font={54}>
				{V1.thanks}
			</Bubble>

			<Tap x={tapWhenX} y={tapWhenY} frame={frame} at={T.tapWhen} />
			<Tap x={tapWorkedX} y={tapWorkedY} frame={frame} at={T.tapWorked} />

			<Caption lines={V1.hook} top={300} font={92} style={fadeRise(frame, T.hook[0], fps, 30, T.hook[1])} />
			<Caption lines={[V1.nextDay]} top={330} font={68} color={C.ink} style={fadeRise(frame, T.nextDay[0], fps, 24, T.nextDay[1])} />
			<Caption lines={V1.message} top={330} font={84} color={C.ink} style={fadeRise(frame, T.message, fps, 30, FROM - 4)} />

			<EndCard frame={frame} fps={fps} from={FROM} slug="v1_remember" tagline={V1.tagline} noorFrom={pose} />
			<Watermark frame={frame} fps={fps} hideAt={FROM} />
			{safe ? <SafeZones /> : null}
			<ReelSound cues={V1_CUES} total={V1_TOTAL} gain={V1_GAIN} />
		</AbsoluteFill>
	);
};
