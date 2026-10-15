// Reel 4 «ركن الطفل» (v4_handover) — screen time with a purpose, and an
// end. The parent enters the code and hands the device over; two paper
// mashrabiya doors open on the child's corner as the app draws it (#129
// «ركن الطفل»): «يا عمر، هذا ركنك», Noor in his window, a story and then
// the day's task — and a paper candle for time, never a number. The candle
// grows shorter through the story; the task goes off the screen («صيّاد
// الألوان»); the device goes back, and only the parent's code opens the way
// out of the child's mode.
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../palette';
import {star8} from '../geometry';
import {
	blinkEyes,
	Caption,
	CX,
	eased,
	EndCard,
	fadeRise,
	fontFamily,
	Hills,
	lowHills,
	Noor,
	SafeZones,
	showFor,
	springAt,
	Stars,
	Tap,
	txt,
	Watermark,
} from './kit';
import {Cue, endCues, ReelSound} from './sound';
import {appArt, CORNER, CornerCard, CornerHills, GoldButton, NoorWindow, PaperCandle} from './world';
import {V4} from './copy';

export const V4_TOTAL = 630;
const FROM = 480;

const T = {
	hook: [3, 92],
	device: 2,
	pin: [30, 37, 44, 51],
	doorsIn: 62,
	handTo: [84, 104],
	doorsOpen: 112,
	home: [118, 204],
	tapStory: 190,
	story: [204, 266],
	mission: [266, 352],
	tapGo: 326,
	back: [352, 478],
	handBack: [370, 390],
	exitPin: [398, 404, 410, 416],
	lock: 424,
	shrink: 430,
	message: 436,
};

// device geometry (output px)
const DEV = {w: 560, h: 960, top: 500, r: 64};
const SCR = {x: 26, y: 74, w: DEV.w - 52, h: DEV.h - 74 - 64, r: 30};

// Sound cues (source frames); exported so the voice-over cut can retime and duck them.
export const V4_CUES: Cue[] = [
	{file: 'rustle', at: 0, vol: 0.5},
	{file: 'rustle', at: T.device + 4, vol: 0.4},
	...T.pin.map((at) => ({file: 'tick' as const, at, vol: 0.45})),
	{file: 'rustle', at: T.doorsIn, vol: 0.5},
	{file: 'rustle_long', at: T.handTo[0] - 2, vol: 0.4},
	{file: 'swish', at: T.doorsOpen, vol: 0.45},
	{file: 'drop', at: T.doorsOpen + 10, vol: 0.4},
	{file: 'rustle', at: T.home[0] + 14, vol: 0.35},
	{file: 'tick', at: T.tapStory, vol: 0.5},
	{file: 'rustle', at: T.story[0], vol: 0.45},
	{file: 'rustle', at: T.mission[0], vol: 0.45},
	{file: 'tick', at: T.tapGo, vol: 0.55},
	{file: 'drop', at: T.tapGo + 3, vol: 0.5},
	{file: 'rustle', at: T.back[0], vol: 0.45},
	{file: 'rustle_long', at: T.handBack[0] - 2, vol: 0.4},
	...T.exitPin.map((at) => ({file: 'tick' as const, at, vol: 0.42})),
	{file: 'air', at: T.lock + 4, vol: 0.4},
	...endCues(FROM),
];

/** Mix trim of this reel (lands the silent cut near -23 LUFS). */
export const V4_GAIN = 1.34;

/** The candle's share through the session: it only ever grows shorter. */
const candleAt = (frame: number) =>
	interpolate(frame, [T.home[0], T.story[0], T.mission[0], T.back[0]], [1, 0.86, 0.62, 0.48], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});

export const V4Handover: React.FC<{safe?: boolean}> = ({safe = false}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	// ── the device: drops in, goes to the child, comes back ──────────────────
	const devIn = springAt(frame, T.device, fps, 12, 110);
	const toChild = eased(frame, T.handTo[0], T.handTo[1], Easing.inOut(Easing.back(1.2)));
	const toParent = eased(frame, T.handBack[0], T.handBack[1], Easing.inOut(Easing.back(1.2)));
	const side = -1 + 2 * toChild - 2 * toParent; // -1 parent … +1 child
	const lift = Math.sin(Math.PI * toChild) * 80 + Math.sin(Math.PI * toParent) * 80;
	const shrink = 1 - 0.12 * eased(frame, T.shrink, T.shrink + 18);
	const devX = CX - DEV.w / 2 + side * 70;
	const devY = DEV.top - 900 * (1 - devIn) - lift;
	const devRot = side * 4 + 8 * (1 - devIn);

	// ── screen states ────────────────────────────────────────────────────────
	const gateS = 1 - eased(frame, T.doorsIn + 10, T.doorsIn + 16);
	const doorsIn = eased(frame, T.doorsIn, T.doorsIn + 14, Easing.out(Easing.cubic));
	const doorsOpen = eased(frame, T.doorsOpen, T.doorsOpen + 22, Easing.inOut(Easing.cubic));
	const homeOn = frame >= T.doorsOpen && frame < T.story[0] + 8;
	const storyS = showFor(frame, T.story[0], T.story[1], fps, 8, 13, 140);
	const missionS = showFor(frame, T.mission[0], T.mission[1], fps, 8, 12, 150);
	const backS = showFor(frame, T.back[0], T.back[1], fps, 8, 12, 150);
	const storySel = springAt(frame, T.tapStory, fps, 10, 180);
	const goSel = springAt(frame, T.tapGo, fps, 10, 180);
	const candle = candleAt(frame);
	const sway = Math.sin(frame * 0.2);

	// Noor himself appears on the gate screen and when the device goes back
	let nEyes = blinkEyes(frame, 'open', [24]);
	let nMouth: 'smile' | 'calm' | 'open' = 'smile';
	let nHeart = 0;
	if (frame >= T.back[0]) {
		nEyes = 'closed';
		nMouth = 'calm';
		nHeart = springAt(frame, T.back[0] + 8, fps, 9, 160);
	}
	const noorState = frame < T.doorsOpen ? {cx: SCR.w / 2 + 10, by: 330, size: 240} : {cx: SCR.w / 2 + 14, by: 360, size: 260};
	const noorPop = frame < T.doorsOpen ? springAt(frame, 10, fps, 11, 140) : frame < T.back[0] ? 0 : backS;

	// where things are on the output frame (for the taps and the end card)
	const scrLeft = devX + SCR.x;
	const scrTop = devY + SCR.y;
	const storyCard = {x: scrLeft + SCR.w / 2 + 40, y: scrTop + 470};
	const goBtn = {x: scrLeft + SCR.w / 2, y: scrTop + 662};
	const endNoor = {
		cx: CX - 70 - DEV.w / 2 + DEV.w / 2 + (SCR.x + noorState.cx - DEV.w / 2) * shrink,
		by: DEV.top + DEV.h + (SCR.y + noorState.by - DEV.h) * shrink,
		size: noorState.size * shrink,
	};
	const lockS = springAt(frame, T.lock, fps, 10, 170);
	const exitS = showFor(frame, T.exitPin[0] - 8, FROM, fps, 8, 12, 150);

	return (
		<AbsoluteFill style={{background: C.emerald, overflow: 'hidden'}}>
			<Stars frame={frame} fps={fps} />
			<Hills hills={lowHills(0)} frame={frame} fps={fps} />

			{frame < FROM && devIn > 0.001 && (
				<div
					style={{
						position: 'absolute',
						left: devX,
						top: devY,
						width: DEV.w,
						height: DEV.h,
						transform: `rotate(${devRot}deg) scale(${shrink})`,
						transformOrigin: '50% 100%',
					}}
				>
					{/* body: paper phone with a flat shadow */}
					<div style={{position: 'absolute', inset: 0, borderRadius: DEV.r, background: C.shadow, transform: 'translate(16px, 20px)'}} />
					<div style={{position: 'absolute', inset: 0, borderRadius: DEV.r, background: C.ivory3}} />
					<div style={{position: 'absolute', left: DEV.w / 2 - 50, top: 30, width: 100, height: 16, borderRadius: 8, background: C.ivory2}} />
					{/* screen */}
					<div
						style={{
							position: 'absolute',
							left: SCR.x,
							top: SCR.y,
							width: SCR.w,
							height: SCR.h,
							borderRadius: SCR.r,
							background: frame >= T.doorsOpen && frame < T.back[0] ? CORNER.ground : C.ivory,
							overflow: 'hidden',
						}}
					>
						{/* 0 · the hand-over gate: the parent enters the code */}
						{gateS > 0.001 && (
							<div style={{position: 'absolute', inset: 0, opacity: gateS, display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 40}}>
								<p style={txt({fontWeight: 900, fontSize: 48, lineHeight: 1.4, color: C.ink})}>{V4.gate}</p>
								<div style={{height: 330}} />
								<p style={txt({fontWeight: 700, fontSize: 38, lineHeight: 1.4, color: C.emerald})}>{V4.pin}</p>
								<PinDots frame={frame} at={T.pin} />
								<div style={{marginTop: 34}}>
									<Padlock size={84} gold={frame >= T.pin[3] + 4} />
								</div>
							</div>
						)}

						{/* 1 · «ركن الطفل»: the corner's home */}
						{homeOn && <CornerHome frame={frame} fps={fps} candle={candle} sway={sway} storySel={storySel} />}

						{/* 2 · the story, read in the corner — the candle keeps burning */}
						{storyS > 0.001 && (
							<div style={{position: 'absolute', inset: 0, background: CORNER.ground, transform: `translateX(${(1 - storyS) * -SCR.w}px)`}}>
								<div style={{position: 'absolute', left: 0, top: 0, width: SCR.w, height: 120, background: CORNER.sky}} />
								<div style={{position: 'absolute', left: 0, top: 96}}>
									<CornerHills w={SCR.w} h={70} />
								</div>
								<p style={{...txt({fontWeight: 900, fontSize: 30, lineHeight: 1.3, color: CORNER.ink, textAlign: 'right'}), position: 'absolute', right: 24, top: 30, width: 260}}>
									{V4.storyTitle}
								</p>
								<CandlePill frame={frame} candle={candle} sway={sway} style={{left: 16, top: 18}} compact />
								<CornerCard style={{position: 'absolute', left: 20, right: 20, top: 200, height: 440, padding: '20px 28px', boxSizing: 'border-box'}} k={1.6}>
									<div style={{display: 'flex', justifyContent: 'center'}}>
										<Img src={appArt('noor/noor_reading')} style={{width: 120, height: 120}} />
									</div>
									<p style={txt({fontWeight: 700, fontSize: 32, lineHeight: 1.7, color: CORNER.ink, textAlign: 'right'})}>{V4.storyText}</p>
								</CornerCard>
								<div style={{position: 'absolute', left: 20, top: 690}}>
									<GoldButton label={V4.next} k={1.9} fontFamily={fontFamily} />
								</div>
							</div>
						)}

						{/* 3 · the day's task, away from the screen */}
						{missionS > 0.001 && (
							<div style={{position: 'absolute', inset: 0, background: CORNER.ground, transform: `scale(${0.9 + 0.1 * missionS})`, opacity: Math.min(1, missionS * 1.4)}}>
								<div style={{position: 'absolute', left: 0, top: 0, width: SCR.w, height: 120, background: CORNER.sky}} />
								<div style={{position: 'absolute', left: 0, top: 96}}>
									<CornerHills w={SCR.w} h={70} />
								</div>
								<CandlePill frame={frame} candle={candle} sway={sway} style={{left: 16, top: 18}} compact />
								<CornerCard style={{position: 'absolute', left: 20, right: 20, top: 196, padding: '24px 26px 28px', boxSizing: 'border-box'}} k={1.6}>
									<div style={{display: 'flex', justifyContent: 'center'}}>
										<MissionGlyph size={96} frame={frame} />
									</div>
									<p style={txt({fontWeight: 700, fontSize: 26, lineHeight: 1.4, color: C.hill3})}>{V4.missionNow}</p>
									<p style={txt({fontWeight: 900, fontSize: 46, lineHeight: 1.35, color: CORNER.ink})}>{V4.missionTitle}</p>
									<p style={txt({fontWeight: 700, fontSize: 25, lineHeight: 1.6, color: CORNER.ink, marginTop: 6})}>{V4.missionBody}</p>
									<GoldButton label={V4.missionGo} k={1.75} sel={goSel} fontFamily={fontFamily} style={{marginTop: 22}} />
								</CornerCard>
							</div>
						)}

						{/* 4 · the device goes back; only the parent's code opens the way out */}
						{backS > 0.001 && (
							<div style={{position: 'absolute', left: 0, right: 0, top: 400, transform: `scale(${backS})`}}>
								<p style={txt({fontWeight: 900, fontSize: 46, lineHeight: 1.4, color: C.ink})}>{V4.giveBack[0]}</p>
								<p style={txt({fontWeight: 900, fontSize: 46, lineHeight: 1.5, color: C.emerald})}>{V4.giveBack[1]}</p>
							</div>
						)}
						{exitS > 0.001 && (
							<div
								style={{
									position: 'absolute',
									left: 0,
									right: 0,
									top: 590,
									display: 'flex',
									flexDirection: 'column',
									alignItems: 'center',
									transform: `scale(${exitS})`,
								}}
							>
								<p style={txt({fontWeight: 700, fontSize: 28, lineHeight: 1.4, color: C.emerald, width: 440})}>{V4.exitPin}</p>
								<PinDots frame={frame} at={T.exitPin} />
							</div>
						)}

						{noorPop > 0.001 && (
							<Noor frame={frame} {...noorState} size={noorState.size * noorPop} eyes={nEyes} mouth={nMouth} heart={nHeart} />
						)}

						{/* the two paper mashrabiya doors */}
						{doorsIn > 0.001 && doorsOpen < 1 && (
							<>
								<Door side="right" slide={doorsIn} open={doorsOpen} />
								<Door side="left" slide={doorsIn} open={doorsOpen} />
							</>
						)}
					</div>
					{/* the code keeps it: a padlock badge on the returned device */}
					{lockS > 0.001 && (
						<div style={{position: 'absolute', left: -46, top: -40, transform: `scale(${lockS}) rotate(-8deg)`}}>
							<div
								style={{
									width: 150,
									height: 150,
									borderRadius: '50%',
									background: C.gold,
									boxShadow: `8px 10px 0 ${C.shadow}`,
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'center',
								}}
							>
								<Padlock size={84} gold={false} />
							</div>
						</div>
					)}
				</div>
			)}

			<Tap x={storyCard.x} y={storyCard.y} frame={frame} at={T.tapStory} />
			<Tap x={goBtn.x} y={goBtn.y} frame={frame} at={T.tapGo} />

			<Caption lines={[V4.hook.join(' ')]} top={300} font={100} style={fadeRise(frame, T.hook[0], fps, 30, T.hook[1])} />
			<Caption lines={V4.message} top={296} font={72} style={fadeRise(frame, T.message, fps, 30, FROM - 4)} />

			<EndCard frame={frame} fps={fps} from={FROM} slug="v4_handover" tagline={V4.tagline} noorFrom={endNoor} />
			<Watermark frame={frame} fps={fps} hideAt={FROM} />
			{safe ? <SafeZones /> : null}
			<ReelSound cues={V4_CUES} total={V4_TOTAL} gain={V4_GAIN} />
		</AbsoluteFill>
	);
};

/** «شمعة وقتك — ما زالت مضيئة»: the corner's candle in its paper pill. */
const CandlePill: React.FC<{frame: number; candle: number; sway: number; style: React.CSSProperties; compact?: boolean}> = ({
	candle,
	sway,
	style,
	compact = false,
}) => (
	<div
		style={{
			position: 'absolute',
			display: 'flex',
			alignItems: 'center',
			gap: 10,
			direction: 'rtl',
			background: CORNER.card,
			borderRadius: 26,
			boxShadow: `5px 6px 0 ${CORNER.cardShadow}`,
			padding: compact ? '8px 18px 8px 14px' : '10px 20px 10px 16px',
			...style,
		}}
	>
		<PaperCandle h={compact ? 62 : 70} fraction={candle} sway={sway} />
		<div>
			{!compact && <p style={txt({fontWeight: 700, fontSize: 21, lineHeight: 1.3, color: C.hill3, textAlign: 'right'})}>{V4.candleLabel}</p>}
			<p style={txt({fontWeight: 900, fontSize: 24, lineHeight: 1.3, color: CORNER.ink, textAlign: 'right'})}>{V4.candleBright}</p>
		</div>
	</div>
);

/** The corner's first screen: greeting, Noor's line, the story card and the task card. */
const CornerHome: React.FC<{frame: number; fps: number; candle: number; sway: number; storySel: number}> = ({frame, fps, candle, sway, storySel}) => {
	const a = T.doorsOpen + 4;
	const greet = fadeRise(frame, a + 6, fps, 20);
	const noorS = springAt(frame, a + 14, fps, 11, 150);
	const lineS = springAt(frame, a + 20, fps, 12, 150);
	const card1 = springAt(frame, a + 28, fps, 12, 140);
	const card2 = springAt(frame, a + 36, fps, 12, 140);
	const pill = springAt(frame, a + 10, fps, 12, 150);
	const bump = 1 + 0.05 * Math.sin(Math.PI * Math.min(1, storySel));
	return (
		<div style={{position: 'absolute', inset: 0}}>
			<div style={{position: 'absolute', left: 0, top: 0, width: SCR.w, height: 300, background: CORNER.sky}} />
			<div style={{position: 'absolute', left: 0, top: 262}}>
				<CornerHills w={SCR.w} h={110} />
			</div>
			<div style={{position: 'absolute', right: 22, top: 22, width: 250, ...greet}}>
				<p style={txt({fontWeight: 900, fontSize: 42, lineHeight: 1.3, color: CORNER.ink, textAlign: 'right'})}>{V4.greeting}</p>
			</div>
			{pill > 0.001 && <CandlePill frame={frame} candle={candle} sway={sway} style={{left: 14, top: 22, transform: `scale(${pill})`, transformOrigin: '0 0'}} />}
			{noorS > 0.001 && (
				<div style={{position: 'absolute', right: 20, top: 160, transform: `scale(${noorS})`}}>
					<NoorWindow size={108} face="calm" ring={1} />
				</div>
			)}
			{lineS > 0.001 && (
				<CornerCard
					style={{position: 'absolute', left: 14, top: 156, width: 330, padding: '12px 18px 14px', boxSizing: 'border-box', transform: `scale(${lineS})`, transformOrigin: '100% 50%'}}
					k={1.4}
				>
					<p style={txt({fontWeight: 700, fontSize: 23, lineHeight: 1.5, color: CORNER.ink, textAlign: 'right'})}>{V4.noorLine}</p>
				</CornerCard>
			)}
			{card1 > 0.001 && (
				<CornerCard
					style={{position: 'absolute', left: 18, right: 18, top: 400, padding: '16px 24px', display: 'flex', alignItems: 'center', gap: 18, direction: 'rtl', transform: `translateY(${(1 - card1) * 300}px) scale(${bump})`}}
					k={1.6}
				>
					<BookGlyph size={70} />
					<div>
						<p style={txt({fontWeight: 700, fontSize: 24, lineHeight: 1.3, color: C.hill3, textAlign: 'right'})}>{V4.storyLabel}</p>
						<p style={txt({fontWeight: 900, fontSize: 32, lineHeight: 1.35, color: CORNER.ink, textAlign: 'right'})}>{V4.storyTitle}</p>
						<p style={txt({fontWeight: 700, fontSize: 24, lineHeight: 1.3, color: C.hill3, textAlign: 'right'})}>{V4.storyHint}</p>
					</div>
				</CornerCard>
			)}
			{card2 > 0.001 && (
				<CornerCard
					style={{position: 'absolute', left: 18, right: 18, top: 586, padding: '16px 24px 20px', direction: 'rtl', transform: `translateY(${(1 - card2) * 300}px)`}}
					k={1.6}
				>
					<div style={{display: 'flex', alignItems: 'center', gap: 18}}>
						<MissionGlyph size={64} frame={frame} />
						<div>
							<p style={txt({fontWeight: 700, fontSize: 24, lineHeight: 1.3, color: C.hill3, textAlign: 'right'})}>{V4.missionLabel}</p>
							<p style={txt({fontWeight: 900, fontSize: 32, lineHeight: 1.35, color: CORNER.ink, textAlign: 'right'})}>{V4.missionTitle}</p>
						</div>
					</div>
					<div style={{display: 'flex', justifyContent: 'flex-end', marginTop: 10}}>
						<GoldButton label={V4.toMission} k={1.6} fontFamily={fontFamily} />
					</div>
				</CornerCard>
			)}
		</div>
	);
};

/** An open paper book (the story card's icon). */
const BookGlyph: React.FC<{size: number}> = ({size}) => (
	<svg width={size} height={size} viewBox="0 0 48 48" style={{flex: 'none', overflow: 'visible'}}>
		<path d="M4 12 Q14 8 24 13 Q34 8 44 12 V38 Q34 34 24 39 Q14 34 4 38 Z" fill={C.shadow} transform="translate(1.5 2)" />
		<path d="M4 12 Q14 8 24 13 Q34 8 44 12 V38 Q34 34 24 39 Q14 34 4 38 Z" fill={C.emerald} />
		<path d="M7 14 Q15 11 22.5 15 V35 Q15 31 7 34 Z M25.5 15 Q33 11 41 14 V34 Q33 31 25.5 35 Z" fill={C.ivory} />
		<path d="M36 10 V20 L38.5 18 L41 20 V10" fill={C.coral} />
	</svg>
);

/** The task's mark: a paper sprout under a gold eight-point star. */
const MissionGlyph: React.FC<{size: number; frame: number}> = ({size, frame}) => (
	<svg width={size} height={size} viewBox="0 0 48 48" style={{flex: 'none', overflow: 'visible'}}>
		<path d="M8 42 Q10 28 24 26 Q38 28 40 42 Z" fill={C.shadow} transform="translate(1.5 2)" />
		<path d="M8 42 Q10 28 24 26 Q38 28 40 42 Z" fill={C.emerald} />
		<path d="M24 34 V20 M24 26 Q18 24 16 18 Q22 18 24 24 M24 24 Q30 20 32 14 Q26 15 24 22" fill="none" stroke={C.ivory} strokeWidth={2.6} strokeLinecap="round" />
		<g transform={`rotate(${4 * Math.sin(frame * 0.08)} 36 9)`}>
			<polygon points={star8(36, 9, 7)} fill={C.gold} />
		</g>
	</svg>
);

const PinDots: React.FC<{frame: number; at: number[]}> = ({frame, at}) => (
	<div style={{display: 'flex', gap: 26, marginTop: 18, direction: 'ltr'}}>
		{at.map((a, i) => {
			const on = frame >= a;
			const bump = on ? 1 + 0.25 * Math.sin(Math.PI * Math.min(1, (frame - a) / 8)) : 1;
			return (
				<div
					key={i}
					style={{
						width: 44,
						height: 44,
						borderRadius: '50%',
						background: on ? C.ink : C.ivory2,
						boxShadow: `3px 4px 0 ${on ? C.shadow : C.ivory3}`,
						transform: `scale(${bump})`,
					}}
				/>
			);
		})}
	</div>
);

const Padlock: React.FC<{size: number; gold: boolean}> = ({size, gold}) => (
	<svg width={size} height={size} viewBox="0 0 48 48" style={{display: 'block', overflow: 'visible'}}>
		<path d="M15 22 V15 A9 9 0 0 1 33 15 V22" fill="none" stroke={C.shadow} strokeWidth={6} transform="translate(1.5 2)" />
		<path d="M15 22 V15 A9 9 0 0 1 33 15 V22" fill="none" stroke={C.ink} strokeWidth={6} />
		<rect x={9.5} y={21.5} width={31} height={22} rx={5} fill={C.shadow} />
		<rect x={8} y={20} width={31} height={22} rx={5} fill={gold ? C.gold : C.ink} />
		<circle cx={23.5} cy={29.5} r={3.4} fill={gold ? C.ink : C.ivory} />
		<rect x={22} y={30} width={3} height={7} rx={1.5} fill={gold ? C.ink : C.ivory} />
	</svg>
);

/**
 * One paper mashrabiya door: a panel with an arched frame and a lattice of
 * eight-point star cut-outs. It slides in from its side (`slide` 0…1), then
 * swings open on its outer hinge (`open` 0…1).
 */
const Door: React.FC<{side: 'left' | 'right'; slide: number; open: number}> = ({side, slide, open}) => {
	const w = SCR.w / 2;
	const h = SCR.h;
	const sgn = side === 'left' ? -1 : 1;
	const tx = sgn * w * (1 - slide);
	const angle = sgn * -105 * open;
	const holes: React.ReactNode[] = [];
	const pitch = 70;
	for (let row = 0; row < 11; row++) {
		for (let col = 0; col < 4; col++) {
			const x = 48 + col * pitch + (row % 2) * (pitch / 2);
			const y = 190 + row * pitch * 0.86;
			if (x > w - 30 || y > h - 80) continue;
			holes.push(<polygon key={`${row}-${col}`} points={star8(x, y, 22)} fill={C.ivory2} />);
		}
	}
	const arch = `M24 ${h - 40} V150 A${w / 2 - 24} ${w / 2 - 24} 0 0 1 ${w - 24} 150 V${h - 40} Z`;
	return (
		<div
			style={{
				position: 'absolute',
				top: 0,
				left: side === 'left' ? 0 : w,
				width: w,
				height: h,
				transform: `translateX(${tx}px) perspective(1600px) rotateY(${angle}deg)`,
				transformOrigin: side === 'left' ? '0% 50%' : '100% 50%',
				backfaceVisibility: 'hidden',
			}}
		>
			<svg width={w} height={h} style={{display: 'block'}}>
				<defs>
					<clipPath id={`arch-${side}`}>
						<path d={arch} />
					</clipPath>
				</defs>
				<rect width={w} height={h} fill={C.hill3} />
				<path d={arch} fill={C.shadow} />
				<g clipPath={`url(#arch-${side})`}>{holes}</g>
				<path d={arch} fill="none" stroke={C.gold} strokeWidth={6} />
				{/* the seam between the two doors, and a small knob */}
				<rect x={side === 'left' ? w - 6 : 0} y={0} width={6} height={h} fill={C.shadow} />
				<circle cx={side === 'left' ? w - 34 : 34} cy={h / 2 + 40} r={13} fill={C.gold} />
			</svg>
		</div>
	);
};
