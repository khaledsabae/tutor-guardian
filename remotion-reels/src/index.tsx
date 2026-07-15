import {Composition, staticFile} from 'remotion';
import {Reel} from './Reel';
import reelData from '../data/reel.json';

export const RemotionRoot: React.FC = () => {
	return (
		<Composition
			id="Reel"
			component={Reel}
			durationInFrames={33 * 30}
			fps={30}
			width={1080}
			height={1920}
			defaultProps={reelData}
		/>
	);
};
