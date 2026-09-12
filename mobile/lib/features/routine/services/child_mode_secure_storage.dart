/// Secure storage helpers for child-mode session tokens and PIN.
library;

import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _storage = FlutterSecureStorage(
  aOptions: AndroidOptions(
    resetOnError: true,
  ),
  iOptions: IOSOptions(
    accessibility: KeychainAccessibility.first_unlock,
  ),
);

const _kChildTokenKey = 'tg_child_session_token';
const _kPinHashKey = 'tg_child_mode_pin_hash';
const _kChildModeActiveKey = 'tg_child_mode_active';
const _kParentTokenKey = 'tg_parent_auth_token';

Future<void> saveParentToken(String token) async {
  try {
    await _storage.write(key: _kParentTokenKey, value: token);
  } catch (_) {}
}

Future<String?> getParentToken() async {
  try {
    return await _storage.read(key: _kParentTokenKey);
  } catch (_) {
    return null;
  }
}

Future<void> saveChildToken(String token) async {
  try {
    await _storage.write(key: _kChildTokenKey, value: token);
  } catch (_) {}
}

Future<String?> getChildToken() async {
  try {
    return await _storage.read(key: _kChildTokenKey);
  } catch (_) {
    return null;
  }
}

Future<void> clearChildToken() async {
  try {
    await _storage.delete(key: _kChildTokenKey);
  } catch (_) {}
}

Future<void> setChildModeActive(bool active) async {
  try {
    await _storage.write(key: _kChildModeActiveKey, value: active ? '1' : '0');
  } catch (_) {}
}

Future<bool> isChildModeActive() async {
  try {
    return (await _storage.read(key: _kChildModeActiveKey)) == '1';
  } catch (_) {
    return false;
  }
}

Future<void> clearChildMode() async {
  try {
    await _storage.delete(key: _kChildTokenKey);
    await _storage.delete(key: _kChildModeActiveKey);
  } catch (_) {}
}

Future<void> setChildModePin(String pin) async {
  try {
    final hash = _hashPin(pin);
    await _storage.write(key: _kPinHashKey, value: hash);
  } catch (_) {}
}

Future<bool> verifyChildModePin(String pin) async {
  try {
    final stored = await _storage.read(key: _kPinHashKey);
    if (stored == null) return false;
    return _hashPin(pin) == stored;
  } catch (_) {
    return false;
  }
}

Future<bool> hasChildModePin() async {
  try {
    return (await _storage.read(key: _kPinHashKey)) != null;
  } catch (_) {
    return false;
  }
}

String _hashPin(String pin) => sha256.convert(utf8.encode(pin.trim())).toString();

/// Generate a numeric PIN that is easy for a child to type.
String generateChildPin({int digits = 4}) {
  final rand = Random.secure();
  return List.generate(digits, (_) => rand.nextInt(10)).join();
}
