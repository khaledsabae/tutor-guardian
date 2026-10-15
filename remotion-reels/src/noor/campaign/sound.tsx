// The campaign reels' sound: the teaser's generated room sounds (no music,
// no instruments, no bells) on cue, over the quiet night bed.
// WAVs come from scripts/gen_teaser_sfx.py (seeded, reproducible).
import React, {useContext} from 'react';
import {SoundMute} from '../mix';
import {Audio, interpolate, Sequence, staticFile} from 'remotion';

export type Sfx = 'rustle' | 'rustle_long' | 'air' | 'drop' | 'tick' | 'swish';
export type Cue = {file: Sfx; at: number; vol: number};

// length of each file in frames @ 30 fps
const LEN: Record<Sfx, number> = {rustle: 14, rustle_long: 44, air: 18, drop: 9, tick: 4, swish: 22};

/**
 * `gain` trims the whole mix of one reel; it is set per reel so that each
 * lands near -23 LUFS integrated with peaks at or below -3 dBFS (measured
 * on the rendered MP4 with ffmpeg ebur128 — see scripts/render_noor_campaign.sh).
 */
export const ReelSound: React.FC<{
	cues: Cue[];
	total: number;
	gain: number;
	bed?: number;
	duck?: (frame: number) => number; // 0…1 multiplier at an absolute frame (the voice-over cut ducks under speech)
}> = ({cues, total, gain, bed = 1, duck = () => 1}) => {
	if (useContext(SoundMute)) return null;
	return (
		<>
			<Audio
				src={staticFile('noor/sfx/night.wav')}
				loop
				volume={(f) =>
					bed *
					interpolate(f, [0, 30, total - 45, total - 2], [0, 1, 1, 0], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
					}) *
					duck(f)
				}
			/>
			{cues.map((c, i) => (
				<Sequence key={i} from={Math.round(c.at)} durationInFrames={LEN[c.file] + 2} layout="none">
					<Audio src={staticFile(`noor/sfx/${c.file}.wav`)} volume={(f) => Math.min(1, c.vol * gain) * duck(Math.round(c.at) + f)} />
				</Sequence>
			))}
		</>
	);
};

/** The end card's sounds, the same in every reel (sheet drops, hills, Noor lands, QR). */
export const endCues = (from: number): Cue[] => [
	{file: 'rustle_long', at: from, vol: 0.55},
	{file: 'rustle', at: from + 8, vol: 0.4},
	{file: 'drop', at: from + 26, vol: 0.5},
	{file: 'tick', at: from + 38, vol: 0.35},
];
