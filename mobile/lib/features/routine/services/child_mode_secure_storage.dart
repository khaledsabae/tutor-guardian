/// Secure storage helpers for child-mode session tokens and PIN.
library;

import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _storage = FlutterSecureStorage();

const _kChildTokenKey = 'tg_child_session_token';
const _kPinHashKey = 'tg_child_mode_pin_hash';
const _kChildModeActiveKey = 'tg_child_mode_active';
const _kParentTokenKey = 'tg_parent_auth_token';

Future<void> saveParentToken(String token) =>
    _storage.write(key: _kParentTokenKey, value: token);

Future<String?> getParentToken() => _storage.read(key: _kParentTokenKey);

Future<void> saveChildToken(String token) =>
    _storage.write(key: _kChildTokenKey, value: token);

Future<String?> getChildToken() => _storage.read(key: _kChildTokenKey);

Future<void> clearChildToken() => _storage.delete(key: _kChildTokenKey);

Future<void> setChildModeActive(bool active) =>
    _storage.write(key: _kChildModeActiveKey, value: active ? '1' : '0');

Future<bool> isChildModeActive() async =>
    (await _storage.read(key: _kChildModeActiveKey)) == '1';

Future<void> clearChildMode() async {
  await _storage.delete(key: _kChildTokenKey);
  await _storage.delete(key: _kChildModeActiveKey);
}

Future<void> setChildModePin(String pin) async {
  final hash = _hashPin(pin);
  await _storage.write(key: _kPinHashKey, value: hash);
}

Future<bool> verifyChildModePin(String pin) async {
  final stored = await _storage.read(key: _kPinHashKey);
  if (stored == null) return false;
  return _hashPin(pin) == stored;
}

Future<bool> hasChildModePin() async =>
    (await _storage.read(key: _kPinHashKey)) != null;

String _hashPin(String pin) => sha256.convert(utf8.encode(pin.trim())).toString();

/// Generate a numeric PIN that is easy for a child to type.
String generateChildPin({int digits = 4}) {
  final rand = Random.secure();
  return List.generate(digits, (_) => rand.nextInt(10)).join();
}
