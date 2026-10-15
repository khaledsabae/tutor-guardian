// «ورق مقصوص» art, transcribed from the staged SVGs copied into public/noor/
// (noor_*.svg, lantern.svg, sprig.svg, star.svg, domain_islamic_parenting.svg)
// so that parts can move on their own: Noor's pupils, a lantern's flame, the
// parent and child stepping out of phase. Shapes and colours are unchanged,
// with one addition: the walkers get the icon set's emerald cut edge (the
// same stroke-behind-fill layer lantern.svg uses) so the ivory child still
// reads when he stands on the ivory path.
import React from 'react';
import {C} from './palette';
import {star8} from './geometry';

const CRESCENT = 'M119.7 69.6 A62.4 62.4 0 1 0 177.5 156.2 A52.8 52.8 0 0 1 119.7 69.6 Z';

// Gold sparkle polygons from noor_happy.svg.
const SPARK_A =
	'178.0,63.0 180.0,69.1 185.8,66.2 182.9,72.0 189.0,74.0 182.9,76.0 185.8,81.8 180.0,78.9 178.0,85.0 176.0,78.9 170.2,81.8 173.1,76.0 167.0,74.0 173.1,72.0 170.2,66.2 176.0,69.1';
const SPARK_B =
	'200.0,105.0 201.3,108.9 204.9,107.1 203.1,110.7 207.0,112.0 203.1,113.3 204.9,116.9 201.3,115.1 200.0,119.0 198.7,115.1 195.1,116.9 196.9,113.3 193.0,112.0 196.9,110.7 195.1,107.1 198.7,108.9';

export type Eyes = 'open' | 'closed' | 'happy';
export type Mouth = 'smile' | 'calm' | 'open';

const line = {
	fill: 'none',
	stroke: C.ink,
	strokeLinecap: 'round' as const,
	strokeLinejoin: 'round' as const,
};

/**
 * Noor in his 240×240 box. The named expressions in the brief map to:
 *   awake  = eyes 'open'   + mouth 'smile'
 *   calm   = eyes 'closed' + mouth 'calm'      (also the blink frame's eyes)
 *   happy  = eyes 'happy'  + mouth 'open' + sparkles
 *   tender = eyes 'closed' + mouth 'calm' + heart
 */
export const NoorArt: React.FC<{
	eyes: Eyes;
	mouth: Mouth;
	look?: number; // -1 … 1, pupils left/right
	sparkles?: number; // 0 … 1 (pop scale)
	sparkleTwinkle?: number; // phase in radians
	heart?: number; // 0 … 1 (pop scale)
	heartFloat?: boolean; // draw the heart up by the tip (his lower half is behind a hill)
	size: number;
}> = ({eyes, mouth, look = 0, sparkles = 0, sparkleTwinkle = 0, heart = 0, heartFloat = false, size}) => {
	const px = look * 3.2;
	const py = Math.abs(look) * 0.4;
	const spark = (pts: string, cx: number, cy: number, s: number) =>
		s > 0.001 ? (
			<g transform={`translate(${cx} ${cy}) scale(${s}) translate(${-cx} ${-cy})`}>
				<polygon points={pts} fill={C.shadow} transform="translate(1.5,2)" />
				<polygon points={pts} fill={C.gold} />
			</g>
		) : null;
	const tw = (k: number) => sparkles * (1 + 0.08 * Math.sin(sparkleTwinkle + k));
	return (
		<svg viewBox="0 0 240 240" width={size} height={size} style={{overflow: 'visible', display: 'block'}}>
			<path d={CRESCENT} fill={C.shadow} transform="translate(5,6)" />
			<path d={CRESCENT} fill={C.ivory} />
			<path
				d="M177.5 156.2 A52.8 52.8 0 0 1 119.7 69.6"
				fill="none"
				stroke={C.ivory2}
				strokeWidth={5}
				strokeLinecap="round"
				transform="translate(-2.5,1.5)"
			/>
			<g transform="translate(85,142) scale(1.18) translate(-85,-142)">
				{eyes === 'open' ? (
					<>
						<circle cx={74 + px} cy={133 + py} r={5.2} fill={C.ink} />
						<circle cx={75.8 + px} cy={131 + py} r={1.7} fill={C.ivory} />
						<circle cx={96 + px} cy={133 + py} r={5.2} fill={C.ink} />
						<circle cx={97.8 + px} cy={131 + py} r={1.7} fill={C.ivory} />
					</>
				) : eyes === 'closed' ? (
					<>
						<path d="M67 134 Q74 130.5 81 134" {...line} strokeWidth={3.4} />
						<path d="M89 134 Q96 130.5 103 134" {...line} strokeWidth={3.4} />
					</>
				) : (
					<>
						<path d="M67 135 Q74 127 81 135" {...line} strokeWidth={3.4} />
						<path d="M89 135 Q96 127 103 135" {...line} strokeWidth={3.4} />
					</>
				)}
				<circle cx={67} cy={148} r={5.4} fill={C.coral} />
				<circle cx={104} cy={148} r={5.4} fill={C.coral} />
				{mouth === 'smile' ? (
					<path d="M77 151 Q85 159 93 151" {...line} strokeWidth={3.2} />
				) : mouth === 'calm' ? (
					<path d="M79 152 Q85 156.5 91 152" {...line} strokeWidth={3.0} />
				) : (
					<path d="M76 150 Q85 162 94 150 Z" fill={C.ink} />
				)}
			</g>
			{spark(SPARK_A, 178, 74, tw(0))}
			{spark(SPARK_B, 200, 112, tw(2.1))}
			{heart > 0.001 ? (
				<g transform={`translate(160 ${heartFloat ? 88 : 188}) scale(${heart}) translate(-162 -188)`}>
					<path
						d="M150 170 C150 162 160 160 162 167 C164 160 174 162 174 170 C174 178 162 184 162 188 C162 184 150 178 150 170 Z"
						fill={C.coral}
					/>
				</g>
			) : null}
		</svg>
	);
};

/**
 * lantern.svg as a <g>, standing on the ground at (x, y). `size` is the px
 * width of the original 48-box. `flame` 0…1 lights it, `glow` 0…1 grows the
 * three flat low-opacity rings (no blur), `pop` 0…1 pops it up from the ground.
 */
export const LanternG: React.FC<{
	x: number;
	y: number;
	size: number;
	pop: number;
	flame: number;
	glow: number;
	flicker: number;
}> = ({x, y, size, pop, flame, glow, flicker}) => {
	if (pop <= 0.001) return null;
	const u = (size / 48) * pop;
	const fs = flame * (1 + 0.05 * flicker);
	const win = flame > 0.5 ? C.ivory : C.ivory2;
	const parts = (
		<>
			<circle cx="24" cy="7.5" r="2.6" fill="none" strokeWidth={2.2} />
			<path strokeWidth={2} d="M14.5 17.5C14.5 13.5 20 12.5 24 9.5C28 12.5 33.5 13.5 33.5 17.5Z" />
			<path strokeWidth={5} d="M16 19.5H32L35 27L31 35H17L13 27Z" />
			<path strokeWidth={2} d="M18 37H30L28 41.5H20Z" />
		</>
	);
	// ground point of the 48-box is (24, 43.5) (base + shadow)
	return (
		<g transform={`translate(${x} ${y}) scale(${u}) translate(-24 -43.5)`}>
			{glow > 0.001 ? (
				<g transform={`translate(24 28) scale(${glow}) translate(-24 -28)`}>
					<circle cx={24} cy={28} r={36} fill={C.gold} opacity={0.05} />
					<circle cx={24} cy={28} r={26} fill={C.gold} opacity={0.07} />
					<circle cx={24} cy={28} r={17} fill={C.gold} opacity={0.1} />
				</g>
			) : null}
			<g transform="translate(-.8 -.2)" strokeLinejoin="round" strokeLinecap="round">
				<g transform="translate(1.5 2)" fill={C.shadow} stroke={C.shadow}>
					{parts}
				</g>
				<g fill={C.emerald} stroke={C.emerald}>
					{parts}
				</g>
				<path fill={win} d="M16 19.5H32L35 27L31 35H17L13 27Z" />
				{fs > 0.001 ? (
					<g transform={`translate(24 33.6) scale(${fs}) translate(-24 -33.6)`}>
						<path
							fill={C.gold}
							d="M24 20.8C28 24.6 28.6 27.2 28.6 29A4.6 4.6 0 0 1 19.4 29C19.4 27.2 20 24.6 24 20.8Z"
						/>
					</g>
				) : null}
			</g>
		</g>
	);
};

/** sprig.svg as a <g> rooted at (x, y) on the ground; `size` = px of the 48-box. */
export const SprigG: React.FC<{x: number; y: number; size: number; pop: number; sway: number}> = ({
	x,
	y,
	size,
	pop,
	sway,
}) => {
	if (pop <= 0.001) return null;
	const u = (size / 48) * pop;
	const leaves =
		'M21.7 35.3Q28.3 35.5 29.8 29.1Q23.2 28.9 21.7 35.3ZM21.7 35.3Q21.7 28.7 15.2 27.5Q15.2 34.1 21.7 35.3ZM22.8 27.6Q29.4 28.2 31.3 21.9Q24.7 21.3 22.8 27.6ZM22.8 27.6Q23.2 21 16.8 19.4Q16.4 26 22.8 27.6ZM24.4 20.2Q30.9 21.3 33.2 15.1Q26.7 14 24.4 20.2ZM24.4 20.2Q25.2 13.6 18.9 11.5Q18.1 18.1 24.4 20.2ZM25.8 15.1Q31.1 12.2 28.5 6.7Q23.1 9.6 25.8 15.1Z';
	const parts = (
		<>
			<path fill="none" strokeWidth={3} d="M21.2 41.2Q22.1 26.3 26.3 13.3" />
			<path strokeWidth={4} d={leaves} />
		</>
	);
	return (
		<g transform={`translate(${x} ${y}) scale(${u}) rotate(${sway}) translate(-21.2 -41.2)`}>
			<g transform="translate(-1 -.7)" strokeLinejoin="round" strokeLinecap="round">
				<g transform="translate(1.5 2)" fill={C.shadow} stroke={C.shadow}>
					{parts}
				</g>
				<g fill={C.emerald} stroke={C.emerald}>
					{parts}
				</g>
				<path fill="#7ED3A6" d={leaves} />
			</g>
		</g>
	);
};

/**
 * Parent and child from domain_islamic_parenting.svg (figures only, no card,
 * hills or lantern). Origin of the 240-box is kept; feet are at y = 200.
 * `stepA`/`stepB` lift each figure a little (in 240-units) for the walk.
 */
export const WalkersG: React.FC<{
	x: number;
	y: number;
	size: number;
	mirror: boolean;
	pop: number;
	stepA: number;
	stepB: number;
	swayA: number;
	swayB: number;
}> = ({x, y, size, mirror, pop, stepA, stepB, swayA, swayB}) => {
	if (pop <= 0.001) return null;
	const u = size / 130;
	// Shapes from the scene. Drawn three times like the icon set: paper
	// shadow, an emerald cut edge (so ivory figures still read on the ivory
	// path), then the colours.
	const parent = [
		'M98.4 135.7 L110.4 160.7 A4 4 0 0 0 117.6 157.3 L105.6 132.3 A4 4 0 0 0 98.4 135.7 Z',
		'M70 140 L104 140 C108 160 112 180 116 200 L58 200 C61 180 65 160 70 140 Z',
		'M85.5 109 A9.5 9.5 0 1 0 104.5 109 A9.5 9.5 0 1 0 85.5 109 Z',
		'M99 99 C97 89 89 85 82 86 C72 88 67 98 67 110 C67 122 64 134 60 146 C59 152 62 156 68 156 L104 156 C110 156 112 150 109 142 C106 134 102 126 99 120 C92 117 89 108 93 102 C95 100 97 99 99 99 Z',
	];
	const parentFill = [C.ivory2, C.ivory2, C.ivory2, C.coral];
	const child = [
		'M126 156 L144 156 C146 170 149 186 151 200 L121 200 C122 186 124 170 126 156 Z',
		'M133 162.1 L118 157.6 A3.5 3.5 0 0 0 116 164.4 L131 168.9 A3.5 3.5 0 0 0 133 162.1 Z',
		'M126 146 A10 10 0 1 0 146 146 A10 10 0 1 0 126 146 Z',
		'M126 144 C126 133 146 133 146 144 Z',
		'M110 160 A5 5 0 1 0 120 160 A5 5 0 1 0 110 160 Z',
	];
	const childFill = [C.ivory, C.ivory, C.ivory2, C.ivory, C.ivory2];
	const layer = (paths: string[], fills: string[]) => (
		<>
			<g transform="translate(4 5)" fill={C.shadow} stroke={C.shadow} strokeWidth={4} strokeLinejoin="round">
				{paths.map((d, i) => (
					<path key={i} d={d} />
				))}
			</g>
			<g fill={C.emerald} stroke={C.emerald} strokeWidth={4} strokeLinejoin="round">
				{paths.map((d, i) => (
					<path key={i} d={d} />
				))}
			</g>
			{paths.map((d, i) => (
				<path key={i} d={d} fill={fills[i]} />
			))}
		</>
	);
	return (
		<g transform={`translate(${x} ${y}) scale(${mirror ? -u : u} ${u * pop}) translate(-106.5 -200)`}>
			<g transform={`translate(0 ${-stepA}) rotate(${swayA} 87 200)`}>{layer(parent, parentFill)}</g>
			<g transform={`translate(0 ${-stepB}) rotate(${swayB} 136 200)`}>{layer(child, childFill)}</g>
		</g>
	);
};

/** One eight-point star with its paper shadow (gold) or flat (dim decoration). */
export const StarShape: React.FC<{x: number; y: number; r: number; gold: boolean; scale: number}> = ({
	x,
	y,
	r,
	gold,
	scale,
}) => {
	if (scale <= 0.001) return null;
	const pts = star8(x, y, r);
	return (
		<g transform={`translate(${x} ${y}) scale(${scale}) translate(${-x} ${-y})`}>
			{gold ? <polygon points={pts} fill={C.shadow} transform={`translate(${r * 0.18} ${r * 0.24})`} /> : null}
			<polygon points={pts} fill={gold ? C.gold : C.starDim} />
		</g>
	);
};
