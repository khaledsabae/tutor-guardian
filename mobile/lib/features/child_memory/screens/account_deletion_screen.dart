/// Settings → Privacy → «حذف الحساب» (MOBILE_API §10; Google Play's in-app
/// account deletion requirement).
///
/// The order on screen is the order of a careful decision: what goes, what
/// cannot be undone, a checkbox, then a final confirmation. Before deleting,
/// the app proves it holds the phone (§9.0.1) — the server refuses a session
/// that has not. And two calm states sit in front of the button when it cannot
/// work yet:
///   * a 72-hour pause (`deletion_paused_until`, or a `device_proof_cooldown`
///     answer): when it ends, on the parent's clock, why it exists, and the
///     e-mail path meanwhile;
///   * a server without in-app deletion (today's production): the e-mail path
///     and the public deletion page.
/// After the server answers 200 the client has already become a new device;
/// this screen clears the phone and ends on a page whose only way out is
/// closing the app — the next launch starts fresh.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../api/tg_client.dart';
import '../../../config/app_config.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../identity/identity_service.dart';
import '../data/local_wipe.dart';
import '../data/memory_models.dart';
import '../device_proof/device_proof_service.dart';
import '../providers/memory_providers.dart';
import '../widgets/memory_errors.dart';
import '../widgets/proof_views.dart';

/// The public page for deletion without the app (also the Play Console
/// "Delete account URL").
Uri get deleteAccountPageUri => Uri.parse('${AppConfig.apiBaseUrl}/delete-account');

enum _Phase { loading, unavailable, paused, ready, proving, deleting, failed }

/// The steps a deletion runs, injectable so tests need no plugins.
class AccountDeletionSteps {
  const AccountDeletionSteps({
    this.wipeLocal = wipeLocalDataAfterAccountDeletion,
    this.wasLinkedToGoogle = _linkedLocally,
  });

  /// Clears the phone after the server deleted the account.
  final Future<void> Function() wipeLocal;

  /// Whether this phone believed it was signed in with Google.
  final Future<bool> Function() wasLinkedToGoogle;

  static Future<bool> _linkedLocally() => IdentityService.instance.isLinked;
}

final accountDeletionStepsProvider =
    Provider<AccountDeletionSteps>((ref) => const AccountDeletionSteps());

class AccountDeletionScreen extends ConsumerStatefulWidget {
  const AccountDeletionScreen({super.key});

  @override
  ConsumerState<AccountDeletionScreen> createState() =>
      _AccountDeletionScreenState();
}

class _AccountDeletionScreenState extends ConsumerState<AccountDeletionScreen> {
  _Phase _phase = _Phase.loading;
  DateTime? _pausedUntil;
  Object? _error;
  bool _understood = false;

  @override
  void initState() {
    super.initState();
    unawaited(_loadStatus());
  }

  Future<void> _loadStatus() async {
    setState(() {
      _phase = _Phase.loading;
      _error = null;
    });
    try {
      final status = await ref.read(memoryRepositoryProvider).proofStatus();
      if (!mounted) return;
      final until = status?.deletionPausedUntil;
      setState(() {
        if (status == null) {
          _phase = _Phase.unavailable;
        } else if (until != null && until.isAfter(DateTime.now().toUtc())) {
          _pausedUntil = until;
          _phase = _Phase.paused;
        } else {
          _phase = _Phase.ready;
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _phase = _Phase.failed;
      });
    }
  }

  Future<void> _delete() async {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.deleteAccountConfirmTitle),
        content: Text(l10n.deleteAccountConfirmBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.cancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: colors.dangerFg),
            child: Text(l10n.deleteAccountButton),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;

    final repo = ref.read(memoryRepositoryProvider);
    final proof = ref.read(deviceProofServiceProvider);
    final steps = ref.read(accountDeletionStepsProvider);
    final navigator = Navigator.of(context);

    // 1. Prove the phone first, so the parent sees which step is running.
    setState(() => _phase = _Phase.proving);
    try {
      await proof.prove();
    } catch (e) {
      _fail(e);
      return;
    }

    // 2. Delete. A 5xx means nothing was deleted (one transaction).
    if (!mounted) return;
    setState(() => _phase = _Phase.deleting);
    // Read before the wipe clears it: it decides one line of the result.
    var wasLinked = false;
    try {
      wasLinked = await steps.wasLinkedToGoogle();
    } catch (_) {}
    final AccountDeletionResult result;
    try {
      result = await repo.deleteAccount();
    } catch (e) {
      _fail(e);
      return;
    }

    // 3. The server is done and this install is already a new device; clear
    // the phone, then leave nothing to navigate back into.
    await steps.wipeLocal();
    unawaited(navigator.pushAndRemoveUntil(
      AppRoutes.accountDeleted(result: result, wasLinkedToGoogle: wasLinked),
      (_) => false,
    ));
  }

  void _fail(Object e) {
    if (!mounted) return;
    setState(() {
      if (e is TgApiError && e.code == 'device_proof_cooldown') {
        _pausedUntil = e.availableAt ?? DateTime.now().toUtc();
        _phase = _Phase.paused;
      } else if (e is TgApiError && e.isMissingEndpoint) {
        _phase = _Phase.unavailable;
      } else {
        _error = e;
        _phase = _Phase.failed;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final busy = _phase == _Phase.proving || _phase == _Phase.deleting;
    return PopScope(
      // Leaving mid-deletion would hide the result of an irreversible step.
      canPop: !busy,
      child: Scaffold(
        appBar: AppBar(
          title: Text(l10n.deleteAccount),
          automaticallyImplyLeading: !busy,
        ),
        body: SafeArea(child: _body(context)),
      ),
    );
  }

  Widget _body(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    switch (_phase) {
      case _Phase.loading:
        return const Center(child: CircularProgressIndicator());
      case _Phase.proving:
        return const Center(child: ProofConfirmingView());
      case _Phase.deleting:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 16),
              Text(l10n.deleteAccountDeleting),
            ],
          ),
        );
      case _Phase.unavailable:
        return ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(l10n.deleteAccountUnavailable,
                style: TextStyle(
                    color: context.colors.ink, fontSize: 15, height: 1.6)),
            const SizedBox(height: 16),
            const _WithoutTheApp(),
          ],
        );
      case _Phase.paused:
        return ListView(
          padding: const EdgeInsets.all(20),
          children: [
            ProofPausedView(
              until: _pausedUntil ?? DateTime.now().toUtc(),
              body: l10n.proofPausedDeletionBody,
              emailLine: l10n.proofPausedEmail(kSupportEmail),
              emailSubject: l10n.deleteAccountEmailSubject,
            ),
            const SizedBox(height: 20),
            const _WhatGoes(),
          ],
        );
      case _Phase.failed:
        final e = _error;
        if (e != null && isProofError(e)) {
          return ListView(
            padding: const EdgeInsets.all(12),
            children: [
              ProofFailedView(
                error: e as TgApiError,
                onRetry: () => setState(() => _phase = _Phase.ready),
              ),
              const SizedBox(height: 12),
              const _WithoutTheApp(),
            ],
          );
        }
        final serverDown = e is TgApiError && (e.statusCode ?? 0) >= 500;
        return ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              serverDown
                  ? l10n.deleteAccountServerError
                  : describeActionFailure(context, e ?? 'error'),
              style: TextStyle(
                  color: context.colors.ink, fontSize: 15, height: 1.6),
            ),
            const SizedBox(height: 16),
            FilledButton(onPressed: _loadStatus, child: Text(l10n.retry)),
            const SizedBox(height: 20),
            const _WithoutTheApp(),
          ],
        );
      case _Phase.ready:
        return _ReadyBody(
          understood: _understood,
          onUnderstood: (v) => setState(() => _understood = v),
          onDelete: _understood ? _delete : null,
        );
    }
  }
}

class _ReadyBody extends StatelessWidget {
  const _ReadyBody({
    required this.understood,
    required this.onUnderstood,
    required this.onDelete,
  });

  final bool understood;
  final ValueChanged<bool> onUnderstood;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
      children: [
        const _WhatGoes(),
        const SizedBox(height: 14),
        Text(l10n.deleteAccountPermanent,
            style: TextStyle(
                color: colors.dangerFg,
                fontWeight: FontWeight.w800,
                fontSize: 15)),
        const SizedBox(height: 8),
        Text(l10n.deleteAccountProofNote,
            style: TextStyle(
                color: colors.textSecondary, fontSize: 13, height: 1.6)),
        const SizedBox(height: 12),
        CheckboxListTile(
          value: understood,
          onChanged: (v) => onUnderstood(v ?? false),
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          title: Text(l10n.deleteAccountUnderstand,
              style: TextStyle(color: colors.ink, fontWeight: FontWeight.w600)),
        ),
        const SizedBox(height: 8),
        FilledButton.icon(
          onPressed: onDelete,
          style: FilledButton.styleFrom(
            backgroundColor: colors.dangerFg,
            foregroundColor: colors.dangerBg,
          ),
          icon: const Icon(Icons.delete_forever_outlined),
          label: Text(l10n.deleteAccountButton),
        ),
        const SizedBox(height: 28),
        const _WithoutTheApp(),
      ],
    );
  }
}

/// What a deletion removes — said the same way before and during a pause.
class _WhatGoes extends StatelessWidget {
  const _WhatGoes();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final body = TextStyle(color: colors.ink, fontSize: 14, height: 1.6);
    final soft = TextStyle(color: colors.textSecondary, fontSize: 13, height: 1.6);
    Widget bullet(String text) => Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Icon(Icons.circle, size: 6, color: colors.inkSoft),
              ),
              const SizedBox(width: 10),
              Expanded(child: Text(text, style: body)),
            ],
          ),
        );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(l10n.deleteAccountIntro,
            style: body.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        bullet(l10n.deleteAccountItemChildren),
        bullet(l10n.deleteAccountItemChat),
        bullet(l10n.deleteAccountItemMemory),
        bullet(l10n.deleteAccountItemOther),
        const SizedBox(height: 8),
        Text(l10n.deleteAccountGoogle, style: soft),
        const SizedBox(height: 6),
        Text(l10n.deleteAccountPhone, style: soft),
        const SizedBox(height: 6),
        Text(l10n.deleteAccountBackups, style: soft),
      ],
    );
  }
}

/// The e-mail path and the public page — always offered, never a dead end.
class _WithoutTheApp extends StatelessWidget {
  const _WithoutTheApp();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: colors.surfaceAlt,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(l10n.privacyDeleteWithoutApp,
              style: TextStyle(
                  color: colors.ink, fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 4),
          Text(l10n.privacyDeleteWithoutAppDesc(kSupportEmail),
              style: TextStyle(
                  color: colors.textSecondary, fontSize: 12.5, height: 1.5)),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: () => openSupportEmail(context,
                    subject: l10n.deleteAccountEmailSubject),
                icon: const Icon(Icons.mail_outline_rounded),
                label: Text(l10n.deleteAccountEmailUs),
              ),
              OutlinedButton.icon(
                onPressed: () async {
                  try {
                    await launchUrl(deleteAccountPageUri,
                        mode: LaunchMode.externalApplication);
                  } catch (_) {}
                },
                icon: const Icon(Icons.open_in_new_rounded),
                label: Text(l10n.deleteAccountOpenPage),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// The end of a deletion. Back and the button both close the app: the next
/// launch is a fresh install in every respect that matters.
class AccountDeletedScreen extends StatelessWidget {
  const AccountDeletedScreen({
    super.key,
    required this.result,
    required this.wasLinkedToGoogle,
    this.closeApp = _closeApp,
  });

  final AccountDeletionResult result;
  final bool wasLinkedToGoogle;
  final Future<void> Function() closeApp;

  static Future<void> _closeApp() => SystemNavigator.pop();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final others = result.devices - 1;
    final soft = TextStyle(color: colors.textSecondary, fontSize: 14, height: 1.6);
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) unawaited(closeApp());
      },
      child: Scaffold(
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 48, 24, 32),
            children: [
              Icon(Icons.check_circle_outline_rounded,
                  size: 56, color: colors.primary),
              const SizedBox(height: 16),
              Text(
                l10n.accountDeletedTitle,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: colors.ink,
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 12),
              Text(l10n.accountDeletedBody,
                  textAlign: TextAlign.center, style: soft),
              if (others > 0) ...[
                const SizedBox(height: 10),
                Text(l10n.accountDeletedOthers(others),
                    textAlign: TextAlign.center, style: soft),
              ],
              if (wasLinkedToGoogle && !result.signedIn) ...[
                const SizedBox(height: 10),
                Text(l10n.accountDeletedUnconfirmed(kSupportEmail),
                    textAlign: TextAlign.center, style: soft),
              ],
              const SizedBox(height: 28),
              FilledButton(
                onPressed: () => unawaited(closeApp()),
                child: Text(l10n.accountDeletedClose),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
