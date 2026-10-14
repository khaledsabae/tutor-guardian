// The hand-over gate's copy of the age gate must agree with the server's.
//
// `backend/guardrails/child_surface.v1.yaml` is the authority; the app keeps a
// copy (`kChildSurfacePolicy`) only so it never *offers* what the server will
// refuse. A copy is a thing that drifts — so this reads the YAML itself and
// fails the build the day the two disagree, band by band.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:yaml/yaml.dart';

import 'package:almorabbi/features/handover/child_surface_policy.dart';

YamlMap _policy() => loadYaml(
        File('../backend/guardrails/child_surface.v1.yaml').readAsStringSync())
    as YamlMap;

void main() {
  group('the client map agrees with child_surface.v1.yaml', () {
    final policy = _policy();
    final bands = policy['age_bands'] as YamlMap;

    test('the YAML parsed into the bands we expect', () {
      expect(bands.keys, containsAll(<String>['under-2', '2-3', '4-6', '7-9']),
          reason: 'the policy file moved or changed shape');
    });

    for (final band in bands.keys.cast<String>()) {
      test('band $band: same allowed_surfaces', () {
        final server = ((bands[band] as YamlMap)['allowed_surfaces'] as YamlList)
            .cast<String>()
            .toSet();
        expect(kChildSurfacePolicy.containsKey(band), isTrue,
            reason: 'band $band is in the policy but not in the app');
        expect(kChildSurfacePolicy[band], server,
            reason: 'the app would offer or hide surfaces for $band that the '
                'server decides differently');
      });
    }

    test('the app has no band the policy does not', () {
      expect(kChildSurfacePolicy.keys.toSet(), bands.keys.cast<String>().toSet());
    });

    test('every surface the gate can hand over is a policy surface', () {
      final surfaces = (policy['surfaces'] as YamlMap).keys.cast<String>().toSet();
      expect(surfaces, containsAll(kHandoverSurfaces));
    });
  });

  group('profile age → band, as the server maps it', () {
    test('prenatal-1 and the legacy 0-3 are under two: no child surface', () {
      for (final age in ['prenatal-1', '0-3']) {
        expect(childSurfaceBand(age), 'under-2', reason: age);
        expect(handoverSurfacesFor(age), isEmpty, reason: age);
      }
    });

    test('unknown or missing fails closed', () {
      for (final age in [null, '', 'unspecified', '19-25', 'garbage']) {
        expect(childSurfaceBand(age), 'under-2', reason: '$age');
        expect(handoverSurfacesFor(age), isEmpty, reason: '$age');
      }
    });

    test('the server source maps the same way', () {
      // core/taxonomy.py: "0-3" aliases onto "prenatal-1", which is "under-2",
      // and an unreadable band falls back to "under-2". If any of these lines
      // change, childSurfaceBand has to change with them.
      final taxonomy =
          File('../backend/app/core/taxonomy.py').readAsStringSync();
      expect(taxonomy, contains('"0-3": "prenatal-1"'));
      expect(taxonomy, contains('{"prenatal-1": "under-2"}'));
      expect(taxonomy, contains('FALLBACK_CHILD_SURFACE_BAND = "under-2"'));
    });
  });

  group('what the gate offers, band by band', () {
    test('2-3: listening with the screen off, and nothing else', () {
      expect(handoverSurfacesFor('2-3'), ['screen_off']);
    });

    test('4-6: never the habit surface (the server answers surface_not_allowed)',
        () {
      expect(handoverSurfacesFor('4-6'), ['mission', 'screen_off']);
      expect(childSurfaceAllowed('4-6', 'habit'), isFalse);
    });

    test('7-9: habits join; no licence', () {
      expect(handoverSurfacesFor('7-9'), ['habit', 'mission', 'screen_off']);
    });

    test('10-12 and 13-15: the licence, where a scenario bank exists', () {
      for (final band in ['10-12', '13-15']) {
        expect(handoverSurfacesFor(band),
            ['habit', 'mission', 'license', 'screen_off'],
            reason: band);
      }
    });

    test('16-18: licence allowed by policy but hidden — no bank to open', () {
      expect(childSurfaceAllowed('16-18', 'license'), isTrue);
      expect(handoverSurfacesFor('16-18'), ['habit', 'mission', 'screen_off']);
    });

    test('nothing offered is outside the policy, for any band', () {
      for (final entry in kChildSurfacePolicy.entries) {
        expect(entry.value, containsAll(handoverSurfacesFor(entry.key)),
            reason: entry.key);
      }
    });

    test('the licence bands match the scenario banks on disk', () {
      final banks = Directory('../knowledge_base/curriculum/license')
          .listSync()
          .map((f) => f.uri.pathSegments.last)
          .map((n) => RegExp(r'_(\d+-\d+)\.json$').firstMatch(n)?.group(1))
          .whereType<String>()
          .toSet();
      expect(kLicenseBankBands, banks);
    });
  });
}
