// Voice-over cuts of the Arabic teaser and the six campaign reels (`_vo`).
// The picture is the silent reel itself, played through <Freeze> on a
// remapped clock: where a spoken line needs more time than its scene had,
// that scene plays a little slower (the plan is in vo_lines.ts, made by
// scripts/gen_vo.py), so the voice is never rushed. The reel's own sound is
// muted and replayed here on the remapped clock, ducked 9 dB under speech.
// Still no music: the voice sits on the same soft generated sounds.
import React from 'react';
import {AbsoluteFill, Audio, Composition, Freeze, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {SoundMute} from '../mix';
import {Cue, ReelSound} from './sound';
import {V1Remember, V1_CUES, V1_GAIN, V1_TOTAL} from './V1Remember';
import {V2Road, V2_CUES, V2_GAIN, V2_TOTAL} from './V2Road';
import {V3Ask, V3_CUES, V3_GAIN, V3_TOTAL} from './V3Ask';
import {V4Handover, V4_CUES, V4_GAIN, V4_TOTAL} from './V4Handover';
import {V5Ramadan, V5_CUES, V5_GAIN, V5_TOTAL} from './V5Ramadan';
import {V6Stories, V6_CUES, V6_GAIN, V6_TOTAL} from './V6Stories';
import {VO, VoPlan} from './vo_lines';
import {TeaserWorld, TEASER_WORLD_CUES, TEASER_WORLD_GAIN, TEASER_WORLD_TOTAL} from './TeaserWorld';

type VoId = 'v1' | 'v2' | 'v3' | 'v4' | 'v5' | 'v6' | 'teaser';

const SRC: Record<VoId, {id: string; Comp: React.FC; cues: Cue[]; gain: number; total: number}> = {
	v1: {id: 'CampaignV1RememberVo', Comp: V1Remember, cues: V1_CUES, gain: V1_GAIN, total: V1_TOTAL},
	v2: {id: 'CampaignV2RoadVo', Comp: V2Road, cues: V2_CUES, gain: V2_GAIN, total: V2_TOTAL},
	v3: {id: 'CampaignV3AskVo', Comp: V3Ask, cues: V3_CUES, gain: V3_GAIN, total: V3_TOTAL},
	v4: {id: 'CampaignV4HandoverVo', Comp: V4Handover, cues: V4_CUES, gain: V4_GAIN, total: V4_TOTAL},
	v5: {id: 'CampaignV5RamadanVo', Comp: V5Ramadan, cues: V5_CUES, gain: V5_GAIN, total: V5_TOTAL},
	v6: {id: 'CampaignV6StoriesVo', Comp: V6Stories, cues: V6_CUES, gain: V6_GAIN, total: V6_TOTAL},
	// the Arabic teaser with the new world cut in (TeaserWorld)
	teaser: {id: 'NoorTeaserArVo', Comp: TeaserWorld, cues: TEASER_WORLD_CUES, gain: TEASER_WORLD_GAIN, total: TEASER_WORLD_TOTAL},
};

/** Source frame -> output frame: each window [a, b] plays over (b - a + add) frames. */
export const srcToOut = (plan: VoPlan, f: number) =>
	plan.stretch.reduce((o, {a, b, add}) => o + (f >= b ? add : (add * Math.max(0, f - a)) / (b - a)), f);

/** Output frame -> source frame (srcToOut is increasing, so bisect). */
export const outToSrc = (plan: VoPlan, o: number) => {
	let lo = 0;
	let hi = o;
	for (let k = 0; k < 40; k++) {
		const mid = (lo + hi) / 2;
		if (srcToOut(plan, mid) < o) lo = mid;
		else hi = mid;
	}
	return (lo + hi) / 2;
};

export const voTotal = (id: VoId) => Math.ceil(srcToOut(VO[id], SRC[id].total));

const DUCK = Math.pow(10, -9 / 20); // sounds sit 9 dB lower while the voice speaks
const ATTACK = 5; // frames the duck leads the voice by
const RELEASE = 10; // frames it takes to come back up

const VoReel: React.FC<{reel: VoId}> = ({reel}) => {
	const frame = useCurrentFrame();
	const plan = VO[reel];
	const s = SRC[reel];
	const total = voTotal(reel);
	const src = Math.min(s.total - 1, outToSrc(plan, frame));
	const speaking = (f: number) =>
		plan.lines.reduce((m, l) => {
			const end = l.at + l.frames;
			const v = f < l.at ? 1 - (l.at - f) / ATTACK : f <= end ? 1 : 1 - (f - end) / RELEASE;
			return Math.max(m, Math.min(1, Math.max(0, v)));
		}, 0);
	const duck = (f: number) => 1 - (1 - DUCK) * speaking(f);
	const cues = s.cues.map((c) => ({...c, at: srcToOut(plan, c.at)}));
	return (
		<AbsoluteFill>
			<SoundMute.Provider value>
				<Freeze frame={src}>
					<s.Comp />
				</Freeze>
			</SoundMute.Provider>
			<ReelSound cues={cues} total={total} gain={s.gain} duck={duck} />
			{plan.lines.map((l, i) => (
				<Sequence key={i} from={l.at} durationInFrames={l.frames + 2} layout="none">
					<Audio src={staticFile(l.file)} />
				</Sequence>
			))}
		</AbsoluteFill>
	);
};

export const VoCompositions: React.FC = () => (
	<>
		{/* a reel whose lines are not recorded yet has no voice-over cut */}
		{(Object.keys(SRC) as VoId[]).filter((k) => VO[k]).map((k) => (
			<Composition
				key={k}
				id={SRC[k].id}
				component={VoReel}
				durationInFrames={voTotal(k)}
				fps={30}
				width={1080}
				height={1920}
				defaultProps={{reel: k}}
			/>
		))}
	</>
);
