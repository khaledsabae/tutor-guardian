/// Backup service — P1.3 data export/import (local-only).
///
/// Handles JSON export/import of user's local-only data:
/// - reflections (notes per lesson)
/// - favorites (lesson IDs + tip IDs)
///
/// The JSON format:
/// {
///   "version": 1,
///   "exported_at": "2026-06-11T12:00:00.000Z",
///   "reflections": { "lesson_id": { "text": "...", "created_at": "...", "updated_at": "..." } },
///   "favorites": { "lessons": ["lesson_id1", ...], "tips": ["tip_id1", ...] }
/// }
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'favorites_storage.dart';
import '../../reflections/data/reflection_storage.dart';

/// Result of an import operation.
class ImportResult {
  const ImportResult({
    required this.success,
    required this.importedReflectionsCount,
    required this.importedFavoritesCount,
    this.errorMessage,
  });

  final bool success;
  final int importedReflectionsCount;
  final int importedFavoritesCount;
  final String? errorMessage;
}

class BackupService {
  BackupService(this._prefs);

  static const int _currentVersion = 1;
  static const String _backupFilenamePrefix = 'almorabbi_backup_';
  static const String _backupFilenameExtension = '.json';

  final SharedPreferences _prefs;

  /// Export all local user data to a JSON string.
  String exportData() {
    final favoritesStorage = FavoritesStorage(_prefs);
    final reflectionsStorage = ReflectionStorage(_prefs);

    final favorites = favoritesStorage.loadAll();
    final reflections = reflectionsStorage.loadAll();

    final exportMap = <String, dynamic>{
      'version': 1,
      'exported_at': DateTime.now().toUtc().toIso8601String(),
      'reflections': reflections
          .map((k, v) => MapEntry(k, v.toJson())),
      'favorites': {
        'lessons': favorites['lessons'] ?? [],
        'tips': favorites['tips'] ?? [],
      },
    };

    const encoder = JsonEncoder.withIndent('  ');
    return encoder.convert(exportMap);
  }

  /// Generate a backup filename with current timestamp.
  String generateBackupFilename() {
    final now = DateTime.now();
    final timestamp = now.toUtc().toIso8601String().replaceAll(':', '-').replaceAll('.', '-');
    return '$_backupFilenamePrefix$timestamp$_backupFilenameExtension';
  }

  /// Export data and save to a file using file_picker (handled by UI layer).
  /// Returns the JSON string that should be saved.
  Future<String> exportToJson() async {
    return exportData();
  }

  /// Import data from a JSON string.
  ///
  /// Merges data with existing data (does not delete existing unless replaceAll is true).
  /// Returns [ImportResult] with counts and any error.
  Future<ImportResult> importFromJson(String jsonString, {bool replaceAll = false}) async {
    try {
      final Map<String, dynamic> decoded = jsonDecode(jsonString);

      // Validate version
      final version = decoded['version'] as int?;
      if (version == null) {
        return const ImportResult(
          success: false,
          importedReflectionsCount: 0,
          importedFavoritesCount: 0,
          errorMessage: 'ملف النسخ الاحتياطي غير صالح: حقل "version" مفقود.',
        );
      }
      if (version > _currentVersion) {
        return ImportResult(
          success: false,
          importedReflectionsCount: 0,
          importedFavoritesCount: 0,
          errorMessage: 'إصدار النسخ الاحتياطي ($version) أحدث من إصدار التطبيق ($_currentVersion). يرجى تحديث التطبيق.',
        );
      }

      final reflectionsStorage = ReflectionStorage(_prefs);

      // Import reflections
      int importedReflectionsCount = 0;
      if (decoded['reflections'] != null) {
        final reflectionsJson = decoded['reflections'] as Map<String, dynamic>;
        final existingReflections = reflectionsStorage.loadAll();

        if (replaceAll) {
          // Clear all and import fresh
          await reflectionsStorage.clearAll();
        }

        for (final entry in reflectionsJson.entries) {
          try {
            final entryJson = entry.value as Map<String, dynamic>;
            final reflectionEntry = ReflectionEntry.fromJson(entryJson);
            
            // Check if we should overwrite
            if (!replaceAll && existingReflections.containsKey(entry.key)) {
              // Keep existing, skip
              continue;
            }
            
            await reflectionsStorage.upsert(reflectionEntry);
            importedReflectionsCount++;
          } catch (e) {
            // Skip malformed entries
            continue;
          }
        }
      }

      // Import favorites
      int importedFavoritesCount = 0;
      if (decoded['favorites'] != null) {
        final favoritesJson = decoded['favorites'] as Map<String, dynamic>;
        final favoritesStorage = FavoritesStorage(_prefs);

        // Import lesson favorites
        final lessonIds = (favoritesJson['lessons'] as List?)?.cast<String>() ?? [];
        for (final lessonId in lessonIds) {
          if (favoritesStorage.isLessonFavorite(lessonId)) {
            continue; // Skip existing
          }
          await favoritesStorage.toggleLesson(lessonId);
          importedFavoritesCount++;
        }

        // Import tip favorites
        final tipIds = (favoritesJson['tips'] as List?)?.cast<String>() ?? [];
        for (final tipId in tipIds) {
          if (favoritesStorage.isTipFavorite(tipId)) {
            continue; // Skip existing
          }
          await favoritesStorage.toggleTip(tipId);
          importedFavoritesCount++;
        }
      }

      return ImportResult(
        success: true,
        importedReflectionsCount: importedReflectionsCount,
        importedFavoritesCount: importedFavoritesCount,
        errorMessage: null,
      );
    } on FormatException catch (e) {
      return ImportResult(
        success: false,
        importedReflectionsCount: 0,
        importedFavoritesCount: 0,
        errorMessage: 'ملف JSON غير صالح: ${e.message}',
      );
    } catch (e) {
      return ImportResult(
        success: false,
        importedReflectionsCount: 0,
        importedFavoritesCount: 0,
        errorMessage: 'حدث خطأ غير متوقع: $e',
      );
}
  }
}
