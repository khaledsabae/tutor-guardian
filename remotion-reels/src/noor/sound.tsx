// Soft generated sounds only — no music, no instruments, no bells.
// Files come from scripts/gen_teaser_sfx.py (seeded, reproducible).
import React, {useContext} from 'react';
import {Audio, interpolate, Sequence, staticFile} from 'remotion';
import {T} from './timeline';
import {SoundMute} from './mix';

export type Cue = {file: 'rustle' | 'rustle_long' | 'air' | 'drop'; at: number; vol: number};

const LEN: Record<Cue['file'], number> = {rustle: 14, rustle_long: 44, air: 18, drop: 9};

// One trim for all cues: lands the mix near -23 LUFS, peaks about -5.5 dBFS.
export const MIX_GAIN = 1.05;

export const CUES: Cue[] = [
	// hill sheets slide up
	{file: 'rustle', at: T.hills[0], vol: 0.5},
	{file: 'rustle', at: T.hills[1], vol: 0.55},
	{file: 'rustle', at: T.hills[2], vol: 0.6},
	{file: 'rustle', at: T.hills[3], vol: 0.7},
	// Noor turns happy
	{file: 'drop', at: T.happy, vol: 0.6},
	// the paper path unrolls
	{file: 'rustle_long', at: T.path[0], vol: 0.8},
	// each lantern is lit
	...T.lights.map((at, i) => ({file: 'air' as const, at, vol: 0.62 - i * 0.04})),
	// speech bubbles (paper cards) pop in
	{file: 'rustle', at: T.ask[0], vol: 0.4},
	{file: 'rustle', at: T.answer[0], vol: 0.4},
	{file: 'drop', at: T.happy2, vol: 0.55},
	// sheets leave, end-card hills come up
	{file: 'rustle', at: T.exit, vol: 0.55},
	{file: 'rustle', at: T.endHills, vol: 0.5},
];

export const TeaserSound: React.FC = () => {
	if (useContext(SoundMute)) return null;
	return (
	<>
		<Audio
			src={staticFile('noor/sfx/night.wav')}
			loop
			volume={(f) =>
				interpolate(f, [0, 45, T.total - 50, T.total - 2], [0, 1, 1, 0], {
					extrapolateLeft: 'clamp',
					extrapolateRight: 'clamp',
				})
			}
		/>
		{CUES.map((c, i) => (
			<Sequence key={i} from={c.at} durationInFrames={LEN[c.file] + 2} layout="none">
				<Audio src={staticFile(`noor/sfx/${c.file}.wav`)} volume={Math.min(1, c.vol * MIX_GAIN)} />
			</Sequence>
		))}
	</>
);
};
