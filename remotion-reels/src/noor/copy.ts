// On-screen copy. Arabic is easy Modern Standard Arabic (no dialect).
export type Lang = 'ar' | 'en';

export type Copy = {
	caption: string[]; // lines
	ask: string;
	answer: string;
	title: string;
	tagline: string;
	free: string;
	play: string;
	scan: string;
};

export const COPY: Record<Lang, Copy> = {
	ar: {
		caption: ['كل خطوة صغيرة مع ابنك…', 'قنديل يضيء.'],
		ask: 'جرّبتها الليلة؟ كيف جرت؟',
		answer: 'الحمد لله، نفعت!',
		title: 'المربّي',
		tagline: 'مربٍّ يعرف ابنك… خطوة بخطوة',
		free: 'مجاني لوجه الله — بلا إعلانات',
		play: 'متاح على Google Play',
		scan: 'امسح للتنزيل',
	},
	en: {
		caption: ['Every small step with your child…', 'a lantern lights up.'],
		ask: 'Did you try it tonight? How did it go?',
		answer: 'Alhamdulillah, it worked!',
		title: 'Almorabbi',
		tagline: 'A guide who knows your child, step by step',
		free: 'Free, for the sake of Allah — no ads',
		play: 'Available on Google Play',
		scan: 'Scan to download',
	},
};
