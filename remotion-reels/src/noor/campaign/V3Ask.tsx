// Reel 3 «اسأل المربّي» (v3_ask) — a real question is typed; Noor thinks,
// then answers with short, calm, practical steps for the child's age, and
// the parent taps «سأجرّبها».
import React from 'react';
import {AbsoluteFill, Easing, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../palette';
import {
	blinkEyes,
	Bubble,
	Caption,
	Chip,
	CX,
	Dots,
	eased,
	EndCard,
	fadeRise,
	Hills,
	lowHills,
	Noor,
	noorHead,
	Paper,
	SafeZones,
	showFor,
	springAt,
	Stars,
	Tap,
	txt,
	Watermark,
} from './kit';
import {Cue, endCues, ReelSound} from './sound';
import {V3} from './copy';

export const V3_TOTAL = 570;
const FROM = 420;

const T = {
	card: 0,
	type: 4, // first letter
	perChar: 1.3, // frames per letter
	tapSend: 54,
	send: 58,
	think: [74, 122],
	answer: 124,
	steps: [140, 164, 188],
	calm: 212,
	button: 230,
	tapTry: 268,
	qOut: 292,
	message: 302,
};

const NOOR = {cx: 230, by: 1528, size: 400};

// The question breaks after «…»: the first line is typed, then the second.
const Q1 = V3.question.slice(0, V3.question.indexOf('…') + 1);
const Q2 = V3.question.slice(Q1.length).trim();

// Sound cues (source frames); exported so the voice-over cut can retime and duck them.
export const V3_CUES: Cue[] = [
	{file: 'rustle', at: 0, vol: 0.5},
	...Array.from({length: Math.ceil((Q1.length + Q2.length) / 2)}, (_, i) => ({
		file: 'tick' as const,
		at: T.type + i * 2 * T.perChar,
		vol: 0.16 + (0.1 * ((i * 7) % 3)) / 2,
	})),
	{file: 'rustle', at: 10, vol: 0.3},
	{file: 'tick', at: T.tapSend, vol: 0.55},
	{file: 'air', at: T.send, vol: 0.5},
	{file: 'rustle', at: T.think[0], vol: 0.3},
	{file: 'rustle', at: T.answer, vol: 0.5},
	...T.steps.map((at) => ({file: 'rustle' as const, at, vol: 0.3})),
	{file: 'rustle', at: T.calm, vol: 0.25},
	{file: 'tick', at: T.button, vol: 0.35},
	{file: 'tick', at: T.tapTry, vol: 0.55},
	{file: 'drop', at: T.tapTry + 3, vol: 0.55},
	{file: 'rustle', at: T.qOut, vol: 0.35},
	{file: 'air', at: T.message + 32, vol: 0.35},
	...endCues(FROM),
];

/** Mix trim of this reel (lands the silent cut near -23 LUFS). */
export const V3_GAIN = 1.42;

export const V3Ask: React.FC<{safe?: boolean}> = ({safe = false}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	// ── typing ───────────────────────────────────────────────────────────────
	const typed = Math.max(0, Math.floor((frame - T.type) / T.perChar) + 1);
	const n1 = Math.min(Q1.length, typed);
	const n2 = Math.max(0, Math.min(Q2.length, typed - Q1.length));
	const typingDone = typed >= Q1.length + Q2.length;
	const sent = frame >= T.send;
	const caretOn = !sent && (!typingDone || Math.floor(frame / 8) % 2 === 0);

	const cardIn = springAt(frame, T.card, fps, 12, 120);
	const up = eased(frame, T.send, T.send + 16, Easing.inOut(Easing.cubic));
	const cardTop = 600 - 280 * up;
	const cardScale = 1.08 - 0.08 * up;
	const qOut = eased(frame, T.qOut, T.qOut + 12, Easing.in(Easing.cubic));
	const CARD_W = 820;
	const sendBtn = {x: CX - (CARD_W / 2 - 70) * cardScale, y: cardTop + 126}; // the card scales about its centre

	// ── Noor ─────────────────────────────────────────────────────────────────
	const rise = springAt(frame, 10, fps, 11, 80);
	let by = NOOR.by + 420 * (1 - rise);
	let eyes = blinkEyes(frame, 'open', [40, 330]);
	let mouth: 'smile' | 'calm' | 'open' = 'smile';
	let look = 0;
	let tilt = 0;
	let sparkles = 0;
	let heart = 0;
	if (frame >= T.think[0] - 6 && frame < T.think[1]) {
		// thinking: looks up at the question, head tilted
		const k = eased(frame, T.think[0] - 6, T.think[0] + 6) * (1 - eased(frame, T.think[1] - 8, T.think[1]));
		look = 0.9 * k;
		tilt = 7 * k;
		mouth = 'calm';
	}
	if (frame >= T.answer && frame < T.tapTry) {
		mouth = 'smile';
	}
	if (frame >= T.tapTry + 2) {
		eyes = 'happy';
		mouth = 'open';
		sparkles = springAt(frame, T.tapTry + 3, fps, 9, 160);
		const h = frame - (T.tapTry + 2);
		if (h < 16) by -= Math.sin((Math.PI * h) / 16) * 40;
	}
	if (frame >= T.message + 30) {
		eyes = 'closed';
		mouth = 'calm';
		sparkles = 0;
		heart = springAt(frame, T.message + 32, fps, 9, 160);
	}
	const pose = {cx: NOOR.cx, by, size: NOOR.size};
	const head = noorHead({cx: NOOR.cx, by: NOOR.by, size: NOOR.size});

	// ── the answer ───────────────────────────────────────────────────────────
	const BW = 820;
	const frac = 0.18;
	const bLeft = head.x - frac * BW;
	const thinkS = showFor(frame, T.think[0], T.think[1] - 4, fps, 6);
	const ansS = showFor(frame, T.answer, FROM, fps, 8, 12, 150);
	const btnFont = 46;
	const btnH = btnFont * 1.3 + btnFont * 0.54;
	const tapTry = {x: bLeft + BW / 2, y: head.y - 36 - 26 * 0.8 - btnH / 2};
	const trySel = springAt(frame, T.tapTry, fps, 10, 180);

	return (
		<AbsoluteFill style={{background: C.emerald, overflow: 'hidden'}}>
			<Stars frame={frame} fps={fps} />
			<Hills hills={lowHills(0).slice(0, 1)} frame={frame} fps={fps} />
			{frame >= 10 && frame < FROM && (
				<Noor frame={frame} {...pose} eyes={eyes} mouth={mouth} look={look} tilt={tilt} sparkles={sparkles} heart={heart} />
			)}
			<Hills hills={lowHills(0).slice(1)} frame={frame} fps={fps} />

			{/* the question being typed */}
			{cardIn > 0.001 && qOut < 1 && (
				<div
					style={{
						position: 'absolute',
						left: CX - CARD_W / 2,
						top: cardTop,
						width: CARD_W,
						transform: `translateY(${-600 * (1 - cardIn)}px) scale(${cardScale * (1 - 0.3 * qOut)})`,
						opacity: 1 - qOut,
					}}
				>
					<div style={{position: 'absolute', top: -34, left: 0, width: CARD_W, display: 'flex', justifyContent: 'center', zIndex: 1}}>
						<Chip label={V3.label} sel={1} font={36} />
					</div>
					<Paper style={{padding: '44px 40px 30px 130px', minHeight: 196, boxSizing: 'border-box'}}>
						<p style={txt({fontWeight: 900, fontSize: 58, lineHeight: 1.45, color: C.ink, textAlign: 'right', textWrap: 'nowrap'})}>
							{Q1.slice(0, n1)}
							{n2 === 0 && caretOn ? <Caret /> : null}
							<br />
							{Q2.slice(0, n2)}
							{n2 > 0 && caretOn ? <Caret /> : null}
						</p>
					</Paper>
					{/* send button (left: the end of an Arabic line), a check once sent */}
					<svg width={100} height={100} style={{position: 'absolute', left: 20, top: 76, overflow: 'visible'}}>
						<circle cx={54} cy={56} r={40} fill={C.shadow} />
						<circle cx={50} cy={50} r={40} fill={sent ? C.gold : C.emerald} />
						{sent ? (
							<path d="M32 51 L45 64 L69 38" fill="none" stroke={C.ink} strokeWidth={9} strokeLinecap="round" strokeLinejoin="round" />
						) : (
							<path d="M66 50 L36 34 L42 50 L36 66 Z" fill={C.ivory} stroke={C.ivory} strokeWidth={4} strokeLinejoin="round" />
						)}
					</svg>
				</div>
			)}

			{/* Noor thinks… */}
			<Bubble tipX={head.x} tipY={head.y} frac={0.3} s={thinkS} font={40}>
				<Dots frame={frame} size={24} />
			</Bubble>

			{/* …and answers */}
			<Bubble tipX={head.x} tipY={head.y} frac={frac} s={ansS} font={44} maxWidth={BW}>
				<div style={{width: BW - 2 * 26 * 1.4, display: 'flex', flexDirection: 'column', alignItems: 'stretch', gap: 16}}>
					<div style={{display: 'flex', justifyContent: 'center'}}>
						<Chip label={V3.age} sel={1} font={36} />
					</div>
					{V3.steps.map((st, i) =>
						frame < T.steps[i] ? null : (
							<div
								key={i}
								style={{
									display: 'flex',
									direction: 'rtl',
									alignItems: 'flex-start',
									gap: 18,
									...fadeRise(frame, T.steps[i], fps, 20),
								}}
							>
								<div
									style={{
										...txt({fontWeight: 900, fontSize: 38, lineHeight: 1.45, color: C.ivory}),
										flex: '0 0 auto',
										width: 58,
										height: 58,
										marginTop: 4,
										borderRadius: '50%',
										background: C.emerald,
										boxShadow: `3px 4px 0 ${C.shadow}`,
									}}
								>
									{['١', '٢', '٣'][i]}
								</div>
								<p style={txt({fontWeight: 700, fontSize: 47, lineHeight: 1.38, color: C.ink, textAlign: 'right'})}>
									{st.map((l, j) => (
										<React.Fragment key={j}>
											{j > 0 ? <br /> : null}
											{l}
										</React.Fragment>
									))}
								</p>
							</div>
						),
					)}
					{frame < T.calm ? null : (
						<p style={txt({...fadeRise(frame, T.calm, fps, 16), fontWeight: 700, fontSize: 40, lineHeight: 1.4, color: C.emerald})}>
							{V3.calm}
						</p>
					)}
					{frame < T.button ? null : (
						<div style={{display: 'flex', justifyContent: 'center', transform: `scale(${springAt(frame, T.button, fps, 11, 170)})`}}>
							<Chip label={V3.button} font={btnFont} dark sel={trySel} style={{minWidth: 300}} />
						</div>
					)}
				</div>
			</Bubble>

			<Tap x={sendBtn.x} y={sendBtn.y} frame={frame} at={T.tapSend} />
			<Tap x={tapTry.x} y={tapTry.y} frame={frame} at={T.tapTry} />

			<Caption lines={V3.message} top={300} font={80} style={fadeRise(frame, T.message, fps, 30, FROM - 4)} />

			<EndCard frame={frame} fps={fps} from={FROM} slug="v3_ask" tagline={V3.tagline} noorFrom={pose} />
			<Watermark frame={frame} fps={fps} hideAt={FROM} />
			{safe ? <SafeZones /> : null}
			<ReelSound cues={V3_CUES} total={V3_TOTAL} gain={V3_GAIN} />
		</AbsoluteFill>
	);
};

const Caret: React.FC = () => (
	<span
		style={{
			display: 'inline-block',
			width: 6,
			height: 62,
			background: C.emerald,
			marginInlineStart: 6,
			verticalAlign: 'middle',
			borderRadius: 3,
		}}
	/>
);
