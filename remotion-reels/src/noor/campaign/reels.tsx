// The six campaign reels (1080×1920, 30 fps) and a dev contact sheet that
// shows one reel at several frames in a single still.
import React from 'react';
import {AbsoluteFill, Composition, Freeze} from 'remotion';
import {V1Remember, V1_TOTAL} from './V1Remember';
import {V2Road, V2_TOTAL} from './V2Road';
import {V3Ask, V3_TOTAL} from './V3Ask';
import {V4Handover, V4_TOTAL} from './V4Handover';
import {V5Ramadan, V5_TOTAL} from './V5Ramadan';
import {V6Stories, V6_TOTAL} from './V6Stories';

export type ReelId = 'v1' | 'v2' | 'v3' | 'v4' | 'v5' | 'v6';

export const REELS: Record<ReelId, {id: string; component: React.FC<{safe?: boolean}>; total: number}> = {
	v1: {id: 'CampaignV1Remember', component: V1Remember, total: V1_TOTAL},
	v2: {id: 'CampaignV2Road', component: V2Road, total: V2_TOTAL},
	v3: {id: 'CampaignV3Ask', component: V3Ask, total: V3_TOTAL},
	v4: {id: 'CampaignV4Handover', component: V4Handover, total: V4_TOTAL},
	v5: {id: 'CampaignV5Ramadan', component: V5Ramadan, total: V5_TOTAL},
	v6: {id: 'CampaignV6Stories', component: V6Stories, total: V6_TOTAL},
};

type SheetProps = {reel: ReelId; frames: number[]; cols: number; scale: number; safe: boolean};

export const ReelSheet: React.FC<SheetProps> = ({reel, frames, cols, scale, safe}) => {
	const Reel = REELS[reel].component;
	return (
		<AbsoluteFill style={{background: '#fff'}}>
			{frames.map((f, i) => (
				<div
					key={f}
					style={{
						position: 'absolute',
						left: (i % cols) * (1080 * scale + 8),
						top: Math.floor(i / cols) * (1920 * scale + 30),
						width: 1080 * scale,
						height: 1920 * scale + 30,
					}}
				>
					<div
						style={{
							width: 1080,
							height: 1920,
							transform: `scale(${scale})`,
							transformOrigin: '0 0',
							position: 'relative',
							overflow: 'hidden',
						}}
					>
						<Freeze frame={f}>
							<Reel safe={safe} />
						</Freeze>
					</div>
					<div style={{position: 'absolute', top: 1920 * scale + 2, left: 4, font: '20px monospace'}}>f{f}</div>
				</div>
			))}
		</AbsoluteFill>
	);
};

export const CampaignCompositions: React.FC = () => (
	<>
		{(Object.keys(REELS) as ReelId[]).map((k) => (
			<Composition
				key={k}
				id={REELS[k].id}
				component={REELS[k].component}
				durationInFrames={REELS[k].total}
				fps={30}
				width={1080}
				height={1920}
				defaultProps={{safe: false}}
			/>
		))}
		<Composition
			id="CampaignSheet"
			component={ReelSheet}
			durationInFrames={Math.max(...Object.values(REELS).map((r) => r.total))}
			fps={30}
			width={4 * (360 + 8)}
			height={2 * (640 + 30)}
			defaultProps={{reel: 'v1' as ReelId, frames: [20, 60, 140, 180, 260, 330, 380, 500], cols: 4, scale: 1 / 3, safe: true}}
		/>
	</>
);
