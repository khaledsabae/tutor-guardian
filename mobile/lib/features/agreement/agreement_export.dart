/// Turning the signed agreement into something that goes on a wall.
///
/// The point of the export is that the agreement stops living in the app. A
/// media plan a family agreed to and then only ever saw inside the phone is
/// the weakest version of the idea; on the fridge it is read by everyone, by
/// accident, repeatedly.
///
/// PNG rather than PDF: there is no PDF toolchain in this project on either
/// side, and adding `pdf` + `printing` to render a one-page document is a
/// dependency decision for a format nobody asked for. A 3× PNG prints
/// legibly at A5.
///
/// PRIVACY: sharing hands the child's name and the family's agreement to
/// whatever app the parent picks. That is the parent's call and the point of
/// the feature — but it is the one place in the child surface where data
/// leaves the device, so [saveAgreementPng] exists on its own for families
/// who want the image without the share sheet.
library;

import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

/// Rendering scale. 3.0 is the floor for print: at 1.0 the image is screen
/// resolution and the text turns to mush on paper.
const double kAgreementPixelRatio = 3.0;

/// Renders the boundary to PNG bytes, or null when the key is not mounted.
Future<Uint8List?> captureAgreementPng(
  GlobalKey boundaryKey, {
  double pixelRatio = kAgreementPixelRatio,
}) async {
  final object = boundaryKey.currentContext?.findRenderObject();
  if (object is! RenderRepaintBoundary) return null;
  final image = await object.toImage(pixelRatio: pixelRatio);
  try {
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    return data?.buffer.asUint8List();
  } finally {
    image.dispose();
  }
}

String agreementFileName(String childName) {
  final safe = childName.replaceAll(RegExp(r'[^\w؀-ۿ]'), '_');
  return 'agreement_${safe.isEmpty ? 'child' : safe}.png';
}

/// Writes the PNG into the app's documents directory and returns its path.
Future<String?> saveAgreementPng(GlobalKey boundaryKey, String childName) async {
  final bytes = await captureAgreementPng(boundaryKey);
  if (bytes == null) return null;
  final dir = await getApplicationDocumentsDirectory();
  final file = File('${dir.path}/${agreementFileName(childName)}');
  await file.writeAsBytes(bytes, flush: true);
  return file.path;
}

Future<void> shareAgreementPng(GlobalKey boundaryKey, String childName) async {
  final path = await saveAgreementPng(boundaryKey, childName);
  if (path == null) return;
  await SharePlus.instance.share(ShareParams(files: [XFile(path)]));
}
