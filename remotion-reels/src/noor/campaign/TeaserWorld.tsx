// The Arabic teaser, refreshed with the app's new world. The teaser plays as
// it was up to the moment Noor's answer lands; then, before the sheets fall
// to the end card, two short glimpses of the new world are cut in — the
// family's road (reel 2: the lit stretch, «أنتم هنا», the gates «على الأفق»
// and Rajab's sky) and the child's corner (reel 4: the doors open on «يا
// عمر، هذا ركنك», the candle, the story) — played from those reels
// themselves, a little faster, so the art is one and the same.
// The sound is the teaser's own cues plus those of the two glimpses, retimed
// onto this clock; the voice-over cut (VoReels, id `teaser`) ducks them all.
import React from 'react';
import {AbsoluteFill, Composition, Freeze, useCurrentFrame} from 'remotion';
import {NoorTeaser} from '../NoorTeaser';
import {CUES as TEASER_CUES, MIX_GAIN as TEASER_GAIN} from '../sound';
import {T as TEASER_T} from '../timeline';
import {SoundMute} from '../mix';
import {Cue, ReelSound} from './sound';
import {V2Road, V2_CUES, V2_GAIN} from './V2Road';
import {V4Handover, V4_CUES, V4_GAIN} from './V4Handover';

// `mix`: the glimpses play their reels' cues faster and closer together, so they sit lower in the teaser's mix
type Seg = {Comp: React.FC; a: number; b: number; speed: number; cues: Cue[]; gain: number; mix: number};

// Its own QR code (VD08), so the world cut's scans are told apart from the plain Arabic cut's.
const Teaser: React.FC = () => <NoorTeaser lang="ar" shape="portrait" qrCut="world" />;
const Road: React.FC = () => <V2Road />;
const Corner: React.FC = () => <V4Handover />;

/** Where the glimpses are cut in: Noor's answer has landed, the sheets have not yet fallen. */
const CUT = 488;

const SEGS: Seg[] = [
	{Comp: Teaser, a: 0, b: CUT, speed: 1, cues: TEASER_CUES, gain: TEASER_GAIN, mix: 1},
	// «درب الأسرة»: the page drops, Noor walks the lit road, the gates, Rajab's stars
	{Comp: Road, a: 70, b: 300, speed: 2.2, cues: V2_CUES, gain: V2_GAIN, mix: 0.75},
	// «ركن الطفل»: the doors open on the corner, the story card is tapped, the story
	{Comp: Corner, a: 112, b: 262, speed: 1.7, cues: V4_CUES, gain: V4_GAIN, mix: 0.75},
	{Comp: Teaser, a: CUT, b: TEASER_T.total, speed: 1, cues: TEASER_CUES, gain: TEASER_GAIN, mix: 1},
];

const LEN = SEGS.map((s) => Math.round((s.b - s.a) / s.speed));
const START = LEN.map((_, i) => LEN.slice(0, i).reduce((x, y) => x + y, 0));
export const TEASER_WORLD_TOTAL = LEN.reduce((x, y) => x + y, 0);

/** The output frame where each glimpse starts (for the voice-over script). */
export const TEASER_WORLD_MARKS = {road: START[1], corner: START[2], resume: START[3]};

/** Every segment's cues on this clock, trimmed to its window, in the teaser's mix. */
export const TEASER_WORLD_CUES: Cue[] = SEGS.flatMap((s, i) =>
	s.cues
		.filter((c) => c.at >= s.a && c.at < s.b)
		.map((c) => ({...c, at: START[i] + (c.at - s.a) / s.speed, vol: (c.vol * s.gain * s.mix) / TEASER_GAIN})),
);
export const TEASER_WORLD_GAIN = TEASER_GAIN;

export const TeaserWorld: React.FC = () => {
	const frame = useCurrentFrame();
	const i = START.reduce((k, st, j) => (frame >= st ? j : k), 0);
	const s = SEGS[i];
	const src = Math.min(s.b - 1, s.a + (frame - START[i]) * s.speed);
	return (
		<AbsoluteFill>
			<SoundMute.Provider value>
				<Freeze frame={src}>
					<s.Comp />
				</Freeze>
			</SoundMute.Provider>
			<ReelSound cues={TEASER_WORLD_CUES} total={TEASER_WORLD_TOTAL} gain={TEASER_WORLD_GAIN} />
		</AbsoluteFill>
	);
};

export const TeaserWorldComposition: React.FC = () => (
	<Composition id="NoorTeaserArWorld" component={TeaserWorld} durationInFrames={TEASER_WORLD_TOTAL} fps={30} width={1080} height={1920} />
);
