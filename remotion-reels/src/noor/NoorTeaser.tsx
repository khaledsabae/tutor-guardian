// «المربّي» teaser — Noor peeks out of a paper-cut night and lights the way.
// One component, three cuts: NoorTeaserAr / NoorTeaserEn (1080×1920) and
// NoorTeaserArWide (1920×1080). Everything moves like paper: sheets slide
// and settle on springs, things pop and unroll; nothing morphs or blurs.
import React, {useMemo} from 'react';
import {AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Cairo';
import {C} from './palette';
import {COPY, Lang} from './copy';
import {hillD, Road} from './geometry';
import {Layout, portrait, SheetName, wide} from './layouts';
import {LanternG, NoorArt, SprigG, StarShape, WalkersG} from './art';
import {TeaserSound} from './sound';
import {T} from './timeline';
import {QR, QrCut} from './qr';

const {fontFamily} = loadFont('normal', {
	weights: ['700', '900'],
	subsets: ['arabic', 'latin'],
	ignoreTooManyRequestsWarning: true,
});

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const springAt = (frame: number, start: number, fps: number, damping = 12, stiffness = 100, mass = 1) =>
	frame < start ? 0 : spring({frame: frame - start, fps, config: {damping, stiffness, mass}});

const eased = (frame: number, a: number, b: number, easing = Easing.inOut(Easing.cubic)) =>
	interpolate(frame, [a, b], [0, 1], {...clamp, easing});

/** A whole sheet leaves: a small lift, then it drops away. */
const exitDrop = (frame: number, start: number, dist: number) =>
	interpolate(frame, [start, start + 26], [0, dist], {...clamp, easing: Easing.back(1.4)});

const SHEET_COLOR: Record<SheetName, string> = {far: C.hill2, mid: C.hill3, near: C.shadow};

// `qrCut`: which campaign code the end card's QR carries (src/noor/qr.ts);
// by default the cut's own — en, wide, or ar.
export type TeaserProps = {lang: Lang; shape: 'portrait' | 'wide'; qrCut?: QrCut};

export const NoorTeaser: React.FC<TeaserProps> = ({lang, shape, qrCut: qrCutProp}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const L: Layout = shape === 'wide' ? wide : portrait;
	const copy = COPY[lang];
	const rtl = lang === 'ar';
	const {W, H, k} = L;
	const id = `${lang}-${shape}`;

	const roads = useMemo(() => L.roads.map((r) => new Road(r.ctrl)), [L]);
	const hillPaths = useMemo(
		() => ({
			far: hillD(L.sheets.far.crest, H + 1400),
			mid: hillD(L.sheets.mid.crest, H + 1400),
			near: hillD(L.sheets.near.crest, H + 1400),
			mound: hillD(L.mound.crest, H + 1600),
		}),
		[L, H],
	);

	// ── camera drift (very slow parallax pan; sheets move at different rates) ─
	const driftE = interpolate(frame, [0, T.exit], [0, 1], {...clamp, easing: Easing.inOut(Easing.sin)});
	const dx = {
		stars: -L.drift.stars * driftE,
		far: -L.drift.far * driftE,
		mid: -L.drift.mid * driftE,
		near: -L.drift.mid * driftE,
		front: -L.drift.front * driftE,
	};

	// ── intro slides & exits ────────────────────────────────────────────────
	const slide = (i: number, dist: number) => dist * (1 - springAt(frame, T.hills[i], fps, 12, 80));
	// The front mound leaves first; the three back sheets leave together so no
	// hidden end of a road piece is ever uncovered on the way out.
	const exFront = exitDrop(frame, T.exit, H * 0.9);
	const exMid = exitDrop(frame, T.exit + 5, H * 0.9);
	const exFar = exMid;
	const sceneGone = frame > T.exit + 40;
	const dy: Record<SheetName | 'mound', number> = {
		far: slide(0, L.sheets.far.slide) + exFar,
		mid: slide(1, L.sheets.mid.slide) + exMid,
		near: slide(2, L.sheets.near.slide) + exMid,
		mound: slide(3, L.mound.slide) + exFront,
	};

	// ── stars ───────────────────────────────────────────────────────────────
	// On the end card, stars that would sit under the logo, Noor or the text
	// pop away (so nothing twinkles through the title).
	const E0 = L.end;
	const qrStackH = E0.qr.place === 'stack' ? E0.qr.size + E0.qr.scan * 1.6 + E0.gap * 2 : 0;
	const endTextH = E0.title * 1.3 + E0.tagline * 3 + E0.free * 1.5 + E0.play * 2.2 + E0.gap * 4 + qrStackH;
	const keepOut = [
		[E0.logoCx - E0.logoSize / 2 - 70, E0.logoCy - E0.logoSize / 2 - 70, E0.logoCx + E0.logoSize / 2 + 70, E0.logoCy + E0.logoSize / 2 + 70],
		[E0.textCx - E0.textWidth / 2 - 30, E0.textTop - 40, E0.textCx + E0.textWidth / 2 + 30, E0.textTop + endTextH],
	];
	const noorSideX =
		E0.noorSide === 'left'
			? [E0.logoCx - E0.logoSize / 2 - E0.noorSize * 0.85, E0.logoCx - E0.logoSize / 2]
			: [E0.logoCx + E0.logoSize / 2, E0.logoCx + E0.logoSize / 2 + E0.noorSize * 0.85];
	keepOut.push([noorSideX[0], E0.logoCy - E0.logoSize / 2 - 70, noorSideX[1], E0.logoCy + E0.logoSize / 2 + 40]);
	if (E0.qr.place === 'abs') {
		const h = E0.qr.size / 2 + 50;
		keepOut.push([E0.qr.cx - h, E0.qr.cy - h, E0.qr.cx + h, E0.qr.cy + h + E0.qr.scan * 2]);
	}
	const Wm = L.watermark;
	const underWatermark = (x: number, y: number) =>
		x > Wm.x - 30 && x < Wm.x + Wm.size + 30 && y > Wm.y - 30 && y < Wm.y + Wm.size + 30;
	const starAway = springAt(frame, T.exit + 10, fps, 14, 120);
	const starEls = L.stars.map((s, i) => {
		if (underWatermark(s.x, s.y)) return null;
		const hidden = keepOut.some(([x0, y0, x1, y1]) => s.x > x0 && s.x < x1 && s.y > y0 && s.y < y1);
		const pop = springAt(frame, 2 + i * 3, fps, 10, 120) * (hidden ? 1 - starAway : 1);
		const tw = 1 + (s.gold ? 0.12 : 0.08) * Math.sin((frame * 2 * Math.PI) / (64 + (i % 5) * 9) + i * 1.3);
		return <StarShape key={i} x={s.x} y={s.y} r={s.r} gold={!!s.gold} scale={pop * tw} />;
	});

	// ── road pieces (one per sheet) ─────────────────────────────────────────
	const roadAll = eased(frame, T.path[0], T.path[1], Easing.inOut(Easing.sin));
	let acc = 0;
	const roadP = L.roads.map((r) => {
		const p = Math.min(1, Math.max(0, (roadAll - acc) / r.share));
		acc += r.share;
		return p;
	});
	const reachFrame = (ri: number, t: number) => {
		for (let f = T.path[0]; f <= T.path[1]; f++) {
			const all = eased(f, T.path[0], T.path[1], Easing.inOut(Easing.sin));
			const start = L.roads.slice(0, ri).reduce((a, r) => a + r.share, 0);
			if ((all - start) / L.roads[ri].share >= t) return f;
		}
		return T.path[1];
	};

	// lanterns: pop when the road reaches them, light near → far
	const lanterns = L.lanterns.map((ln, i) => {
		const s = roads[ln.road].at(ln.t);
		const off = s.w / 2 + ln.size * 0.42;
		return {
			sheet: L.roads[ln.road].sheet,
			x: s.x + ln.side * s.nx * off,
			y: s.y + ln.side * s.ny * off,
			size: ln.size,
			pop: springAt(frame, reachFrame(ln.road, ln.t) + 2, fps, 10, 160),
			flame: springAt(frame, T.lights[i], fps, 9, 150),
			glow: springAt(frame, T.lights[i] + 3, fps, 18, 70),
			flicker: 0.6 * Math.sin(frame * 0.33 + i * 1.7) + 0.4 * Math.sin(frame * 0.13 + i),
		};
	});

	// ── walkers (on the near sheet) ─────────────────────────────────────────
	const walkRoad = roads[L.walk.road];
	const walkE = eased(frame, T.walk[0], T.walk[1], Easing.inOut(Easing.sin));
	const wt = L.walk.t0 + (L.walk.t1 - L.walk.t0) * walkE;
	const wPt = walkRoad.at(wt);
	const w0 = walkRoad.at(L.walk.t0).w;
	const wSize = L.walk.size * Math.pow(wPt.w / w0, 0.5);
	const phase = walkE * 9 * Math.PI;
	const walking = frame > T.walk[0] && frame < T.walk[1];
	const stepA = walking ? Math.abs(Math.sin(phase)) * 2.4 : 0;
	const stepB = walking ? Math.abs(Math.sin(phase + Math.PI / 2)) * 3 : 0;
	const swayA = walking ? Math.sin(phase) * 1.3 : 0;
	const swayB = walking ? Math.sin(phase + Math.PI / 2) * 1.8 : 0;
	// parent's hood top, after mirroring (the parent ends up on the right)
	const parentHead = {
		x: wPt.x + ((106.5 - 88) / 130) * wSize + dx.near,
		y: wPt.y - ((200 - 86) / 130) * wSize + dy.near,
	};

	// ── Noor ────────────────────────────────────────────────────────────────
	const S0 = L.noor.size;
	const sc0 = S0 / 240;
	const hiddenY = L.noor.crestY + 12;
	const peekY = L.noor.crestY - 138.5 * sc0; // eyes just clear the crest, cheeks stay hidden
	const happyY = L.noor.crestY - 184 * sc0;
	const rise = springAt(frame, T.noorRise, fps, 11, 70);
	const up2 = springAt(frame, T.happy, fps, 8, 170);
	const hop = frame >= T.happy2 ? Math.sin(Math.PI * Math.min(1, (frame - T.happy2) / 14)) * 34 * k : 0;
	let ny = hiddenY + (peekY - hiddenY) * rise + (happyY - peekY) * up2 - hop;
	let nx = L.noor.cx - S0 / 2 + dx.front;
	let nSize = S0;

	const look = (() => {
		const [a, b, c, d, e, f] = T.look;
		if (frame < a || frame >= f) return 0;
		if (frame < b) return -eased(frame, a, b);
		if (frame < c) return -1;
		if (frame < d) return -1 + 2 * eased(frame, c, d);
		if (frame < e) return 1;
		return 1 - eased(frame, e, f);
	})();
	const tilt = look * 4;

	// end-card target: sitting on the logo tile's baseline, beside it
	const E = L.end;
	const eS = E.noorSize;
	const eSc = eS / 240;
	// The real logo is round (with an ivory paper rim), so Noor sits on the
	// same ground line and keeps a small gap to the circle at his own height.
	const logoMat = 10 * k;
	const logoR = E.logoSize / 2 + logoMat;
	const eNoorY = E.logoCy + logoR - 194 * eSc;
	const circleHalfWidthAt = (y: number) => Math.sqrt(Math.max(0, logoR * logoR - (y - E.logoCy) * (y - E.logoCy)));
	const eNoorX =
		E.noorSide === 'left'
			? E.logoCx - circleHalfWidthAt(eNoorY + 156 * eSc) - 16 * k - 177.5 * eSc
			: E.logoCx + circleHalfWidthAt(eNoorY + 132 * eSc) + 16 * k - 57.6 * eSc;

	if (frame >= T.exit) {
		const p = eased(frame, T.exit, T.land, Easing.inOut(Easing.cubic));
		const sx = L.noor.cx - S0 / 2 - L.drift.front;
		nx = sx + (eNoorX - sx) * p;
		ny = happyY + (eNoorY - happyY) * p - Math.sin(Math.PI * p) * 240 * k;
		nSize = S0 + (eS - S0) * p;
	}
	const landS = springAt(frame, T.land, fps, 7, 220);
	const squash = frame >= T.land ? (1 - landS) * 0.12 : 0;
	const happyPulse =
		frame >= T.happy && frame < T.happy + 14 ? Math.sin((Math.PI * (frame - T.happy)) / 14) * 0.05 : 0;
	const breathe = 0.02 * Math.sin((frame * 2 * Math.PI) / 75);
	const nScaleX = 1 + breathe * 0.5 + squash * 0.6;
	const nScaleY = 1 + breathe + happyPulse - squash;

	// expression
	let eyes: 'open' | 'closed' | 'happy' = 'open';
	let mouth: 'smile' | 'calm' | 'open' = 'smile';
	let sparkles = 0;
	let heart = 0;
	const blinking = (b: number) => frame >= b && frame < b + 4;
	if (frame < T.happy) {
		eyes = T.blinks.some(blinking) ? 'closed' : 'open';
	} else if (frame < T.tender) {
		eyes = 'happy';
		mouth = 'open';
		sparkles = springAt(frame, T.happy + 2, fps, 9, 160);
	} else if (frame < T.happy2) {
		eyes = 'closed';
		mouth = 'calm';
		heart = springAt(frame, T.tender + 4, fps, 9, 160);
	} else if (frame < T.land) {
		eyes = 'happy';
		mouth = 'open';
		sparkles = springAt(frame, T.happy2 + 2, fps, 9, 160);
	} else {
		eyes = blinking(T.endBlink) ? 'closed' : 'open';
		mouth = 'open';
	}

	// ── text helpers ────────────────────────────────────────────────────────
	const textBase: React.CSSProperties = {
		fontFamily,
		direction: rtl ? 'rtl' : 'ltr',
		textAlign: 'center',
		color: C.ivory,
		margin: 0,
	};
	// Even line lengths when a line wraps (English copy is longer).
	const balance = {textWrap: 'balance'} as React.CSSProperties;
	const capFont = L.caption.font * (rtl ? 1 : 0.86);
	const paperShadow = (s: number) => `${(4 * s).toFixed(1)}px ${(5 * s).toFixed(1)}px 0 ${C.shadow}`;

	// caption
	const capIn = springAt(frame, T.caption[0], fps, 200, 60);
	const capOut = eased(frame, T.caption[1], T.caption[1] + 14, Easing.in(Easing.cubic));
	const capOpacity = capIn * (1 - capOut);
	const capY = (1 - capIn) * 30 * k - capOut * 16 * k;

	// bubbles
	const bubbleScale = (start: number, end: number) => {
		if (frame < start) return 0;
		const inS = springAt(frame, start, fps, 11, 180);
		const out = eased(frame, end, end + 8, Easing.in(Easing.cubic));
		return inS * (1 - out);
	};
	const askS = bubbleScale(T.ask[0], T.ask[1]);
	const ansS = bubbleScale(T.answer[0], T.answer[1]);
	const noorTop = {x: nx + 110 * (nSize / 240), y: ny + 68 * (nSize / 240)};

	const bubble = (text: string, tipX: number, tipY: number, frac: number, s: number) => {
		if (s <= 0.001) return null;
		const tail = 36 * k;
		const pad = 26 * k;
		return (
			<div
				style={{
					position: 'absolute',
					left: tipX,
					top: tipY - tail,
					transform: `translate(${-frac * 100}%, -100%)`,
				}}
			>
				<div style={{transform: `scale(${s})`, transformOrigin: `${frac * 100}% calc(100% + ${tail}px)`}}>
					<div
						style={{
							...textBase,
							position: 'relative',
							background: C.ivory,
							color: C.ink,
							fontWeight: 700,
							fontSize: L.bubble.font,
							lineHeight: 1.35,
							padding: `${pad * 0.6}px ${pad * 1.4}px ${pad * 0.8}px`,
							borderRadius: 34 * k,
							boxShadow: `${10 * k}px ${12 * k}px 0 ${C.shadow}`,
							width: 'max-content',
							maxWidth: L.bubble.maxWidth,
							...balance,
						}}
					>
						{text}
						<svg
							width={tail * 1.5}
							height={tail}
							viewBox="0 0 48 34"
							preserveAspectRatio="none"
							style={{
								position: 'absolute',
								left: `calc(${frac * 100}% - ${tail * 0.75}px)`,
								top: '100%',
								marginTop: -1,
								overflow: 'visible',
							}}
						>
							<path d="M6 0 L42 0 L24 34 Z" fill={C.shadow} transform="translate(9 10)" />
							<path d="M6 -2 L42 -2 L24 34 Z" fill={C.ivory} />
						</svg>
					</div>
				</div>
			</div>
		);
	};

	// end card
	const logoS = springAt(frame, T.logo, fps, 11, 120);
	const fadeRise = (start: number) => {
		const s = springAt(frame, start, fps, 200, 70);
		return {opacity: s, transform: `translateY(${(1 - s) * 34 * k}px)`};
	};
	const playS = springAt(frame, T.play, fps, 11, 160);
	const qrS = springAt(frame, T.qr, fps, 12, 140);
	const qrCut: QrCut = qrCutProp ?? (lang === 'en' ? 'en' : shape === 'wide' ? 'wide' : 'ar');
	const qr = QR[qrCut];
	// whole pixels per module keep the code crisp
	const qrPx = Math.max(1, Math.round(E.qr.size / qr.n)) * qr.n;
	const qrCard = (
		<div style={{position: 'relative', width: qrPx, height: qrPx, transform: `scale(${qrS})`}}>
			<div
				style={{
					position: 'absolute',
					inset: 0,
					borderRadius: (qrPx / qr.n) * 1.6,
					background: C.shadow,
					transform: `translate(${8 * k}px, ${10 * k}px)`,
				}}
			/>
			<svg width={qrPx} height={qrPx} viewBox={`0 0 ${qr.n} ${qr.n}`} shapeRendering="crispEdges" style={{position: 'absolute', inset: 0}}>
				<rect width={qr.n} height={qr.n} rx={1.6} fill={C.ivory} />
				<path d={qr.d} fill={C.ink} />
			</svg>
		</div>
	);
	const scanLine = (
		<p style={{...textBase, ...fadeRise(T.scan), fontWeight: 700, fontSize: E.qr.scan, lineHeight: 1.4, color: C.ivory2}}>{copy.scan}</p>
	);
	const endHillY = (i: number) => (H * 0.35 + 80 * i) * (1 - springAt(frame, T.endHills + i * 6, fps, 12, 80));

	// one hill sheet with its road piece (clipped to the sheet) and lanterns
	const sheet = (name: SheetName) => {
		const clipId = `clip-${id}-${name}`;
		const d = hillPaths[name];
		const ri = L.roads.findIndex((r) => r.sheet === name);
		const rd = ri >= 0 ? roads[ri].outline(roadP[ri]) : '';
		return (
			<svg
				key={name}
				width={W}
				height={H}
				viewBox={`0 0 ${W} ${H}`}
				style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', transform: `translate(${dx[name]}px, ${dy[name]}px)`}}
			>
				<defs>
					<clipPath id={clipId}>
						<path d={d} />
					</clipPath>
				</defs>
				<path d={d} fill={SHEET_COLOR[name]} />
				{rd ? (
					<g clipPath={`url(#${clipId})`}>
						<path d={rd} fill={name === 'near' ? C.ink : C.shadow} transform={`translate(${7 * k} ${9 * k})`} />
						<path d={rd} fill={C.ivory} />
					</g>
				) : null}
				{lanterns
					.filter((l) => l.sheet === name)
					.sort((a, b) => a.y - b.y)
					.map((l, i) => (
						<LanternG key={i} x={l.x} y={l.y} size={l.size} pop={l.pop} flame={l.flame} glow={l.glow} flicker={l.flicker} />
					))}
				{name === 'near' && frame >= T.walk[0] ? (
					<WalkersG
						x={wPt.x}
						y={wPt.y}
						size={wSize}
						mirror
						pop={springAt(frame, T.walk[0], fps, 11, 150)}
						stepA={stepA}
						stepB={stepB}
						swayA={swayA}
						swayB={swayB}
					/>
				) : null}
			</svg>
		);
	};

	return (
		<AbsoluteFill style={{background: C.emerald, overflow: 'hidden'}}>
			{/* stars */}
			<svg width={W} height={H} style={{position: 'absolute', transform: `translateX(${dx.stars}px)`}}>
				{starEls}
			</svg>

			{!sceneGone && (
				<>
					{sheet('far')}
					{sheet('mid')}
					{sheet('near')}
				</>
			)}

			{/* Noor sits between the near sheet and the front mound */}
			{frame >= T.noorRise && (
				<div
					style={{
						position: 'absolute',
						left: nx,
						top: ny,
						width: nSize,
						height: nSize,
						transform: `rotate(${tilt}deg) scale(${nScaleX}, ${nScaleY})`,
						transformOrigin: `${nSize / 2}px ${(194 / 240) * nSize}px`,
					}}
				>
					<NoorArt
						eyes={eyes}
						mouth={mouth}
						look={look}
						sparkles={sparkles}
						sparkleTwinkle={frame * 0.12}
						heart={heart}
						heartFloat
						size={nSize}
					/>
				</div>
			)}

			{!sceneGone && (
				<svg
					width={W}
					height={H}
					style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', transform: `translate(${dx.front}px, ${dy.mound}px)`}}
				>
					<path d={hillPaths.mound} fill={C.hill2} />
					{L.sprigs.map((s, i) => (
						<SprigG
							key={i}
							x={s.x}
							y={s.y}
							size={s.size}
							pop={springAt(frame, T.hills[3] + 14 + i * 5, fps, 10, 140)}
							sway={s.rot + 2.5 * Math.sin(frame * 0.07 + i * 1.9)}
						/>
					))}
				</svg>
			)}

			{/* caption */}
			{capOpacity > 0.001 && (
				<div
					style={{
						position: 'absolute',
						left: (W - L.caption.width) / 2,
						top: L.caption.top,
						width: L.caption.width,
						opacity: capOpacity,
						transform: `translateY(${capY}px)`,
					}}
				>
					<p style={{...textBase, ...balance, fontWeight: 900, fontSize: capFont, lineHeight: 1.5, textShadow: paperShadow(1.6 * k)}}>
						{L.caption.oneLine ? (
							copy.caption.join(' ')
						) : (
							<>
								{copy.caption[0]}
								<br />
								{copy.caption[1]}
							</>
						)}
					</p>
				</div>
			)}

			{bubble(copy.ask, noorTop.x, noorTop.y - L.bubble.lift, L.bubble.askFrac, askS)}
			{bubble(copy.answer, parentHead.x, parentHead.y - L.bubble.lift, L.bubble.answerFrac, ansS)}

			{/* end card */}
			{frame >= T.exit && (
				<>
					{E.hills.map((crest, i) => (
						<svg
							key={i}
							width={W}
							height={H}
							style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', transform: `translateY(${endHillY(i)}px)`}}
						>
							<path d={hillD(crest, H + 800)} fill={[C.hill2, C.hill3, C.shadow][i]} />
						</svg>
					))}
					{logoS > 0.001 && (
						<div
							style={{
								position: 'absolute',
								left: E.logoCx - logoR,
								top: E.logoCy - logoR,
								width: logoR * 2,
								height: logoR * 2,
								transform: `scale(${logoS})`,
							}}
						>
							{/* paper shadow, then an ivory rim so the teal disc reads on the emerald card */}
							<div
								style={{
									position: 'absolute',
									inset: 0,
									borderRadius: '50%',
									background: C.shadow,
									transform: `translate(${14 * k}px, ${18 * k}px)`,
								}}
							/>
							<div style={{position: 'absolute', inset: 0, borderRadius: '50%', background: C.ivory}} />
							<Img
								src={staticFile('noor/app_logo_round.png')}
								style={{position: 'absolute', left: logoMat, top: logoMat, width: E.logoSize, height: E.logoSize}}
							/>
						</div>
					)}
					<div
						style={{
							position: 'absolute',
							left: E.textCx - E.textWidth / 2,
							top: E.textTop,
							width: E.textWidth,
							display: 'flex',
							flexDirection: 'column',
							alignItems: 'center',
							gap: E.gap,
						}}
					>
						<p style={{...textBase, ...fadeRise(T.title), fontWeight: 900, fontSize: E.title, lineHeight: 1.5, textShadow: paperShadow(2.2 * k)}}>
							{copy.title}
						</p>
						<p style={{...textBase, ...balance, ...fadeRise(T.tagline), fontWeight: 700, fontSize: E.tagline, lineHeight: 1.4, textShadow: paperShadow(1.1 * k)}}>
							{copy.tagline}
						</p>
						<p style={{...textBase, ...balance, ...fadeRise(T.free), fontWeight: 700, fontSize: E.free, lineHeight: 1.4, color: C.ivory2}}>
							{copy.free}
						</p>
						<div
							style={{
								...textBase,
								marginTop: E.gap * 0.8,
								transform: `scale(${playS})`,
								background: C.ivory,
								color: C.ink,
								fontWeight: 700,
								fontSize: E.play,
								lineHeight: 1.3,
								padding: `${12 * k}px ${44 * k}px ${16 * k}px`,
								borderRadius: 999,
								boxShadow: `${8 * k}px ${10 * k}px 0 ${C.shadow}`,
							}}
						>
							{copy.play}
						</div>
						{E.qr.place === 'stack' && (
							<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: E.gap * 0.6, marginTop: E.gap * 0.5}}>
								{qrCard}
								{scanLine}
							</div>
						)}
					</div>
					{E.qr.place === 'abs' && (
						<div
							style={{
								position: 'absolute',
								left: E.qr.cx - 300,
								top: E.qr.cy - qrPx / 2,
								width: 600,
								display: 'flex',
								flexDirection: 'column',
								alignItems: 'center',
								gap: E.gap * 0.8,
							}}
						>
							{qrCard}
							{scanLine}
						</div>
					)}
				</>
			)}

			{/* the real app logo, small, in a corner clear of the platform UI, whole video */}
			<div
				style={{
					position: 'absolute',
					left: Wm.x,
					top: Wm.y,
					width: Wm.size,
					height: Wm.size,
					opacity: 0.85,
					transform: `scale(${springAt(frame, 8, fps, 12, 120)})`,
				}}
			>
				<div
					style={{
						position: 'absolute',
						inset: 0,
						borderRadius: '50%',
						background: C.shadow,
						transform: `translate(${3 * k}px, ${4 * k}px)`,
					}}
				/>
				<Img src={staticFile('noor/app_logo_round.png')} style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}} />
			</div>

			<TeaserSound />
		</AbsoluteFill>
	);
};
