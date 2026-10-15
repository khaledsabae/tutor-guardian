// Shared by the teaser and the campaign reels: when a reel is played inside
// its voice-over cut, the cut makes the reel's own sound component silent
// and plays the (retimed, ducked) cues itself next to the voice.
import {createContext} from 'react';

export const SoundMute = createContext(false);
