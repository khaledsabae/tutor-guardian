import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/animated_progress_bar.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/skeleton.dart';
import '../models/flashcard_deck.dart';
import '../providers/lesson_assets_provider.dart';

/// Interactive flashcards viewer — replaces the Phase-4 placeholder.
///
/// Loads one or more decks (their ids come from the lesson-assets
/// metadata), merges the cards, and presents them as a swipeable card
/// deck (neighbors peek + scale) with tappable 3-D flip.
class FlashcardsScreen extends ConsumerWidget {
  final List<String> deckIds;
  const FlashcardsScreen({super.key, required this.deckIds});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final decksAsync = ref.watch(flashcardDecksProvider(deckIds.join(',')));

    return Scaffold(
      appBar: AppBar(title: const Text('📇 فلاش كاردز')),
      body: decksAsync.when(
        loading: () => const SingleChildScrollView(
          physics: NeverScrollableScrollPhysics(),
          child: SkeletonList(count: 2, itemHeight: 260),
        ),
        error: (e, _) => EmptyState(
          emoji: '📡',
          title: 'تعذّر تحميل البطاقات',
          actionLabel: 'إعادة المحاولة',
          onAction: () =>
              ref.invalidate(flashcardDecksProvider(deckIds.join(','))),
        ),
        data: (decks) {
          final cards = decks.expand((d) => d.cards).toList();
          if (cards.isEmpty) {
            return const EmptyState(
              emoji: '📇',
              title: 'لا توجد بطاقات متاحة لهذا الدرس حالياً',
            );
          }
          return _FlashcardPager(cards: cards);
        },
      ),
    );
  }
}

class _FlashcardPager extends StatefulWidget {
  final List<Flashcard> cards;
  const _FlashcardPager({required this.cards});

  @override
  State<_FlashcardPager> createState() => _FlashcardPagerState();
}

class _FlashcardPagerState extends State<_FlashcardPager> {
  // Deck feel: current card dominates, neighbors peek from the sides.
  final _controller = PageController(viewportFraction: 0.88);
  int _index = 0;

  bool get _isLast => _index == widget.cards.length - 1;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _go(int delta) {
    final next = (_index + delta).clamp(0, widget.cards.length - 1);
    _controller.animateToPage(
      next,
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOut,
    );
  }

  @override
  Widget build(BuildContext context) {
    final total = widget.cards.length;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Text(
            'البطاقة ${_index + 1} من $total',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppTheme.textSecondary,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ),
        const SizedBox(height: 8),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: AnimatedProgressBar(value: (_index + 1) / total, height: 12),
        ),
        Expanded(
          child: PageView.builder(
            controller: _controller,
            itemCount: total,
            onPageChanged: (i) => setState(() => _index = i),
            itemBuilder: (context, i) => AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                // Neighbors shrink slightly for a stacked-deck feel.
                double scale = 1;
                if (_controller.position.haveDimensions) {
                  final page = _controller.page ?? _index.toDouble();
                  scale = (1 - ((page - i).abs() * .08)).clamp(.85, 1.0);
                }
                return Transform.scale(scale: scale, child: child);
              },
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 20),
                child: FlipCard(card: widget.cards[i]),
              ),
            ),
          ),
        ),
        if (_isLast)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF4E0),
                borderRadius: BorderRadius.circular(Dt.rChip),
              ),
              child: const Text(
                'أنهيت البطاقات! 🎉',
                style: TextStyle(
                  color: Dt.accentDeep,
                  fontWeight: FontWeight.w800,
                ),
              ),
            )
                .animate()
                .scale(
                  begin: const Offset(.6, .6),
                  duration: Dt.base,
                  curve: Curves.easeOutBack,
                )
                .fadeIn(),
          ),
        Padding(
          padding: const EdgeInsets.only(bottom: 24, left: 24, right: 24),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              IconButton.filledTonal(
                onPressed: _index > 0 ? () => _go(-1) : null,
                icon: const Icon(Icons.arrow_forward),
                tooltip: 'السابقة',
              ),
              Text(
                'اضغط للقلب · اسحب للتالي',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textMuted,
                    ),
              ),
              IconButton.filledTonal(
                onPressed: _index < total - 1 ? () => _go(1) : null,
                icon: const Icon(Icons.arrow_back),
                tooltip: 'التالية',
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// A single card that flips between question (front) and answer (back)
/// with a 3-D rotation when tapped.
class FlipCard extends StatefulWidget {
  final Flashcard card;
  const FlipCard({super.key, required this.card});

  @override
  State<FlipCard> createState() => _FlipCardState();
}

class _FlipCardState extends State<FlipCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _anim = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 450),
  );

  @override
  void didUpdateWidget(FlipCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.card != widget.card) _anim.value = 0;
  }

  @override
  void dispose() {
    _anim.dispose();
    super.dispose();
  }

  void _flip() {
    if (_anim.isAnimating) return;
    _anim.value < 0.5 ? _anim.forward() : _anim.reverse();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: _flip,
      child: AnimatedBuilder(
        animation: _anim,
        builder: (context, _) {
          final curved =
              Curves.easeInOutBack.transform(_anim.value.clamp(0.0, 1.0));
          final angle = curved * math.pi;
          final showBack = curved >= 0.5;
          return Transform(
            alignment: Alignment.center,
            transform: Matrix4.identity()
              ..setEntry(3, 2, 0.001)
              ..rotateY(angle),
            child: showBack
                ? Transform(
                    alignment: Alignment.center,
                    transform: Matrix4.identity()..rotateY(math.pi),
                    child: _CardFace.back(card: widget.card),
                  )
                : _CardFace.front(card: widget.card),
          );
        },
      ),
    );
  }
}

class _CardFace extends StatelessWidget {
  final Flashcard card;
  final bool isFront;

  const _CardFace.front({required this.card}) : isFront = true;
  const _CardFace.back({required this.card}) : isFront = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        gradient: isFront ? Dt.primaryGradient : null,
        color: isFront ? null : Colors.white,
        borderRadius: BorderRadius.circular(Dt.rSheet),
        boxShadow: isFront
            ? Dt.softShadow(Dt.primary)
            : Dt.cardShadow,
      ),
      padding: const EdgeInsets.all(24),
      child: isFront
          ? Center(
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('🤔', style: TextStyle(fontSize: 44)),
                    const SizedBox(height: 16),
                    Text(
                      card.front,
                      textAlign: TextAlign.center,
                      style: theme.textTheme.titleMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        height: 1.7,
                      ),
                    ),
                  ],
                ),
              ),
            )
          : SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text('💡', style: TextStyle(fontSize: 22)),
                      const SizedBox(width: 8),
                      Text(
                        'الإجابة',
                        style: theme.textTheme.titleSmall?.copyWith(
                          color: AppTheme.primary,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  for (final point in card.backPoints)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Padding(
                            padding: EdgeInsets.only(top: 7),
                            child: Icon(Icons.circle,
                                size: 7, color: AppTheme.primary),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              point,
                              style: theme.textTheme.bodyMedium
                                  ?.copyWith(height: 1.7),
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
    );
  }
}
