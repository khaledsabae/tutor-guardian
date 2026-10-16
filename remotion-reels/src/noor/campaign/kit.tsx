// Shared parts of the five «المربّي» campaign reels (1080×1920 only).
// Built on the teaser's art (art.tsx, geometry.ts, palette.ts) and its rules:
// flat palette colours, paper shadows offset without blur, things slide, pop
// and unroll on springs — nothing morphs, nothing is blurred, no gradients.
//
// Every reel keeps its words and its main characters inside the SAFE box:
// the Reels/Shorts/TikTok interface covers the top 14 %, the bottom 20 % and
// the right 15 % of the frame.
import React from 'react';
import {Easing, Img, interpolate, spring, staticFile} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Cairo';
import {C} from '../palette';
import {Eyes, Mouth, NoorArt, StarShape} from '../art';
import {hillD, P, star8} from '../geometry';
import {portrait, StarSpec} from '../layouts';
import {QR, Slug} from './qr';
import {END} from './copy';

const cairo = loadFont('normal', {
	weights: ['700', '900'],
	subsets: ['arabic', 'latin'],
	ignoreTooManyRequestsWarning: true,
});
export const fontFamily = cairo.fontFamily;

export const W = 1080;
export const H = 1920;
export const SAFE = {left: 48, right: Math.round(W * 0.85), top: Math.round(H * 0.14), bottom: Math.round(H * 0.8)};
/** Centre of the safe column (the right 15 % is covered by the like/share buttons). */
export const CX = Math.round((SAFE.left + SAFE.right) / 2);
export const COL = 820; // text column width, centred on CX

// ── motion helpers ───────────────────────────────────────────────────────────
export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export const springAt = (frame: number, start: number, fps: number, damping = 12, stiffness = 100, mass = 1) =>
	frame < start ? 0 : spring({frame: frame - start, fps, config: {damping, stiffness, mass}});

export const eased = (frame: number, a: number, b: number, easing = Easing.inOut(Easing.cubic)) =>
	interpolate(frame, [a, b], [0, 1], {...clamp, easing});

/** Pops in at `a` (spring), folds away over `out` frames from `b`. */
export const showFor = (frame: number, a: number, b: number, fps: number, out = 8, damping = 11, stiffness = 170) => {
	if (frame < a) return 0;
	return springAt(frame, a, fps, damping, stiffness) * (1 - eased(frame, b, b + out, Easing.in(Easing.cubic)));
};

/** A soft settle (no overshoot) — for lines of text. */
export const fadeRise = (frame: number, a: number, fps: number, dist = 30, b = Infinity, out = 10): React.CSSProperties => {
	const s = springAt(frame, a, fps, 200, 70);
	const o = b === Infinity ? 0 : eased(frame, b, b + out, Easing.in(Easing.cubic));
	return {opacity: s * (1 - o), transform: `translateY(${(1 - s) * dist - o * dist * 0.5}px)`};
};

/** A hop along an arc from p0 to p1 between frames a and b. */
export const hop = (frame: number, a: number, b: number, p0: [number, number], p1: [number, number], height = 160) => {
	const p = eased(frame, a, b, Easing.inOut(Easing.quad));
	return {
		x: p0[0] + (p1[0] - p0[0]) * p,
		y: p0[1] + (p1[1] - p0[1]) * p - Math.sin(Math.PI * p) * height,
		p,
	};
};

// ── text ─────────────────────────────────────────────────────────────────────
export const paperText = (s: number) => `${(4 * s).toFixed(1)}px ${(5 * s).toFixed(1)}px 0 ${C.shadow}`;

export const txt = (extra: React.CSSProperties = {}): React.CSSProperties =>
	({
		fontFamily,
		direction: 'rtl',
		textAlign: 'center',
		color: C.ivory,
		margin: 0,
		textWrap: 'balance',
		...extra,
	}) as React.CSSProperties;

/** Big burnt-in caption (the hook, the message): lines centred on the safe column. */
export const Caption: React.FC<{
	lines: string[];
	top: number;
	style: React.CSSProperties; // usually fadeRise(...)
	font?: number;
	color?: string;
	shadow?: boolean;
}> = ({lines, top, style, font = 84, color = C.ivory, shadow = true}) => {
	if ((style.opacity as number) <= 0.001) return null;
	return (
		<div style={{position: 'absolute', left: CX - COL / 2, top, width: COL, ...style}}>
			<p style={txt({fontWeight: 900, fontSize: font, lineHeight: 1.45, color, textShadow: shadow ? paperShadowFor(color, font) : 'none'})}>
				{lines.map((l, i) => (
					<React.Fragment key={i}>
						{i > 0 ? <br /> : null}
						{l}
					</React.Fragment>
				))}
			</p>
		</div>
	);
};
// Ivory words get the dark paper shadow; ink words (on a coral/ivory sky) a light one.
const paperShadowFor = (color: string, font: number) => {
	const s = font / 50;
	return color === C.ink ? `${(3 * s).toFixed(1)}px ${(4 * s).toFixed(1)}px 0 ${C.ivory}` : paperText(s);
};

// ── paper pieces ─────────────────────────────────────────────────────────────
/** An ivory paper card with a flat, offset shadow. Positioned by the caller. */
export const Paper: React.FC<{
	style?: React.CSSProperties;
	color?: string;
	shadow?: string;
	off?: number;
	radius?: number;
	children?: React.ReactNode;
}> = ({style, color = C.ivory, shadow = C.shadow, off = 12, radius = 34, children}) => (
	<div
		style={{
			background: color,
			borderRadius: radius,
			boxShadow: `${off * 0.85}px ${off}px 0 ${shadow}`,
			...style,
		}}
	>
		{children}
	</div>
);

/** Rounded pill: a choice or a button. `sel` 0…1 swaps its paper to gold. */
export const Chip: React.FC<{label: string; sel?: number; font?: number; dark?: boolean; style?: React.CSSProperties}> = ({
	label,
	sel = 0,
	font = 44,
	dark = false,
	style,
}) => {
	const on = sel > 0.5;
	const bump = 1 + 0.1 * Math.sin(Math.PI * Math.min(1, sel));
	return (
		<div
			style={{
				...txt({fontWeight: 700, fontSize: font, lineHeight: 1.3}),
				color: on ? C.ink : dark ? C.ivory : C.ink,
				background: on ? C.gold : dark ? C.emerald : C.ivory2,
				padding: `${font * 0.22}px ${font * 0.7}px ${font * 0.32}px`,
				borderRadius: 999,
				boxShadow: `${font * 0.12}px ${font * 0.15}px 0 ${on ? C.shadow : dark ? C.shadow : C.ivory3}`,
				transform: `scale(${bump})`,
				whiteSpace: 'nowrap',
				...style,
			}}
		>
			{label}
		</div>
	);
};

/** A fingertip comes in, presses at `at`, a flat ring spreads; then it leaves. */
export const Tap: React.FC<{x: number; y: number; frame: number; at: number}> = ({x, y, frame, at}) => {
	if (frame < at - 10 || frame > at + 22) return null;
	const inP = eased(frame, at - 10, at - 2, Easing.out(Easing.cubic));
	const press = frame >= at - 2 && frame < at + 4 ? 0.82 : 1;
	const outP = eased(frame, at + 8, at + 18, Easing.in(Easing.cubic));
	const ring = eased(frame, at, at + 16, Easing.out(Easing.cubic));
	const r = 34;
	return (
		<svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', pointerEvents: 'none'}}>
			{frame >= at && ring < 1 ? (
				<circle cx={x} cy={y} r={r + ring * 60} fill="none" stroke={C.ivory} strokeWidth={8 * (1 - ring)} opacity={1 - ring} />
			) : null}
			<g transform={`translate(${x + 60 * (1 - inP) + 40 * outP} ${y + 90 * (1 - inP) + 60 * outP}) scale(${press})`} opacity={1 - outP}>
				<circle cx={6} cy={8} r={r} fill={C.shadow} />
				<circle cx={0} cy={0} r={r} fill={C.coral} />
				<circle cx={-9} cy={-10} r={9} fill={C.ivory} opacity={0.55} />
			</g>
		</svg>
	);
};

/** A speech bubble (paper card with a tail) whose tail tip sits at (tipX, tipY). */
export const Bubble: React.FC<{
	tipX: number;
	tipY: number;
	frac: number; // where the tail sits along the bubble's width, 0…1 (from the left)
	s: number;
	font?: number;
	maxWidth?: number;
	children: React.ReactNode;
}> = ({tipX, tipY, frac, s, font = 52, maxWidth = 780, children}) => {
	if (s <= 0.001) return null;
	const tail = 36;
	const pad = 26;
	return (
		<div style={{position: 'absolute', left: tipX, top: tipY - tail, transform: `translate(${-frac * 100}%, -100%)`}}>
			<div style={{transform: `scale(${s})`, transformOrigin: `${frac * 100}% calc(100% + ${tail}px)`}}>
				<div
					style={{
						...txt({fontWeight: 700, fontSize: font, lineHeight: 1.4, color: C.ink}),
						position: 'relative',
						background: C.ivory,
						padding: `${pad * 0.6}px ${pad * 1.4}px ${pad * 0.8}px`,
						borderRadius: 34,
						boxShadow: `10px 12px 0 ${C.shadow}`,
						width: 'max-content',
						maxWidth,
					}}
				>
					{children}
					<svg
						width={tail * 1.5}
						height={tail}
						viewBox="0 0 48 34"
						preserveAspectRatio="none"
						style={{position: 'absolute', left: `calc(${frac * 100}% - ${tail * 0.75}px)`, top: '100%', marginTop: -1, overflow: 'visible'}}
					>
						<path d="M6 0 L42 0 L24 34 Z" fill={C.shadow} transform="translate(9 10)" />
						<path d="M6 -2 L42 -2 L24 34 Z" fill={C.ivory} />
					</svg>
				</div>
			</div>
		</div>
	);
};

/** Three ink dots that bob one after the other — Noor is thinking. */
export const Dots: React.FC<{frame: number; size?: number}> = ({frame, size = 22}) => (
	<div style={{display: 'flex', gap: size * 0.8, padding: `${size * 0.6}px ${size * 0.4}px`, direction: 'ltr'}}>
		{[0, 1, 2].map((i) => {
			const b = Math.max(0, Math.sin((frame - i * 5) * 0.32));
			return (
				<div
					key={i}
					style={{width: size, height: size, borderRadius: '50%', background: C.ink, transform: `translateY(${-b * size * 0.7}px)`}}
				/>
			);
		})}
	</div>
);

// ── the sky, the hills ───────────────────────────────────────────────────────
/** The teaser's star field; `away` 0…1 pops them back off (dawn). */
export const Stars: React.FC<{
	frame: number;
	fps: number;
	at?: number;
	away?: number;
	stars?: StarSpec[];
	skip?: (s: StarSpec) => boolean;
}> = ({frame, fps, at = 0, away = 0, stars = portrait.stars, skip}) => (
	<svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0}}>
		{stars.map((s, i) => {
			if (skip && skip(s)) return null;
			const pop = springAt(frame, at + 2 + i * 3, fps, 10, 120) * (1 - away);
			const tw = 1 + (s.gold ? 0.12 : 0.08) * Math.sin((frame * 2 * Math.PI) / (64 + (i % 5) * 9) + i * 1.3);
			return <StarShape key={i} x={s.x} y={s.y} r={s.r} gold={!!s.gold} scale={pop * tw} />;
		})}
	</svg>
);

/**
 * A new sky: a full-frame paper sheet that drops in from the top and settles.
 * Its lower edge is a soft wave with a flat shadow, so it reads as paper
 * while it moves; once settled the edge is below the frame. Children ride
 * along with the sheet (a sun, stars).
 */
export const SkySheet: React.FC<{color: string; frame: number; fps: number; at: number; children?: React.ReactNode}> = ({
	color,
	frame,
	fps,
	at,
	children,
}) => {
	if (frame < at) return null;
	const p = springAt(frame, at, fps, 15, 60);
	const y = -(H + 260) * (1 - p);
	const edge: P[] = [];
	for (let i = 0; i <= 8; i++) edge.push([W + 40 - (i * (W + 80)) / 8, H + 70 + 26 * Math.sin(i * 1.7)]);
	const d = `M-40 -40 L${W + 40} -40 L${W + 40} ${H + 70} ` + edge.map(([x, yy]) => `L${x.toFixed(1)} ${yy.toFixed(1)}`).join(' ') + ' Z';
	return (
		<div style={{position: 'absolute', left: 0, top: 0, width: W, height: H, transform: `translateY(${y}px)`}}>
			<svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
				<path d={d} fill={C.shadow} transform="translate(0 18)" />
				<path d={d} fill={color} />
			</svg>
			{children}
		</div>
	);
};

/** A flat gold sun (disc + two flat low-opacity rings), centred at (x, y). */
export const Sun: React.FC<{x: number; y: number; r: number; s?: number}> = ({x, y, r, s = 1}) => (
	<svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
		<g transform={`translate(${x} ${y}) scale(${s})`}>
			<circle r={r * 1.9} fill={C.gold} opacity={0.12} />
			<circle r={r * 1.45} fill={C.gold} opacity={0.18} />
			<circle cx={r * 0.12} cy={r * 0.16} r={r} fill={C.coral} />
			<circle r={r} fill={C.gold} />
		</g>
	</svg>
);

export type HillSpec = {crest: P[]; color: string; at: number; slide?: number};

/** Hill sheets that slide up from below and settle (back to front). */
export const Hills: React.FC<{hills: HillSpec[]; frame: number; fps: number}> = ({hills, frame, fps}) => (
	<>
		{hills.map((h, i) => {
			const dy = (h.slide ?? 700) * (1 - springAt(frame, h.at, fps, 12, 80));
			return (
				<svg
					key={i}
					width={W}
					height={H}
					style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', transform: `translateY(${dy}px)`}}
				>
					<path d={hillD(h.crest, H + 900)} fill={h.color} />
				</svg>
			);
		})}
	</>
);

/** The low hills most reels stand on (crests in the bottom fifth of the frame). */
export const lowHills = (at: number): HillSpec[] => [
	{
		crest: [
			[-200, 1560],
			[180, 1520],
			[520, 1556],
			[860, 1506],
			[1280, 1546],
		],
		color: C.hill2,
		at,
		slide: 500,
	},
	{
		crest: [
			[-200, 1640],
			[260, 1606],
			[640, 1650],
			[1280, 1612],
		],
		color: C.hill3,
		at: at + 5,
		slide: 500,
	},
	{
		crest: [
			[-200, 1760],
			[380, 1730],
			[800, 1772],
			[1280, 1736],
		],
		color: C.shadow,
		at: at + 10,
		slide: 500,
	},
];

// ── Noor ─────────────────────────────────────────────────────────────────────
export type NoorPose = {
	cx: number; // centre of his circle (x)
	by: number; // the ground under him (y)
	size: number; // px of the 240-box
	eyes?: Eyes;
	mouth?: Mouth;
	look?: number;
	sparkles?: number;
	heart?: number;
	tilt?: number; // degrees
	squash?: number; // 0…1 landing squash
	pulse?: number; // extra stretch (happy)
	opacity?: number;
};

/** Noor, anchored by the bottom of his circle; he breathes on his own. */
export const Noor: React.FC<NoorPose & {frame: number}> = ({
	cx,
	by,
	size,
	eyes = 'open',
	mouth = 'smile',
	look = 0,
	sparkles = 0,
	heart = 0,
	tilt = 0,
	squash = 0,
	pulse = 0,
	opacity = 1,
	frame,
}) => {
	const s = size / 240;
	const breathe = 0.02 * Math.sin((frame * 2 * Math.PI) / 75);
	const sx = 1 + breathe * 0.5 + squash * 0.6;
	const sy = 1 + breathe + pulse - squash;
	return (
		<div
			style={{
				position: 'absolute',
				left: cx - 120 * s,
				top: by - 194 * s,
				width: size,
				height: size,
				opacity,
				transform: `rotate(${tilt}deg) scale(${sx}, ${sy})`,
				transformOrigin: `${120 * s}px ${194 * s}px`,
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
				size={size}
			/>
		</div>
	);
};

/** Top of Noor's head (the upper horn) for a pose — where a speech bubble's tail points. */
export const noorHead = (p: {cx: number; by: number; size: number}) => {
	const s = p.size / 240;
	return {x: p.cx - 10 * s, y: p.by - 130 * s};
};

/** Blink twice a few seconds apart, unless told otherwise. */
export const blinkEyes = (frame: number, base: Eyes, blinks: number[]): Eyes =>
	blinks.some((b) => frame >= b && frame < b + 4) ? 'closed' : base;

// ── end card ─────────────────────────────────────────────────────────────────
export const endTimes = (from: number) => ({
	sheet: from,
	hills: from + 6,
	logo: from + 10,
	title: from + 16,
	land: from + 26,
	tagline: from + 24,
	free: from + 30,
	play: from + 34,
	qr: from + 38,
	scan: from + 46,
	blink: from + 90,
});

const LOGO = {cx: 586, cy: 410, size: 236, mat: 10};
const NOOR_END = {size: 330};

/**
 * The closing card, the same in every reel: an emerald sheet drops over the
 * scene, then the real round app logo with Noor beside it, the name, the
 * reel's own tagline, «free — no ads», the Play pill and this reel's QR code.
 * Everything is kept inside the safe box. Noor hops in from `noorFrom`.
 */
export const EndCard: React.FC<{
	frame: number;
	fps: number;
	from: number;
	slug: Slug;
	tagline: string;
	noorFrom: {cx: number; by: number; size: number};
}> = ({frame, fps, from, slug, tagline, noorFrom}) => {
	if (frame < from) return null;
	const T = endTimes(from);
	const logoR = LOGO.size / 2 + LOGO.mat;
	const logoS = springAt(frame, T.logo, fps, 11, 120);
	const eS = NOOR_END.size;
	const es = eS / 240;
	const endBy = LOGO.cy + logoR;
	// beside the circle, a small gap from it at his own widest point
	const endCx = LOGO.cx - logoR - 16 - (182 - 120) * es;
	const p = eased(frame, from, T.land, Easing.inOut(Easing.cubic));
	const cx = noorFrom.cx + (endCx - noorFrom.cx) * p;
	const by = noorFrom.by + (endBy - noorFrom.by) * p - Math.sin(Math.PI * p) * 220;
	const size = noorFrom.size + (eS - noorFrom.size) * p;
	const landS = springAt(frame, T.land, fps, 7, 220);
	const squash = frame >= T.land ? (1 - landS) * 0.12 : 0;
	const landed = frame >= T.land;
	const eyes: Eyes = !landed ? 'happy' : blinkEyes(frame, 'open', [T.blink]);
	const qr = QR[slug];
	// Whole pixels per module keep the code crisp; about 340 px whatever the
	// code's version (a short /go?ref= link needs far fewer modules).
	const qrPx = Math.max(6, Math.round(340 / qr.n)) * qr.n;
	const qrS = springAt(frame, T.qr, fps, 12, 140);
	const playS = springAt(frame, T.play, fps, 11, 160);
	const hillY = (i: number) => (700 + 80 * i) * (1 - springAt(frame, T.hills + i * 6, fps, 12, 80));
	const hills: P[][] = [
		[
			[-200, 1640],
			[200, 1600],
			[560, 1636],
			[900, 1590],
			[1280, 1630],
		],
		[
			[-200, 1736],
			[300, 1706],
			[700, 1744],
			[1280, 1702],
		],
		[
			[-200, 1830],
			[400, 1814],
			[820, 1840],
			[1280, 1812],
		],
	];
	return (
		<>
			<SkySheet color={C.emerald} frame={frame} fps={fps} at={T.sheet}>
				<Stars frame={frame} fps={fps} at={T.sheet} skip={(s) => s.x > 120 && s.x < 900 && s.y > 250 && s.y < 1560} />
			</SkySheet>
			{hills.map((crest, i) => (
				<svg
					key={i}
					width={W}
					height={H}
					style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', transform: `translateY(${hillY(i)}px)`}}
				>
					<path d={hillD(crest, H + 800)} fill={[C.hill2, C.hill3, C.shadow][i]} />
				</svg>
			))}
			{logoS > 0.001 && (
				<div
					style={{
						position: 'absolute',
						left: LOGO.cx - logoR,
						top: LOGO.cy - logoR,
						width: logoR * 2,
						height: logoR * 2,
						transform: `scale(${logoS})`,
					}}
				>
					<div style={{position: 'absolute', inset: 0, borderRadius: '50%', background: C.shadow, transform: 'translate(13px, 16px)'}} />
					<div style={{position: 'absolute', inset: 0, borderRadius: '50%', background: C.ivory}} />
					<Img
						src={staticFile('noor/app_logo_round.png')}
						style={{position: 'absolute', left: LOGO.mat, top: LOGO.mat, width: LOGO.size, height: LOGO.size}}
					/>
				</div>
			)}
			<div
				style={{
					position: 'absolute',
					left: CX - COL / 2,
					top: LOGO.cy + logoR + 6,
					width: COL,
					display: 'flex',
					flexDirection: 'column',
					alignItems: 'center',
					gap: 10,
				}}
			>
				<p style={txt({...fadeRise(frame, T.title, fps), fontWeight: 900, fontSize: 124, lineHeight: 1.4, textShadow: paperText(2.4)})}>
					{END.title}
				</p>
				<p style={txt({...fadeRise(frame, T.tagline, fps), fontWeight: 900, fontSize: 58, lineHeight: 1.4, textShadow: paperText(1.2)})}>
					{tagline}
				</p>
				<p style={txt({...fadeRise(frame, T.free, fps), fontWeight: 700, fontSize: 38, lineHeight: 1.4, color: C.ivory2})}>{END.free}</p>
				<div
					style={{
						...txt({fontWeight: 700, fontSize: 42, lineHeight: 1.3, color: C.ink}),
						marginTop: 10,
						transform: `scale(${playS})`,
						background: C.ivory,
						padding: '12px 44px 16px',
						borderRadius: 999,
						boxShadow: `8px 10px 0 ${C.shadow}`,
					}}
				>
					{END.play}
				</div>
				<div style={{position: 'relative', width: qrPx, height: qrPx, marginTop: 14, transform: `scale(${qrS})`}}>
					<div style={{position: 'absolute', inset: 0, borderRadius: 10, background: C.shadow, transform: 'translate(8px, 10px)'}} />
					<svg
						width={qrPx}
						height={qrPx}
						viewBox={`0 0 ${qr.n} ${qr.n}`}
						shapeRendering="crispEdges"
						style={{position: 'absolute', inset: 0}}
					>
						<rect width={qr.n} height={qr.n} rx={1.6} fill={C.ivory} />
						<path d={qr.d} fill={C.ink} />
					</svg>
				</div>
				<p style={txt({...fadeRise(frame, T.scan, fps), fontWeight: 700, fontSize: 36, lineHeight: 1.4, color: C.ivory2})}>{END.scan}</p>
			</div>
			<Noor frame={frame} cx={cx} by={by} size={size} eyes={eyes} mouth="open" sparkles={landed ? 0 : 1} squash={squash} />
		</>
	);
};

/** The small real logo in the top corner — gone once the end card (with the big logo) arrives. */
export const Watermark: React.FC<{frame: number; fps: number; hideAt: number}> = ({frame, fps, hideAt}) => {
	const s = springAt(frame, 8, fps, 12, 120) * (1 - eased(frame, hideAt, hideAt + 8, Easing.in(Easing.cubic)));
	if (s <= 0.001) return null;
	const {x, y, size} = portrait.watermark;
	return (
		<div style={{position: 'absolute', left: x, top: y, width: size, height: size, opacity: 0.85, transform: `scale(${s})`}}>
			<div style={{position: 'absolute', inset: 0, borderRadius: '50%', background: C.shadow, transform: 'translate(3px, 4px)'}} />
			<Img src={staticFile('noor/app_logo_round.png')} style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}} />
		</div>
	);
};

/** Dev aid: the platform-UI zones tinted, to check a frame by eye. */
export const SafeZones: React.FC = () => (
	<svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0}}>
		<rect x={0} y={0} width={W} height={SAFE.top} fill="#ff0000" opacity={0.18} />
		<rect x={0} y={SAFE.bottom} width={W} height={H - SAFE.bottom} fill="#ff0000" opacity={0.18} />
		<rect x={SAFE.right} y={SAFE.top} width={W - SAFE.right} height={SAFE.bottom - SAFE.top} fill="#ff0000" opacity={0.18} />
	</svg>
);

/** An eight-point star as a flat polygon (for lattices and badges). */
export const Star8: React.FC<{x: number; y: number; r: number; fill: string}> = ({x, y, r, fill}) => (
	<polygon points={star8(x, y, r)} fill={fill} />
);
