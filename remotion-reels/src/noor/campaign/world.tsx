// The app's new world, for the reels: the very pieces the app draws.
//
//  * story scenes (#126): a 360×240 backdrop and 240-box props from
//    mobile/assets/svg/stories (copied to public/noor/app/ by
//    scripts/sync_app_art.sh), placed by the same numbers as
//    story_scene_catalog.dart and moved by the same idle loop as
//    story_scene.dart (sway / bob / breathe / twinkle / drift, 6 s a loop);
//  * Noor's faces (assets/svg/noor) in the app's round window (NoorPresence);
//  * «درب {الاسم}» (#130): the paper gate (PaperGatePainter), the season
//    marks of the sky band (sky_band.dart: Rajab's stars, Sha'ban's bunting,
//    Dhu al-Hijjah's birds and tents);
//  * «ركن الطفل» (#129): the corner's hills (CornerHillsPainter), its colours
//    (CornerPaper, light) and the candle that only grows shorter
//    (PaperCandlePainter).
// Drawn here as SVG at reel size, with the numbers of the Dart painters.
import React from 'react';
import {Img, staticFile} from 'remotion';
import {C} from '../palette';
import {star8} from '../geometry';

/** A piece of the app's own art (after scripts/sync_app_art.sh). */
export const appArt = (path: string) => staticFile(`noor/app/${path}.svg`);

// ── story scenes ─────────────────────────────────────────────────────────────
export type SceneMotion = 'still' | 'sway' | 'bob' | 'breathe' | 'twinkle' | 'drift';
export type SceneLayer = {piece: string; x: number; y?: number; size?: number; depth?: number; motion?: SceneMotion; flip?: boolean; phase?: number};
export type StoryScene = {backdrop: string; layers: SceneLayer[]};

const KID = 0.8;
const ADULT = 0.8;

/** «يوسف وغرسة الأمل» (hope_sprout), page by page — story_scene_catalog.dart. */
export const HOPE_SPROUT: StoryScene[] = [
	{
		backdrop: 'bg_garden_day',
		layers: [
			{piece: 'tree', x: 0.12, size: 0.95, depth: 0.2, motion: 'sway'},
			{piece: 'father_out', x: 0.4, size: ADULT},
			{piece: 'boy_hold', x: 0.64, size: KID},
		],
	},
	{
		backdrop: 'bg_garden_day',
		layers: [
			{piece: 'boy', x: 0.35, size: KID},
			{piece: 'seed', x: 0.6, y: 1, size: 0.45, depth: 0.8},
			{piece: 'watering_can', x: 0.84, size: 0.38, depth: 0.7},
		],
	},
	{
		backdrop: 'bg_garden_evening',
		layers: [
			{piece: 'boy', x: 0.36, size: KID},
			{piece: 'father', x: 0.64, size: ADULT, flip: true},
			{piece: 'seed', x: 0.86, y: 1, size: 0.35, depth: 0.8},
		],
	},
	{
		backdrop: 'bg_garden_day',
		layers: [
			{piece: 'boy_up', x: 0.3, size: KID, motion: 'bob'},
			{piece: 'plant', x: 0.6, y: 1, size: 0.65, depth: 0.7, motion: 'sway'},
			{piece: 'bird', x: 0.84, y: 0.5, size: 0.26, depth: 0.9, motion: 'bob'},
		],
	},
];

/** One idle-loop transform of a piece (story_scene.dart `_moved`); t runs 0…1. */
const idle = (motion: SceneMotion, t: number, side: number): {transform: string; opacity: number; origin: string} => {
	const wave = Math.sin(t * 2 * Math.PI);
	switch (motion) {
		case 'sway':
			return {transform: `rotate(${wave * 0.035}rad)`, opacity: 1, origin: '50% 100%'};
		case 'bob':
			return {transform: `translateY(${-side * 0.018 * (wave + 1)}px)`, opacity: 1, origin: '50% 50%'};
		case 'breathe':
			return {transform: `scale(${1 + 0.025 * wave})`, opacity: 1, origin: '50% 100%'};
		case 'twinkle':
			return {transform: 'none', opacity: 0.7 + (0.3 * (wave + 1)) / 2, origin: '50% 50%'};
		case 'drift':
			return {transform: `translateX(${side * 0.05 * wave}px)`, opacity: 1, origin: '50% 50%'};
		default:
			return {transform: 'none', opacity: 1, origin: '50% 50%'};
	}
};

/**
 * A story page as layered paper, `width` px wide (3:2). `parallax` −1…1 slides
 * near pieces further than far ones (a page being turned); `pop(i)` 0…1 lets
 * the caller bring each piece in on its own spring (the backdrop is -1).
 */
export const SceneView: React.FC<{
	scene: StoryScene;
	width: number;
	frame: number;
	parallax?: number;
	pop?: (i: number) => number;
	radius?: number;
}> = ({scene, width, frame, parallax = 0, pop = () => 1, radius = 0}) => {
	const h = (width * 2) / 3;
	const t = frame / 180; // the app's idle loop is 6 s
	const bg = pop(-1);
	return (
		<div style={{position: 'relative', width, height: h, overflow: 'hidden', borderRadius: radius}}>
			<Img src={appArt(`stories/${scene.backdrop}`)} style={{position: 'absolute', inset: 0, width, height: h, opacity: bg > 0.001 ? 1 : 0}} />
			{scene.layers.map((l, i) => {
				const p = pop(i);
				if (p <= 0.001) return null;
				const side = h * (l.size ?? KID);
				const left = l.x * width - side / 2 + parallax * (l.depth ?? 0.5) * width * 0.12;
				const top = (l.y ?? 0.97) * h - side;
				const m = idle(l.motion ?? 'still', (t + (l.phase ?? 0)) % 1, side);
				return (
					<div
						key={i}
						style={{
							position: 'absolute',
							left,
							top,
							width: side,
							height: side,
							opacity: m.opacity,
							transform: `${m.transform} translateY(${(1 - p) * side * 0.25}px) scale(${0.6 + 0.4 * p})`,
							transformOrigin: m.origin,
						}}
					>
						<Img
							src={appArt(`stories/${l.piece}`)}
							style={{width: side, height: side, transform: l.flip ? 'scaleX(-1)' : undefined, opacity: Math.min(1, p * 1.5)}}
						/>
					</div>
				);
			})}
		</div>
	);
};

// ── Noor's window (NoorPresence) ─────────────────────────────────────────────
export type NoorFace = 'calm' | 'awake' | 'happy' | 'thinking' | 'tender' | 'reading' | 'sleepy';
const ACCENT = '#D97706'; // the app's accent (app_palette.dart), the window's rim
const WINDOW = '#0F6B5C'; // kNoorWindowGround

/** Noor's face in the app's round emerald window with its accent rim. */
export const NoorWindow: React.FC<{size: number; face: NoorFace; ring?: number}> = ({size, face, ring = 0}) => (
	<div style={{position: 'relative', width: size, height: size}}>
		{ring > 0.001 && (
			<div
				style={{
					position: 'absolute',
					inset: -size * 0.12 * ring,
					borderRadius: '50%',
					border: `${Math.max(2, size * 0.02)}px solid ${ACCENT}`,
					opacity: 0.45 * ring,
				}}
			/>
		)}
		<div
			style={{
				position: 'absolute',
				inset: 0,
				borderRadius: '50%',
				background: WINDOW,
				border: `${Math.max(3, size * 0.035)}px solid ${ACCENT}`,
				boxSizing: 'border-box',
				overflow: 'hidden',
			}}
		>
			<Img src={appArt(`noor/noor_${face}`)} style={{position: 'absolute', left: '-6%', top: '-8%', width: '112%', height: '112%'}} />
		</div>
	</div>
);

// ── «درب {الاسم}» ────────────────────────────────────────────────────────────
const archD = (l: number, t: number, r: number, b: number) => {
	const rad = (r - l) / 2;
	return `M${l} ${b} V${t + rad} A${rad} ${rad} 0 0 1 ${r} ${t + rad} V${b} Z`;
};

/** The paper gate: an emerald arch on its solid shadow, ivory light through it (PaperGatePainter). */
export const PaperGate: React.FC<{h: number; near?: boolean}> = ({h, near = false}) => {
	const w = h * 0.8;
	const u = h / 30; // the app's gate is 30 high
	const top = near ? h * 0.14 : 0;
	const cx = (w - 1.5 * u) / 2;
	const r = h * 0.08;
	return (
		<svg width={w + 2 * u} height={h + 2 * u} viewBox={`0 0 ${w + 2 * u} ${h + 2 * u}`} style={{display: 'block', overflow: 'visible'}}>
			<path d={archD(0, top, w - 1.5 * u, h - 2 * u)} fill={C.shadow} transform={`translate(${1.5 * u} ${2 * u})`} />
			<path d={archD(0, top, w - 1.5 * u, h - 2 * u)} fill={C.emerald} />
			<path d={archD(w * 0.24, top + h * 0.2, w - 1.5 * u - w * 0.24, h - 2 * u)} fill={C.ivory} />
			{near && (
				<path
					d={`M${cx} 0 L${cx + r * 0.35} ${r * 0.65} L${cx + r} ${r} L${cx + r * 0.35} ${r * 1.35} L${cx} ${r * 2} L${cx - r * 0.35} ${r * 1.35} L${cx - r} ${r} L${cx - r * 0.35} ${r * 0.65} Z`}
					fill={C.gold}
				/>
			)}
		</svg>
	);
};

export type Season = 'rajab' | 'shaban' | 'hijjah';

/**
 * The season's paper touch along the top of a sky band `w`×`h` (sky_band.dart,
 * scaled by `k` from the app's dp): Rajab hangs three eight-point stars on
 * threads, Sha'ban strings bunting overhead, Dhu al-Hijjah sends three paper
 * birds across and pitches white tents on the far hill. `show` 0…1 drops the
 * marks in from above (and lifts them away). Never a word.
 */
export const SeasonMarks: React.FC<{season: Season; w: number; h: number; k: number; show: number; frame: number; farY: number}> = ({
	season,
	w,
	h,
	k,
	show,
	frame,
	farY,
}) => {
	if (show <= 0.001) return null;
	const drop = (1 - show) * -60 * k;
	if (season === 'rajab') {
		return (
			<g transform={`translate(0 ${drop})`}>
				{[0.3, 0.5, 0.7].map((fx, i) => {
					const x = fx * w;
					const cy = (i === 1 ? 11 : 9) * k + 0.6 * k * Math.sin(frame * 0.06 + i);
					return (
						<g key={i}>
							<line x1={x} y1={0} x2={x} y2={cy - 5 * k} stroke={C.ivory2} strokeWidth={1 * k} />
							<polygon points={star8(x + 1 * k, cy + 1.4 * k, 5.2 * k)} fill="#062B26" />
							<polygon points={star8(x, cy, 5.2 * k)} fill={C.ivory} />
						</g>
					);
				})}
			</g>
		);
	}
	if (season === 'shaban') {
		const swags = 3;
		const sag = 5 * k;
		const span = w / swags;
		const ropeY = (x: number) => {
			const t = (x % span) / span;
			return 1 * k + sag * 4 * t * (1 - t);
		};
		const rope = Array.from({length: 61}, (_, i) => {
			const x = (w * i) / 60;
			return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${(i % 20 === 0 ? 1 * k : ropeY(x)).toFixed(1)}`;
		}).join(' ');
		return (
			<g transform={`translate(0 ${drop})`}>
				<path d={rope} fill="none" stroke={C.ivory2} strokeWidth={1.1 * k} />
				{Array.from({length: 9}, (_, i) => {
					const x = (w * (i + 0.5)) / 9;
					const y = ropeY(x);
					const f = `M${x - 5 * k} ${y} L${x + 5 * k} ${y} L${x} ${y + 9 * k} Z`;
					return (
						<g key={i} transform={`rotate(${2 * Math.sin(frame * 0.07 + i)} ${x} ${y})`}>
							<path d={f} fill="#062B26" transform={`translate(${1 * k} ${1.4 * k})`} />
							<path d={f} fill={i % 2 ? C.coral : C.ivory} />
						</g>
					);
				})}
			</g>
		);
	}
	// Dhu al-Hijjah: birds across the middle of the band, tents on the far hill
	const birds: [number, number, number][] = [
		[0.42, 8, 6],
		[0.5, 12, 5],
		[0.58, 7, 5.5],
	];
	const glide = (frame * 0.6 * k) % (w * 0.2);
	return (
		<g>
			{birds.map(([fx, y, s], i) => {
				const x = fx * w + glide - w * 0.1;
				const yy = y * k * 2 + drop + Math.sin(frame * 0.12 + i) * 2 * k;
				const flap = Math.sin(frame * 0.35 + i * 2) * 0.35 * s * k;
				const d = `M${x - s * k} ${yy - flap} Q${x - s * k * 0.4} ${yy - s * k * 0.2} ${x} ${yy} Q${x + s * k * 0.4} ${yy - s * k * 0.2} ${x + s * k} ${yy - flap}`;
				return <path key={i} d={d} fill="none" stroke={C.ivory} strokeWidth={1.6 * k} strokeLinecap="round" strokeLinejoin="round" />;
			})}
			{[0.16, 0.24, 0.32, 0.4].map((fx, i) => {
				const x = fx * w;
				const base = farY + 2 * k;
				const tw = 7 * k;
				const th = 6 * k * show;
				return (
					<g key={i}>
						<path d={`M${x - tw + 1 * k} ${base + 1.2 * k} L${x + 1 * k} ${base - th + 1.2 * k} L${x + tw + 1 * k} ${base + 1.2 * k} Z`} fill="#062B26" />
						<path d={`M${x - tw} ${base} L${x} ${base - th} L${x + tw} ${base} Z`} fill={C.ivory} />
					</g>
				);
			})}
		</g>
	);
};

// ── «ركن الطفل» ──────────────────────────────────────────────────────────────
/** CornerPaper (light), app_palette.dart. */
export const CORNER = {
	sky: '#F4A492',
	hillFar: '#12806D',
	hillNear: '#0D6A5A',
	ground: '#094A40',
	card: '#FBF1DE',
	cardShadow: '#D9C7A7',
	ink: '#0F3D36',
};

/** The corner's band where the sky meets the valley (CornerHillsPainter, RTL: mirrored). */
export const CornerHills: React.FC<{w: number; h: number; sun?: number}> = ({w, h, sun = 1}) => {
	// mirrored once for Arabic: x -> w - x
	const X = (fx: number) => w - fx * w;
	const far = `M${X(0)} ${h * 0.78} C${X(0.3)} ${h * 0.62} ${X(0.55)} ${h * 0.5} ${X(0.78)} ${h * 0.44} C${X(0.9)} ${h * 0.4} ${X(1)} ${h * 0.46} ${X(1)} ${h * 0.5} L${X(1)} ${h} L${X(0)} ${h} Z`;
	const near = `M${X(0)} ${h * 0.58} C${X(0.18)} ${h * 0.5} ${X(0.36)} ${h * 0.62} ${X(0.55)} ${h * 0.78} C${X(0.72)} ${h * 0.9} ${X(0.88)} ${h * 0.88} ${X(1)} ${h * 0.84} L${X(1)} ${h} L${X(0)} ${h} Z`;
	return (
		<svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{display: 'block'}}>
			<rect width={w} height={h} fill={CORNER.sky} />
			<circle cx={X(0.82)} cy={h * 0.5 + (1 - sun) * h * 0.4} r={h * 0.3} fill={C.gold} />
			<path d={far} fill={CORNER.hillFar} />
			<path d={near} fill={CORNER.ground} transform={`translate(${-h * 0.06} ${h * 0.08})`} />
			<path d={near} fill={CORNER.hillNear} />
			<rect x={0} y={h - h * 0.09} width={w} height={h * 0.09} fill={CORNER.ground} />
		</svg>
	);
};

/**
 * «شمعة وقتك» — an ivory stick on an emerald dish that only grows shorter, a
 * gold flame while time remains (PaperCandlePainter). `fraction` 1 … 0.
 */
export const PaperCandle: React.FC<{h: number; fraction: number; sway: number}> = ({h, fraction, sway}) => {
	const w = h * 0.75;
	const unit = h / 48;
	const sh = {x: 1.5 * unit, y: 2 * unit};
	const stickH = h * (0.08 + 0.5 * Math.max(0, Math.min(1, fraction)));
	const stickW = w * 0.46;
	const stickL = (w - stickW) / 2;
	const stickT = h * 0.84 - stickH;
	const rr = stickW * 0.3;
	const stick = `M${stickL} ${stickT + stickH} V${stickT + rr} Q${stickL} ${stickT} ${stickL + rr} ${stickT} H${stickL + stickW - rr} Q${stickL + stickW} ${stickT} ${stickL + stickW} ${stickT + rr} V${stickT + stickH} Z`;
	const wickTop = stickT - h * 0.06;
	const fh = h * 0.22;
	const fw = w * 0.42;
	const leaf = `M0 ${-fh} C${fw * 0.55} ${-fh * 0.55} ${fw * 0.55} 0 0 0 C${-fw * 0.55} 0 ${-fw * 0.55} ${-fh * 0.55} 0 ${-fh} Z`;
	return (
		<svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{display: 'block', overflow: 'visible'}}>
			<rect x={w * 0.05 + sh.x} y={h * 0.84 + sh.y} width={w * 0.9} height={h * 0.1} rx={h * 0.05} fill={C.shadow} />
			<rect x={w * 0.05} y={h * 0.84} width={w * 0.9} height={h * 0.1} rx={h * 0.05} fill={C.emerald} />
			<path d={stick} fill={C.ivory3} transform={`translate(${sh.x} ${sh.y})`} />
			<path d={stick} fill={C.ivory} />
			{stickH > h * 0.2 && (
				<path
					d={`M${stickL + stickW * 0.62} ${stickT + stickW * 0.2} L${stickL + stickW} ${stickT + stickW * 0.2} L${stickL + stickW} ${stickT + stickH * 0.45} A${stickW * 0.2} ${stickW * 0.2} 0 0 1 ${stickL + stickW * 0.62} ${stickT + stickH * 0.38} Z`}
					fill={C.ivory3}
				/>
			)}
			<line x1={w / 2} y1={stickT + unit} x2={w / 2} y2={wickTop} stroke={C.ink} strokeWidth={Math.max(1.2, unit * 1.4)} strokeLinecap="round" />
			{fraction > 0 && <path d={leaf} fill={C.gold} transform={`translate(${w / 2} ${wickTop + unit}) rotate(${sway * 0.08 * (180 / Math.PI)})`} />}
		</svg>
	);
};

/** An ivory corner card on its solid shadow (CornerPaperCard), positioned by the caller. */
export const CornerCard: React.FC<{style?: React.CSSProperties; children?: React.ReactNode; k?: number}> = ({style, children, k = 1}) => (
	<div style={{background: CORNER.card, borderRadius: 22 * k, boxShadow: `${4 * k}px ${5 * k}px 0 ${CORNER.cardShadow}`, ...style}}>{children}</div>
);

/** The corner's gold button (CornerGoldButton). */
export const GoldButton: React.FC<{label: string; k?: number; sel?: number; style?: React.CSSProperties; fontFamily: string}> = ({
	label,
	k = 1,
	sel = 0,
	style,
	fontFamily,
}) => (
	<div
		style={{
			background: C.gold,
			color: CORNER.ink,
			borderRadius: 18 * k,
			padding: `${10 * k}px ${20 * k}px ${12 * k}px`,
			fontFamily,
			fontWeight: 900,
			fontSize: 17 * k,
			lineHeight: 1.4,
			textAlign: 'center',
			direction: 'rtl',
			boxShadow: `${3 * k}px ${4 * k}px 0 ${sel > 0.5 ? C.shadow : 'rgba(0,0,0,0)'}`,
			transform: `scale(${1 + 0.08 * Math.sin(Math.PI * Math.min(1, sel))})`,
			...style,
		}}
	>
		{label}
	</div>
);
