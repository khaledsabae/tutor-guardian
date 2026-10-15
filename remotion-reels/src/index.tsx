import {Composition} from 'remotion';
import {Reel} from './Reel';
import reelData from '../data/reel.json';
import {NoorTeaser} from './noor/NoorTeaser';
import {T} from './noor/timeline';
import {NoorDevSheet} from './noor/DevSheet';
import {CampaignCompositions} from './noor/campaign/reels';
import {VoCompositions} from './noor/campaign/VoReels';
import {TeaserWorldComposition} from './noor/campaign/TeaserWorld';

export const RemotionRoot: React.FC = () => {
	return (
		<>
			<Composition
				id="Reel"
				component={Reel}
				durationInFrames={33 * 30}
				fps={30}
				width={1080}
				height={1920}
				defaultProps={reelData}
			/>
			<Composition
				id="NoorTeaserAr"
				component={NoorTeaser}
				durationInFrames={T.total}
				fps={30}
				width={1080}
				height={1920}
				defaultProps={{lang: 'ar' as const, shape: 'portrait' as const}}
			/>
			<Composition
				id="NoorTeaserEn"
				component={NoorTeaser}
				durationInFrames={T.total}
				fps={30}
				width={1080}
				height={1920}
				defaultProps={{lang: 'en' as const, shape: 'portrait' as const}}
			/>
			<Composition
				id="NoorTeaserArWide"
				component={NoorTeaser}
				durationInFrames={T.total}
				fps={30}
				width={1920}
				height={1080}
				defaultProps={{lang: 'ar' as const, shape: 'wide' as const}}
			/>
			<Composition
				id="NoorTeaserDevSheet"
				component={NoorDevSheet}
				durationInFrames={T.total}
				fps={30}
				width={1472}
				height={1360}
				defaultProps={{
					lang: 'ar' as const,
					shape: 'portrait' as const,
					frames: [60, 112, 230, 300, 360, 410, 470, 600],
					cols: 4,
					scale: 1 / 3,
				}}
			/>
			<CampaignCompositions />
			<TeaserWorldComposition />
			<VoCompositions />
		</>
	);
};
