/// The three things a parent may see while a protected action waits on the
/// device proof (MOBILE_API §9.0.1): it is under way, it is paused until a
/// time, or it could not complete — each calm, each with a way forward.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../api/tg_client.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../device_proof/device_proof_service.dart' show kSupportEmail;

/// [utc] on the parent's own clock and calendar, in the app's language:
/// «الثلاثاء، ٧ أكتوبر ٢٠٢٦ ٦:٣٠ م» / "Tuesday, October 7, 2026 6:30 PM".
String formatLocalDateTime(BuildContext context, DateTime utc) {
  final m = MaterialLocalizations.of(context);
  final local = utc.toLocal();
  return '${m.formatFullDate(local)} ${m.formatTimeOfDay(TimeOfDay.fromDateTime(local))}';
}

/// Opens a new e-mail to [email]; when the phone has no mail app, copies the
/// address instead and says so — the e-mail path must never be a dead end.
Future<void> openSupportEmail(BuildContext context,
    {String email = kSupportEmail, String? subject}) async {
  final l10n = AppLocalizations.of(context);
  final messenger = ScaffoldMessenger.maybeOf(context);
  final uri = Uri(
    scheme: 'mailto',
    path: email,
    query: subject == null ? null : 'subject=${Uri.encodeComponent(subject)}',
  );
  var opened = false;
  try {
    opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
  } catch (_) {
    opened = false;
  }
  if (opened) return;
  await Clipboard.setData(ClipboardData(text: email));
  messenger?.showSnackBar(SnackBar(content: Text(l10n.supportEmailCopied(email))));
}

/// A tappable support address inside a sentence-length line.
class SupportEmailLine extends StatelessWidget {
  const SupportEmailLine({
    super.key,
    required this.text,
    this.email = kSupportEmail,
    this.subject,
  });

  final String text;
  final String email;
  final String? subject;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Semantics(
      button: true,
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () => openSupportEmail(context, email: email, subject: subject),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.mail_outline_rounded, size: 18, color: colors.primary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  text,
                  style: TextStyle(
                    color: colors.primary,
                    fontSize: 13,
                    height: 1.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// «نتأكّد أن هذا هاتفك…»
class ProofConfirmingView extends StatelessWidget {
  const ProofConfirmingView({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Semantics(
      liveRegion: true,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 32,
              height: 32,
              child: CircularProgressIndicator(
                  strokeWidth: 3, color: colors.primary),
            ),
            const SizedBox(height: 16),
            Text(
              l10n.proofConfirmingTitle,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: colors.ink,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.proofConfirmingBody,
              textAlign: TextAlign.center,
              style: TextStyle(
                  color: colors.textSecondary, fontSize: 13, height: 1.5),
            ),
          ],
        ),
      ),
    );
  }
}

/// A pause (`device_proof_cooldown`): when it ends, why, and what still
/// works. [child] is what stays available meanwhile (the memory switch).
class ProofPausedView extends StatelessWidget {
  const ProofPausedView({
    super.key,
    required this.until,
    required this.body,
    this.emailLine,
    this.emailSubject,
    this.child,
  });

  final DateTime until;
  final String body;

  /// A line naming the support address (tapping it opens an e-mail).
  final String? emailLine;
  final String? emailSubject;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colors.surfaceAlt,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.hourglass_top_rounded, color: colors.primary, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  l10n.proofPausedTitle(formatLocalDateTime(context, until)),
                  style: TextStyle(
                    color: colors.ink,
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(body,
              style: TextStyle(
                  color: colors.textSecondary, fontSize: 13, height: 1.6)),
          if (emailLine != null) ...[
            const SizedBox(height: 6),
            SupportEmailLine(text: emailLine!, subject: emailSubject),
          ],
          if (child != null) ...[
            const SizedBox(height: 12),
            child!,
          ],
        ],
      ),
    );
  }
}

/// The challenge could not complete: what happened, a retry, and the address.
class ProofFailedView extends StatelessWidget {
  const ProofFailedView({super.key, required this.error, this.onRetry});

  final TgApiError error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final email = error.supportEmail ?? kSupportEmail;
    // The server's own message names the address already for the two codes
    // that carry it; for the rest, add the line.
    final message = error.message.trim().isEmpty
        ? l10n.proofFailedBody
        : error.message.trim();
    final namesAddress = message.contains(email);
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Icon(Icons.phonelink_lock_outlined, size: 36, color: colors.inkSoft),
          const SizedBox(height: 12),
          Text(
            l10n.proofFailedTitle,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: colors.ink,
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 8),
          Text(message,
              textAlign: TextAlign.center,
              style: TextStyle(
                  color: colors.textSecondary, fontSize: 13, height: 1.6)),
          const SizedBox(height: 4),
          SupportEmailLine(
            text: namesAddress ? email : l10n.proofSupport(email),
            email: email,
          ),
          if (onRetry != null) ...[
            const SizedBox(height: 8),
            Center(
              child: FilledButton(
                onPressed: onRetry,
                child: Text(l10n.retry),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// True for the errors the proof views explain (rather than a generic retry).
bool isProofError(Object error) =>
    error is TgApiError &&
    const {
      'device_proof_required',
      'device_proof_cooldown',
      'no_push_token',
      'push_unavailable',
      'proof_rate_limited',
      'proof_failed',
      'proof_timeout',
    }.contains(error.code);
