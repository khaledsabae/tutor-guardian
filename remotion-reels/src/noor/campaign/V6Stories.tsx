// Reel 6 «حكاية مع نور» (v6_stories) — a bedtime story, told by Noor, on the
// app's new reader (#126): each page a layered paper scene drawn from the
// app's own pieces (the same backdrop, props and places as
// story_scene_catalog.dart), the words lighting up as Noor reads, a page
// turn that slides near paper further than far paper — and halfway, «وقفة مع
// نور»: he stops to ask the child what they would do.
import React from 'react';
import {AbsoluteFill, Easing, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../palette';
import {
	blinkEyes,
	Bubble,
	Caption,
	CX,
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
import {HOPE_SPROUT, NoorFace, NoorWindow, SceneView} from './world';
import {V6} from './copy';

export const V6_TOTAL = 690;
const FROM = 540;

// the open book (output px)
const BOOK = {left: 50, width: 860, sceneTop: 452};
const SCENE_H = (BOOK.width * 2) / 3;
const NARRATOR = {cx: 190, by: 1530, size: 210};

const T = {
	hook: [3, 84],
	rise: 6,
	intro: [86, 126],
	book: 128, // the first page drops in, piece by piece
	pieces: [136, 144, 152, 160],
	read1: [162, 250],
	turn1: [256, 276],
	read2: [280, 320],
	pause: 324, // «وقفة مع نور» slides in as a page of its own
	question: 336,
	options: 352,
	tap: 404,
	affirm: 414,
	turn2: [452, 472], // on to the page where the sprout has grown
	message: 478,
};

const SPEAK: [number, number][] = [
	[T.read1[0], T.read1[1]],
	[T.read2[0] - 4, T.read2[1]],
];

// Sound cues (source frames); exported so the voice-over cut can retime and duck them.
export const V6_CUES: Cue[] = [
	{file: 'rustle', at: 0, vol: 0.45},
	{file: 'air', at: T.rise, vol: 0.35},
	{file: 'rustle', at: T.intro[0], vol: 0.4},
	{file: 'rustle_long', at: T.book - 4, vol: 0.5},
	...T.pieces.map((a, i) => ({file: 'tick' as const, at: a, vol: 0.3 - i * 0.02})),
	{file: 'swish', at: T.turn1[0], vol: 0.5},
	{file: 'rustle', at: T.pause, vol: 0.5},
	{file: 'drop', at: T.question, vol: 0.4},
	{file: 'tick', at: T.options, vol: 0.3},
	{file: 'tick', at: T.options + 6, vol: 0.3},
	{file: 'tick', at: T.tap, vol: 0.55},
	{file: 'drop', at: T.tap + 3, vol: 0.5},
	{file: 'swish', at: T.turn2[0], vol: 0.5},
	...endCues(FROM),
];

/** Mix trim of this reel (lands the silent cut near -23 LUFS). */
export const V6_GAIN = 1.42;

export const V6Stories: React.FC<{safe?: boolean}> = ({safe = false}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	// ── Noor: rises big in the hook, says hello, then settles as the narrator ─
	const rise = springAt(frame, T.rise, fps, 11, 80);
	const settle = eased(frame, T.book - 6, T.book + 18, Easing.inOut(Easing.cubic));
	const big = {cx: CX, by: 1420 + 500 * (1 - rise), size: 400};
	const pose = {
		cx: big.cx + (NARRATOR.cx - big.cx) * settle,
		by: big.by + (NARRATOR.by - big.by) * settle - Math.sin(Math.PI * settle) * 160,
		size: big.size + (NARRATOR.size - big.size) * settle,
	};
	const speaking = SPEAK.some(([a, b]) => frame >= a && frame < b);
	let eyes = blinkEyes(frame, 'open', [60, 230, 300]);
	let mouth: 'smile' | 'calm' | 'open' = speaking ? (Math.sin(frame * 0.9) > 0 ? 'open' : 'smile') : 'smile';
	let sparkles = 0;
	if (frame >= T.intro[0] && frame < T.intro[1]) {
		eyes = 'happy';
		mouth = 'open';
	}
	if (frame >= T.turn2[0]) {
		eyes = 'happy';
		mouth = 'open';
		sparkles = springAt(frame, T.turn2[1], fps, 9, 160);
	}
	const noorShow = 1 - eased(frame, T.pause - 4, T.pause + 6) + eased(frame, T.turn2[0], T.turn2[0] + 10);

	// ── the book ─────────────────────────────────────────────────────────────
	const bookS = springAt(frame, T.book, fps, 13, 90);
	const pop = (i: number) => (i < 0 ? bookS : springAt(frame, T.pieces[i] ?? T.pieces[3], fps, 10, 160));
	// page turn: the old page leaves to the right, the new comes from the left (Arabic)
	const turn1 = eased(frame, T.turn1[0], T.turn1[1], Easing.inOut(Easing.cubic));
	const turn2 = eased(frame, T.turn2[0], T.turn2[1], Easing.inOut(Easing.cubic));
	const pauseIn = springAt(frame, T.pause, fps, 14, 110);
	const pauseOut = turn2;

	const titleS = fadeRise(frame, T.book + 6, fps, 20, T.pause - 4);
	const readP = (i: number) => {
		const [a, b] = SPEAK[i];
		return eased(frame, a, b - 6, Easing.linear);
	};

	// the page that shows, and how far it has turned
	const pageSlide = (k: number) => {
		// k = 0: page 1 (leaves on turn1); 1: page 2 (arrives on turn1, covered by the pause); 3: the grown sprout (arrives on turn2)
		if (k === 0) return turn1;
		if (k === 1) return turn1 - 1;
		return turn2 - 1;
	};

	const pauseFace: NoorFace = frame < T.tap ? 'thinking' : 'happy';
	const qS = fadeRise(frame, T.question, fps, 24);
	const optS = (i: number) => springAt(frame, T.options + i * 6, fps, 12, 150);
	const sel = springAt(frame, T.tap, fps, 10, 180);
	const affirmS = fadeRise(frame, T.affirm, fps, 20);
	const tapAt = {x: CX + 60, y: 952};

	return (
		<AbsoluteFill style={{background: C.emerald, overflow: 'hidden'}}>
			<Stars frame={frame} fps={fps} />
			<Hills hills={lowHills(0)} frame={frame} fps={fps} />

			{/* the story's title over the book */}
			<Caption lines={[V6.title]} top={300} font={64} style={titleS} />

			{/* pages 1 and 2, then the page where the sprout has grown */}
			{bookS > 0.001 &&
				[0, 1, 3].map((k) => {
					const slide = pageSlide(k);
					if (k === 3 && frame < T.turn2[0]) return null;
					if (k === 1 && frame < T.turn1[0]) return null;
					if (k !== 3 && frame >= T.turn2[1]) return null;
					if (Math.abs(slide) >= 1) return null;
					const x = slide * 1080; // + right, − left
					const scene = HOPE_SPROUT[k];
					const text = k === 3 ? null : V6.pages[k];
					const words = text ? text.split(' ') : [];
					const lit = k < 2 ? Math.round(readP(k) * words.length) : 0;
					return (
						<div
							key={k}
							style={{
								position: 'absolute',
								left: BOOK.left,
								top: BOOK.sceneTop,
								transform: `translate(${x}px, ${(1 - bookS) * -700}px) rotate(${slide * 6}deg)`,
								transformOrigin: '50% 120%',
							}}
						>
							<Paper radius={44} off={16} style={{width: BOOK.width, height: SCENE_H, overflow: 'hidden'}}>
								<SceneView scene={scene} width={BOOK.width} frame={frame} parallax={slide * 2} pop={k === 0 ? pop : () => 1} radius={44} />
							</Paper>
							{text && (
								<Paper radius={40} off={12} style={{width: BOOK.width, marginTop: 34, padding: '28px 44px 32px', boxSizing: 'border-box'}}>
									<p style={txt({fontWeight: 700, fontSize: 44, lineHeight: 1.7, color: C.ink, textAlign: 'right'})}>
										{words.map((w, i) => (
											<span key={i} style={{opacity: i < lit || frame < SPEAK[k][0] - 30 ? 1 : 0.38}}>
												{w}{' '}
											</span>
										))}
									</p>
									<p style={txt({fontWeight: 700, fontSize: 30, lineHeight: 1.4, color: C.hill3, marginTop: 8})}>{V6.pageOf(k + 1, 4)}</p>
								</Paper>
							)}
						</div>
					);
				})}

			{/* «وقفة مع نور» — a page of its own */}
			{frame >= T.pause && pauseOut < 1 && (
				<div
					style={{
						position: 'absolute',
						left: BOOK.left,
						top: 300,
						width: BOOK.width,
						transform: `translate(${(1 - pauseIn) * -1080 + pauseOut * 1080}px) rotate(${(1 - pauseIn) * -6 + pauseOut * 6}deg)`,
						transformOrigin: '50% 120%',
					}}
				>
					<Paper radius={48} off={16} style={{padding: '44px 48px 56px', minHeight: 1180, boxSizing: 'border-box'}}>
						<div style={{display: 'flex', justifyContent: 'center'}}>
							<NoorWindow size={230} face={pauseFace} ring={0.6 + 0.4 * Math.sin(frame * 0.1)} />
						</div>
						<p style={txt({fontWeight: 900, fontSize: 58, lineHeight: 1.5, color: C.emerald, marginTop: 26})}>{V6.pauseTitle}</p>
						<p style={txt({fontWeight: 900, fontSize: 52, lineHeight: 1.55, color: C.ink, marginTop: 10, ...qS})}>{V6.question}</p>
						<div style={{display: 'flex', flexDirection: 'column', gap: 26, marginTop: 40}}>
							{V6.options.map((o, i) => {
								const s = optS(i);
								const on = i === 0 && sel > 0.5;
								return (
									<div
										key={i}
										style={{
											...txt({fontWeight: 800, fontSize: 44, lineHeight: 1.4, color: C.ink}),
											background: on ? C.gold : C.ivory2,
											borderRadius: 30,
											padding: '20px 30px 24px',
											boxShadow: `8px 10px 0 ${on ? C.shadow : C.ivory3}`,
											transform: `scale(${s * (on ? 1 + 0.06 * Math.sin(Math.PI * Math.min(1, sel)) : 1)})`,
											opacity: frame >= T.affirm && !on ? 0.55 : 1,
										}}
									>
										{o}
									</div>
								);
							})}
						</div>
						<p style={txt({fontWeight: 700, fontSize: 42, lineHeight: 1.6, color: C.ink, marginTop: 36, ...affirmS})}>{V6.affirm}</p>
					</Paper>
				</div>
			)}
			<Tap x={tapAt.x} y={tapAt.y} frame={frame} at={T.tap} />

			{frame >= T.rise && frame < FROM && noorShow > 0.001 && (
				<Noor
					frame={frame}
					{...pose}
					size={pose.size * Math.min(1, noorShow)}
					eyes={eyes}
					mouth={mouth}
					sparkles={sparkles}
					look={settle > 0.5 ? 0.6 : 0}
				/>
			)}
			{/* Noor says hello as himself — the app's own words */}
			<Bubble tipX={noorHead(big).x + 40} tipY={noorHead(big).y - 10} frac={0.5} s={showFor(frame, T.intro[0], T.intro[1], fps, 8, 12, 160)} font={50} maxWidth={760}>
				{V6.intro}
			</Bubble>

			<Caption lines={V6.hook} top={300} font={96} style={fadeRise(frame, T.hook[0], fps, 30, T.hook[1])} />
			<Caption lines={V6.message} top={1090} font={76} style={fadeRise(frame, T.message, fps, 30, FROM - 4)} />

			<EndCard frame={frame} fps={fps} from={FROM} slug="v6_stories" tagline={V6.tagline} noorFrom={pose} />
			<Watermark frame={frame} fps={fps} hideAt={FROM} />
			{safe ? <SafeZones /> : null}
			<ReelSound cues={V6_CUES} total={V6_TOTAL} gain={V6_GAIN} />
		</AbsoluteFill>
	);
};

