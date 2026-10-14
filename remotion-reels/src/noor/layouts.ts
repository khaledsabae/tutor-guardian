// Where everything sits, per frame size. Coordinates are in output pixels.
import {P, RoadCtrl} from './geometry';

export type StarSpec = {x: number; y: number; r: number; gold?: boolean};
export type SheetName = 'far' | 'mid' | 'near';

export type Layout = {
	W: number;
	H: number;
	k: number; // general size unit (shadow offsets, paddings)
	sheets: Record<SheetName, {crest: P[]; slide: number}>;
	mound: {crest: P[]; slide: number};
	sprigs: {x: number; y: number; size: number; rot: number}[]; // on the mound
	drift: {stars: number; far: number; mid: number; front: number};
	stars: StarSpec[];
	noor: {cx: number; crestY: number; size: number};
	// The path is cut in pieces, one per hill sheet; each piece is clipped by
	// its own sheet and hidden behind the sheet in front, so it disappears
	// over each crest and reappears smaller on the next one.
	roads: {sheet: SheetName; ctrl: RoadCtrl[]; share: number}[];
	lanterns: {road: number; t: number; side: 1 | -1; size: number}[];
	walk: {road: number; t0: number; t1: number; size: number};
	caption: {top: number; width: number; font: number; oneLine: boolean};
	bubble: {font: number; maxWidth: number; askFrac: number; answerFrac: number; lift: number};
	end: {
		logoCx: number;
		logoCy: number;
		logoSize: number;
		noorSize: number;
		noorSide: 'left' | 'right';
		textCx: number;
		textTop: number;
		textWidth: number;
		title: number;
		tagline: number;
		free: number;
		play: number;
		gap: number;
		hills: P[][];
		stars: StarSpec[];
	};
};

export const portrait: Layout = {
	W: 1080,
	H: 1920,
	k: 1,
	sheets: {
		far: {crest: [[-200, 760], [110, 700], [400, 742], [690, 800], [960, 708], [1280, 676]], slide: 600},
		mid: {crest: [[-200, 902], [180, 850], [470, 890], [760, 838], [1280, 906]], slide: 760},
		near: {crest: [[-200, 1082], [230, 1058], [560, 1090], [860, 1034], [1280, 1070]], slide: 920},
	},
	mound: {
		crest: [[-240, 1390], [20, 1290], [290, 1262], [500, 1286], [612, 1362], [670, 1520], [702, 1920], [720, 2300]],
		slide: 1100,
	},
	sprigs: [
		{x: 70, y: 1470, size: 124, rot: -6},
		{x: 480, y: 1520, size: 96, rot: 8},
		{x: 210, y: 1650, size: 88, rot: -3},
		{x: 560, y: 1760, size: 74, rot: 5},
	],
	drift: {stars: 8, far: 14, mid: 26, front: 40},
	stars: [
		{x: 90, y: 140, r: 16},
		{x: 330, y: 90, r: 12},
		{x: 1000, y: 110, r: 13},
		{x: 560, y: 175, r: 12},
		{x: 160, y: 560, r: 13},
		{x: 470, y: 600, r: 15},
		{x: 985, y: 530, r: 15},
		{x: 660, y: 655, r: 12},
		{x: 60, y: 680, r: 14},
		{x: 830, y: 640, r: 14},
		{x: 760, y: 150, r: 16, gold: true},
		{x: 230, y: 650, r: 19, gold: true},
		{x: 905, y: 600, r: 21, gold: true},
		{x: 560, y: 690, r: 13, gold: true},
		{x: 370, y: 545, r: 12, gold: true},
	],
	noor: {cx: 300, crestY: 1262, size: 860},
	roads: [
		{
			sheet: 'near',
			share: 0.62,
			ctrl: [
				{x: 1000, y: 1990, w: 300},
				{x: 880, y: 1770, w: 236},
				{x: 815, y: 1590, w: 186},
				{x: 880, y: 1425, w: 146},
				{x: 975, y: 1292, w: 114},
				{x: 905, y: 1170, w: 88},
				{x: 815, y: 1082, w: 70},
				{x: 780, y: 1010, w: 62},
			],
		},
		{
			sheet: 'mid',
			share: 0.26,
			ctrl: [
				{x: 772, y: 1140, w: 58},
				{x: 748, y: 1045, w: 54},
				{x: 692, y: 960, w: 46},
				{x: 652, y: 895, w: 40},
				{x: 640, y: 830, w: 36},
			],
		},
		{
			sheet: 'far',
			share: 0.12,
			ctrl: [
				{x: 650, y: 920, w: 30},
				{x: 655, y: 862, w: 28},
				{x: 680, y: 825, w: 22},
				{x: 700, y: 798, w: 18},
				{x: 708, y: 770, w: 16},
			],
		},
	],
	lanterns: [
		{road: 0, t: 0.6, side: 1, size: 132},
		{road: 0, t: 0.75, side: -1, size: 108},
		{road: 0, t: 0.92, side: 1, size: 86},
		{road: 1, t: 0.62, side: 1, size: 62},
		{road: 2, t: 0.45, side: -1, size: 44},
	],
	walk: {road: 0, t0: 0.16, t1: 0.36, size: 330},
	caption: {top: 250, width: 1000, font: 76, oneLine: false},
	bubble: {font: 56, maxWidth: 760, askFrac: 0.2, answerFrac: 0.7, lift: 26},
	end: {
		logoCx: 680,
		logoCy: 610,
		logoSize: 420,
		noorSize: 520,
		noorSide: 'left',
		textCx: 540,
		textTop: 890,
		textWidth: 1040,
		title: 184,
		tagline: 64,
		free: 46,
		play: 48,
		gap: 26,
		hills: [
			[[-200, 1690], [200, 1640], [560, 1686], [900, 1630], [1280, 1680]],
			[[-200, 1786], [300, 1750], [700, 1796], [1280, 1744]],
			[[-200, 1866], [400, 1846], [820, 1876], [1280, 1844]],
		],
		stars: [],
	},
};

export const wide: Layout = {
	W: 1920,
	H: 1080,
	k: 0.8,
	sheets: {
		far: {crest: [[-200, 545], [250, 500], [700, 540], [1150, 486], [1600, 530], [2120, 492]], slide: 320},
		mid: {crest: [[-200, 650], [400, 612], [900, 652], [1400, 606], [2120, 656]], slide: 400},
		near: {crest: [[-200, 770], [500, 746], [1000, 786], [1500, 738], [2120, 772]], slide: 480},
	},
	mound: {
		crest: [[-260, 968], [120, 884], [500, 860], [820, 882], [960, 948], [1030, 1088], [1070, 1300]],
		slide: 600,
	},
	sprigs: [
		{x: 110, y: 1000, size: 92, rot: -6},
		{x: 860, y: 1010, size: 74, rot: 8},
	],
	drift: {stars: 10, far: 18, mid: 32, front: 50},
	stars: [
		{x: 110, y: 90, r: 13},
		{x: 420, y: 60, r: 10},
		{x: 1500, y: 70, r: 12},
		{x: 1830, y: 120, r: 13},
		{x: 230, y: 300, r: 11},
		{x: 760, y: 330, r: 12},
		{x: 1180, y: 380, r: 10},
		{x: 1700, y: 330, r: 13},
		{x: 70, y: 450, r: 11},
		{x: 1880, y: 420, r: 10},
		{x: 600, y: 420, r: 15, gold: true},
		{x: 1420, y: 270, r: 17, gold: true},
		{x: 320, y: 400, r: 13, gold: true},
		{x: 1760, y: 470, r: 12, gold: true},
		{x: 1040, y: 240, r: 14, gold: true},
	],
	noor: {cx: 500, crestY: 860, size: 620},
	roads: [
		{
			sheet: 'near',
			share: 0.6,
			ctrl: [
				{x: 1400, y: 1130, w: 196},
				{x: 1310, y: 1030, w: 160},
				{x: 1320, y: 935, w: 128},
				{x: 1410, y: 860, w: 100},
				{x: 1390, y: 795, w: 80},
				{x: 1330, y: 748, w: 66},
				{x: 1306, y: 712, w: 60},
			],
		},
		{
			sheet: 'mid',
			share: 0.25,
			ctrl: [
				{x: 1320, y: 800, w: 60},
				{x: 1300, y: 752, w: 56},
				{x: 1240, y: 700, w: 48},
				{x: 1200, y: 655, w: 42},
				{x: 1190, y: 610, w: 38},
			],
		},
		{
			sheet: 'far',
			share: 0.15,
			ctrl: [
				{x: 1195, y: 670, w: 36},
				{x: 1200, y: 628, w: 32},
				{x: 1230, y: 560, w: 26},
				{x: 1240, y: 515, w: 22},
				{x: 1240, y: 480, w: 20},
			],
		},
	],
	lanterns: [
		{road: 0, t: 0.6, side: 1, size: 96},
		{road: 0, t: 0.78, side: -1, size: 80},
		{road: 0, t: 0.94, side: 1, size: 64},
		{road: 1, t: 0.55, side: -1, size: 54},
		{road: 2, t: 0.5, side: 1, size: 40},
	],
	walk: {road: 0, t0: 0.16, t1: 0.36, size: 240},
	caption: {top: 50, width: 1800, font: 64, oneLine: true},
	bubble: {font: 46, maxWidth: 820, askFrac: 0.2, answerFrac: 0.72, lift: 22},
	end: {
		logoCx: 1360,
		logoCy: 430,
		logoSize: 360,
		noorSize: 440,
		noorSide: 'right',
		textCx: 690,
		textTop: 190,
		textWidth: 1100,
		title: 156,
		tagline: 56,
		free: 40,
		play: 42,
		gap: 18,
		hills: [
			[[-200, 905], [400, 870], [900, 905], [1400, 862], [2120, 900]],
			[[-200, 965], [500, 940], [1100, 972], [2120, 935]],
			[[-200, 1022], [700, 1008], [1400, 1030], [2120, 1006]],
		],
		stars: [],
	},
};
