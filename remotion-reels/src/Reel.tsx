import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig, spring, Easing, AbsoluteFill, staticFile} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Cairo';

const {fontFamily} = loadFont();

export type ReelProps = {
	title: string;
	subtitle: string;
	scenes: {text: string; sub: string; start: number; end: number}[];
	brandColor?: string;
	accentColor?: string;
	logoPath?: string;
	screenshotPath?: string;
	backgroundVideoPath?: string;
};

const BRAND_NAVY = '#0B1021';
const BRAND_TEAL = '#14B8A6';      // brighter teal
const ACCENT_AMBER = '#FBBF24';
const ACCENT_CORAL = '#FB7185';
const ACCENT_VIOLET = '#A78BFA';

function splitWords(text: string): string[] {
	return text.split(/\s+/).filter(Boolean);
}

export const Reel: React.FC<ReelProps> = ({
	title,
	subtitle,
	scenes,
	logoPath,
	screenshotPath,
}) => {
	const frame = useCurrentFrame();
	const {fps, durationInFrames} = useVideoConfig();
	const t = frame / durationInFrames;
	const sec = frame / fps;

	// Background gradient with subtle shifting
	const bgPhase = interpolate(frame, [0, durationInFrames], [0, 360], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});

	const activeScene = scenes.find((s) => sec >= s.start && sec < s.end);
	const sceneProgress = activeScene
		? Math.min(1, Math.max(0, (sec - activeScene.start) / (activeScene.end - activeScene.start)))
		: 0;

	// CTA panel progress in last 6 seconds
	const ctaProgress = interpolate(frame, [durationInFrames - 6 * fps, durationInFrames - 5 * fps], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});

	const logoSrc = logoPath ? staticFile(logoPath) : undefined;
	const screenshotSrc = screenshotPath ? staticFile(screenshotPath) : undefined;

	return (
		<AbsoluteFill
			style={{
				fontFamily,
				background: `linear-gradient(${135 + bgPhase * 0.05}deg, #111a3d 0%, #16275c 50%, #1c2f6e 100%)`,
				overflow: 'hidden',
			}}
		>
			{/* Animated soft blobs */}
			<Blob x={0.2} y={0.25} color={BRAND_TEAL} frame={frame} delay={0} />
			<Blob x={0.75} y={0.4} color={ACCENT_AMBER} frame={frame} delay={120} />
			<Blob x={0.45} y={0.72} color={ACCENT_VIOLET} frame={frame} delay={240} />
			<Blob x={0.1} y={0.6} color={ACCENT_CORAL} frame={frame} delay={360} />

			{/* Top bar */}
			<div
				style={{
					position: 'absolute',
					top: 0,
					left: 0,
					width: '100%',
					height: 8,
					background: ACCENT_AMBER,
				}}
			/>

			{/* Logo area */}
			<div style={{position: 'absolute', top: 45, left: 50, display: 'flex', alignItems: 'center', gap: 20, zIndex: 20}}>
				{logoSrc ? (
					<img src={logoSrc} style={{width: 86, height: 86, objectFit: 'contain'}} />
				) : (
					<div
						style={{
							width: 86,
							height: 86,
							borderRadius: '50%',
							background: BRAND_TEAL,
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center',
							color: 'white',
							fontSize: 38,
							fontWeight: 700,
						}}
					>
						م
					</div>
				)}
				<span style={{color: '#fff', fontSize: 40, fontWeight: 700, letterSpacing: -1}}>المربّي</span>
			</div>

			{/* Screenshot circle */}
			{screenshotSrc ? (
				<div
					style={{
						position: 'absolute',
						top: '50%',
						left: '50%',
						transform: `translate(-50%, -70%) scale(${1 + 0.02 * Math.sin(frame * 0.02)})`,
						width: 420,
						height: 420,
						borderRadius: '50%',
						overflow: 'hidden',
						border: '6px solid rgba(255,255,255,0.25)',
						boxShadow: '0 20px 80px rgba(0,0,0,0.35)',
						zIndex: 10,
					}}
				>
					<img src={screenshotSrc} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
				</div>
			) : null}

			{/* Central content */}
			<div
				style={{
					position: 'absolute',
					top: '50%',
					left: 0,
					width: '100%',
					transform: 'translateY(15%)',
					textAlign: 'center',
					zIndex: 20,
					padding: '0 60px',
				}}
			>
				{activeScene ? (
					<SceneText text={activeScene.text} sub={activeScene.sub} progress={sceneProgress} />
				) : (
					<CTAText sec={sec} />
				)}
			</div>

			{/* CTA panel */}
			<div
				style={{
					position: 'absolute',
					bottom: 80,
					left: 50,
					right: 50,
					height: Math.max(0, ctaProgress * 380),
					background: 'rgba(11, 16, 33, 0.92)',
					border: `3px solid ${ACCENT_AMBER}`,
					borderRadius: 32,
					overflow: 'hidden',
					display: 'flex',
					flexDirection: 'column',
					alignItems: 'center',
					justifyContent: 'center',
					gap: 12,
					zIndex: 30,
					opacity: ctaProgress,
				}}
			>
				<span style={{color: '#fff', fontSize: 42, fontWeight: 700}}>حمّل المربّي مجاناً</span>
				<span style={{color: '#94a3b8', fontSize: 32}}>منهج تربية إسلامية متكامل</span>
				<span style={{color: '#cbd5e1', fontSize: 28}}>من الحمل لـ 18 سنة</span>
				<div
					style={{
						marginTop: 10,
						background: ACCENT_AMBER,
						color: BRAND_NAVY,
						padding: '20px 64px',
						borderRadius: 50,
						fontSize: 36,
						fontWeight: 800,
						display: 'flex',
						alignItems: 'center',
						gap: 14,
					}}
				>
					Google Play
					<span style={{fontSize: 32}}>→</span>
				</div>
			</div>
		</AbsoluteFill>
	);
};

const Blob: React.FC<{ x: number; y: number; color: string; frame: number; delay: number }> = ({
	x,
	y,
	color,
	frame,
	delay,
}) => {
	const scale = 1 + 0.08 * Math.sin((frame + delay) * 0.015);
	const cx = x * 1080 + 80 * Math.sin((frame + delay) * 0.008);
	const cy = y * 1920 + 80 * Math.cos((frame + delay) * 0.01);
	const radius = 320 * scale;
	return (
		<div
			style={{
				position: 'absolute',
				left: cx - radius,
				top: cy - radius,
				width: radius * 2,
				height: radius * 2,
				borderRadius: '50%',
				background: `radial-gradient(circle, ${color}66 0%, ${color}22 40%, transparent 70%)`,
				filter: 'blur(40px)',
				zIndex: 1,
			}}
		/>
	);
};

const SceneText: React.FC<{ text: string; sub: string; progress: number }> = ({text, sub, progress}) => {
	const words = splitWords(text);
	return (
		<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 24}}>
			<div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '18px 24px', direction: 'rtl'}}>
				{words.map((word, i) => {
					const wordProgress = Math.min(1, Math.max(0, (progress * words.length - i) / 0.8));
					const y = 40 * (1 - wordProgress);
					const opacity = wordProgress;
					return (
						<span
							key={i}
							style={{
								fontSize: 88,
								fontWeight: 800,
								color: '#fff',
								transform: `translateY(${y}px)`,
								opacity,
								textShadow: '0 4px 30px rgba(0,0,0,0.35)',
								lineHeight: 1.25,
							}}
						>
							{word}
						</span>
					);
				})}
			</div>
			<div
				style={{
					fontSize: 48,
					fontWeight: 500,
					color: '#cbd5e1',
					opacity: Math.min(1, Math.max(0, (progress - 0.35) / 0.4)),
					transform: `translateY(${20 * (1 - Math.min(1, Math.max(0, (progress - 0.35) / 0.4)))}px)`,
					marginTop: 12,
				}}
			>
				{sub}
			</div>
		</div>
	);
};

const CTAText: React.FC<{ sec: number }> = ({sec}) => {
	return (
		<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20}}>
			<div
				style={{
					fontSize: 90,
					fontWeight: 800,
					color: '#fff',
					textShadow: '0 4px 30px rgba(0,0,0,0.35)',
				}}
			>
				حمّل المربّي مجاناً
			</div>
			<div style={{fontSize: 48, color: '#94a3b8'}}>ابدأ رحلة تربية إسلامية متكاملة</div>
		</div>
	);
};
