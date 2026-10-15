// Reel 4 «دوره الآن» (v4_handover) — screen time with a purpose. The parent
// enters the code and hands the device over; two paper mashrabiya doors open
// on «يا يوسف، دورك الآن»; a short mission away from the screen; then «أعِد
// الجهاز إلى أهلك — شكرًا لك» and the device goes back, locked by the code.
import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../palette';
import {SprigG} from '../art';
import {star8} from '../geometry';
import {
	blinkEyes,
	Caption,
	Chip,
	CX,
	eased,
	EndCard,
	fadeRise,
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
import {V4} from './copy';

export const V4_TOTAL = 600;
const FROM = 450;

const T = {
	hook: [3, 92],
	device: 2,
	pin: [30, 37, 44, 51],
	doorsIn: 62,
	handTo: [84, 104],
	doorsOpen: 112,
	turn: [114, 192],
	mission: [192, 292],
	tapDone: 262,
	back: [292, 440],
	handBack: [318, 338],
	lock: 340,
	shrink: 346,
	message: 352,
};

// device geometry (output px)
const DEV = {w: 560, h: 960, top: 500, r: 64};
const SCR = {x: 26, y: 74, w: DEV.w - 52, h: DEV.h - 74 - 64, r: 30};

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
	const turnS = showFor(frame, T.doorsOpen + 6, T.turn[1], fps, 8, 12, 140);
	const missionS = showFor(frame, T.mission[0], T.mission[1], fps, 8, 12, 150);
	const backS = showFor(frame, T.back[0], T.back[1], fps, 8, 12, 150);
	const doneSel = springAt(frame, T.tapDone, fps, 10, 180);

	// Noor inside the screen
	let nEyes = blinkEyes(frame, 'open', [24, 380]);
	let nMouth: 'smile' | 'calm' | 'open' = 'smile';
	let nSpark = 0;
	let nHeart = 0;
	if (frame >= T.doorsOpen + 6 && frame < T.turn[1]) {
		nEyes = 'happy';
		nMouth = 'open';
		nSpark = springAt(frame, T.doorsOpen + 10, fps, 9, 160);
	}
	if (frame >= T.tapDone + 2 && frame < T.mission[1]) {
		nEyes = 'happy';
		nMouth = 'open';
		nSpark = springAt(frame, T.tapDone + 3, fps, 9, 160);
	}
	if (frame >= T.back[0]) {
		nEyes = 'closed';
		nMouth = 'calm';
		nHeart = springAt(frame, T.back[0] + 8, fps, 9, 160);
	}
	const noorState = (() => {
		if (frame < T.doorsOpen) return {cx: SCR.w / 2 + 10, by: 330, size: 240};
		if (frame < T.mission[0]) return {cx: SCR.w / 2 + 14, by: 420, size: 320};
		if (frame < T.back[0]) return {cx: SCR.w / 2 + 120, by: SCR.h - 26, size: 210};
		return {cx: SCR.w / 2 + 14, by: 420, size: 300};
	})();
	const noorPop =
		frame < T.doorsOpen ? springAt(frame, 10, fps, 11, 140) : frame < T.mission[0] ? turnS : frame < T.back[0] ? missionS : backS;

	// where things are on the output frame (for the taps and the end card)
	const scrLeft = devX + SCR.x;
	const scrTop = devY + SCR.y;
	const doneBtn = {x: scrLeft + SCR.w / 2 - 70, y: scrTop + SCR.h - 116};
	// Noor's place on the frame as the end card starts (device back on the parent's side, shrunk about its base)
	const endNoor = {
		cx: CX - 70 - DEV.w / 2 + DEV.w / 2 + (SCR.x + noorState.cx - DEV.w / 2) * shrink,
		by: DEV.top + DEV.h + (SCR.y + noorState.by - DEV.h) * shrink,
		size: noorState.size * shrink,
	};

	const cues: Cue[] = [
		{file: 'rustle', at: 0, vol: 0.5},
		{file: 'rustle', at: T.device + 4, vol: 0.4},
		...T.pin.map((at) => ({file: 'tick' as const, at, vol: 0.45})),
		{file: 'rustle', at: T.doorsIn, vol: 0.5},
		{file: 'rustle_long', at: T.handTo[0] - 2, vol: 0.4},
		{file: 'swish', at: T.doorsOpen, vol: 0.45},
		{file: 'drop', at: T.doorsOpen + 10, vol: 0.4},
		{file: 'rustle', at: T.mission[0], vol: 0.45},
		{file: 'tick', at: T.tapDone, vol: 0.55},
		{file: 'drop', at: T.tapDone + 3, vol: 0.5},
		{file: 'rustle', at: T.back[0], vol: 0.45},
		{file: 'rustle_long', at: T.handBack[0] - 2, vol: 0.4},
		{file: 'tick', at: T.lock, vol: 0.45},
		{file: 'air', at: T.lock + 4, vol: 0.4},
		...endCues(FROM),
	];

	const lockS = springAt(frame, T.lock, fps, 10, 170);

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
					<div
						style={{position: 'absolute', left: DEV.w / 2 - 50, top: 30, width: 100, height: 16, borderRadius: 8, background: C.ivory2}}
					/>
					{/* screen */}
					<div
						style={{
							position: 'absolute',
							left: SCR.x,
							top: SCR.y,
							width: SCR.w,
							height: SCR.h,
							borderRadius: SCR.r,
							background: C.ivory,
							overflow: 'hidden',
						}}
					>
						{/* 0 · the hand-over gate: the parent enters the code */}
						{gateS > 0.001 && (
							<div
								style={{
									position: 'absolute',
									inset: 0,
									opacity: gateS,
									display: 'flex',
									flexDirection: 'column',
									alignItems: 'center',
									paddingTop: 40,
								}}
							>
								<p style={txt({fontWeight: 900, fontSize: 48, lineHeight: 1.4, color: C.ink})}>{V4.gate}</p>
								<div style={{height: 330}} />
								<p style={txt({fontWeight: 700, fontSize: 38, lineHeight: 1.4, color: C.emerald})}>{V4.pin}</p>
								<PinDots frame={frame} at={T.pin} />
								<div style={{marginTop: 34}}>
									<Padlock size={84} gold={frame >= T.pin[3] + 4} />
								</div>
							</div>
						)}
						{/* 1 · «يا يوسف، دورك الآن» */}
						{turnS > 0.001 && (
							<div style={{position: 'absolute', left: 0, right: 0, top: 470, ...fadeRise(frame, T.doorsOpen + 12, fps, 24, T.turn[1])}}>
								<p style={txt({fontWeight: 900, fontSize: 66, lineHeight: 1.4, color: C.ink})}>
									{V4.yourTurn[0]}
									<br />
									{V4.yourTurn[1]}
								</p>
							</div>
						)}
						{/* 2 · a short mission, away from the screen */}
						{missionS > 0.001 && (
							<div
								style={{
									position: 'absolute',
									inset: 0,
									display: 'flex',
									flexDirection: 'column',
									alignItems: 'center',
									paddingTop: 46,
									gap: 18,
									transform: `scale(${missionS})`,
								}}
							>
								<Chip label={V4.missionLabel} sel={1} font={40} />
								<svg width={220} height={220} viewBox="0 0 220 220" style={{overflow: 'visible'}}>
									<SprigG x={110} y={196} size={200} pop={1} sway={2.5 * Math.sin(frame * 0.08)} />
									{/* drops of water fall on the sprig */}
									{[0, 1, 2].map((i) => {
										const ph = ((frame - T.mission[0] + i * 9) % 27) / 27;
										return <ellipse key={i} cx={70 + i * 34} cy={10 + ph * 120} rx={7} ry={10} fill={C.hill2} opacity={1 - ph} />;
									})}
								</svg>
								<p style={txt({fontWeight: 900, fontSize: 56, lineHeight: 1.4, color: C.ink})}>
									{V4.mission[0]}
									<br />
									{V4.mission[1]}
								</p>
							</div>
						)}
						{missionS > 0.001 && (
							<div
								style={{
									position: 'absolute',
									left: SCR.w / 2 - 70 - 120,
									width: 240,
									top: SCR.h - 116 - 40,
									display: 'flex',
									justifyContent: 'center',
									transform: `scale(${missionS})`,
								}}
							>
								<Chip label={V4.done} font={46} dark sel={doneSel} style={{minWidth: 200, boxSizing: 'border-box'}} />
							</div>
						)}
						{/* 3 · give the device back */}
						{backS > 0.001 && (
							<div style={{position: 'absolute', left: 0, right: 0, top: 470, transform: `scale(${backS})`}}>
								<p style={txt({fontWeight: 900, fontSize: 52, lineHeight: 1.4, color: C.ink})}>{V4.giveBack[0]}</p>
								<p style={txt({fontWeight: 900, fontSize: 52, lineHeight: 1.5, color: C.emerald})}>{V4.giveBack[1]}</p>
							</div>
						)}

						{noorPop > 0.001 && (
							<Noor
								frame={frame}
								{...noorState}
								size={noorState.size * noorPop}
								eyes={nEyes}
								mouth={nMouth}
								sparkles={nSpark}
								heart={nHeart}
							/>
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

			<Tap x={doneBtn.x} y={doneBtn.y} frame={frame} at={T.tapDone} />

			<Caption lines={[V4.hook.join(' ')]} top={300} font={100} style={fadeRise(frame, T.hook[0], fps, 30, T.hook[1])} />
			<Caption lines={V4.message} top={296} font={72} style={fadeRise(frame, T.message, fps, 30, FROM - 4)} />

			<EndCard frame={frame} fps={fps} from={FROM} slug="v4_handover" tagline={V4.tagline} noorFrom={endNoor} />
			<Watermark frame={frame} fps={fps} hideAt={FROM} />
			{safe ? <SafeZones /> : null}
			<ReelSound cues={cues} total={V4_TOTAL} gain={1.34} />
		</AbsoluteFill>
	);
};

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
