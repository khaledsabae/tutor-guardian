/// Backup service provider — P1.3 data export/import.
///
/// Wraps [BackupService] so it can be consumed via Riverpod.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/program/data/backup_service.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';

/// The reactive backup service provider.
final backupServiceProvider = Provider<BackupService>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider).requireValue;
  return BackupService(prefs);
});
