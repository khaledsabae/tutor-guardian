// Dev aid: one still showing the teaser at several frames (contact sheet),
// so a layout pass costs one render instead of one per frame.
import React from 'react';
import {AbsoluteFill, Freeze} from 'remotion';
import {NoorTeaser, TeaserProps} from './NoorTeaser';

export type DevSheetProps = TeaserProps & {frames: number[]; cols: number; scale: number};

export const NoorDevSheet: React.FC<DevSheetProps> = ({lang, shape, frames, cols, scale}) => {
	const W = shape === 'wide' ? 1920 : 1080;
	const H = shape === 'wide' ? 1080 : 1920;
	return (
		<AbsoluteFill style={{background: '#fff'}}>
			{frames.map((f, i) => (
				<div
					key={f}
					style={{
						position: 'absolute',
						left: (i % cols) * (W * scale + 8),
						top: Math.floor(i / cols) * (H * scale + 30),
						width: W * scale,
						height: H * scale + 30,
					}}
				>
					<div style={{width: W, height: H, transform: `scale(${scale})`, transformOrigin: '0 0', position: 'relative', overflow: 'hidden'}}>
						<Freeze frame={f}>
							<NoorTeaser lang={lang} shape={shape} />
						</Freeze>
					</div>
					<div style={{position: 'absolute', top: H * scale + 2, left: 4, font: '20px monospace'}}>f{f}</div>
				</div>
			))}
		</AbsoluteFill>
	);
};
